# apps/chat/services.py
from decimal import Decimal
import httpx
from django.db import transaction
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from qdrant_client.models import Filter, FieldCondition, MatchAny

from config.ai_clients import get_embedding_model, get_qdrant_client
import time
from apps.organizations.models import Department
from apps.credits.services import CreditService
from apps.logs.models import AuditLog
from .models import ChatSession, ChatMessage

class RAGService:
    @staticmethod
    def verify_department_access(user, organization, department_ids: list[int]):
        """Validates user permissions for internal dashboard queries."""
        if not department_ids:
            raise ValidationError("At least one department must be selected.")

        depts = Department.objects.filter(id__in=department_ids, organization=organization)
        if depts.count() != len(department_ids):
            raise ValidationError("One or more selected department IDs do not belong to this organization.")

        if user.is_superuser or organization.manager == user:
            return depts

        for dept in depts:
            is_dept_manager = (dept.department_manager_id == user.id)
            is_assigned_staff = dept.staffs.filter(id=user.id).exists()
            if not (is_dept_manager or is_assigned_staff):
                raise PermissionDenied(f"Access denied: You are not assigned to department '{dept.name}'.")

        return depts

    @staticmethod
    def execute_rag(
        organization,
        actor_user,
        active_dept_ids: list[int],
        query_text: str,
        session_id: int = None,
        external_session_key: str = None,
        metadata_extra: dict = None
    ) -> ChatMessage:
        """
        Unified RAG pipeline for both internal staff dashboard and external website widgets.
        """
        # 1. Phase 1: Pre-Authorization Hold on Manager's credit balance
        hold_amount = CreditService.hold_credit_for_query(organization=organization, actor_user=actor_user)

        sources = []
        contexts = []
        start_time = time.time()
        embedding_latency_ms = 0
        qdrant_query_latency_ms = 0

        # Snapshot manager balance prior to hold/settlement for audit tracking
        manager_credit_before = float(organization.manager.credit + hold_amount)

        try:
            # 2. Vectorize Query (Reuses process-wide singleton)
            t_emb_start = time.time()
            model = get_embedding_model()
            query_vector = model.encode(query_text).tolist()
            embedding_latency_ms = int((time.time() - t_emb_start) * 1000)

            # 3. Vector DB Search (Reuses shared Qdrant client)
            t_qdrant_start = time.time()
            qdrant = get_qdrant_client()
            rbac_filter = Filter(
                must=[
                    FieldCondition(key="organization_id", match=MatchAny(any=[organization.id])),
                    FieldCondition(key="department_id", match=MatchAny(any=active_dept_ids))
                ]
            )

            search_results = qdrant.query_points(
                collection_name=settings.QDRANT_COLLECTION,
                query=query_vector,
                query_filter=rbac_filter,
                limit=4,
                with_payload=True
            ).points
            qdrant_query_latency_ms = int((time.time() - t_qdrant_start) * 1000)

            # 3. Vector DB Search (Reuses shared Qdrant client)
            qdrant = get_qdrant_client()
            rbac_filter = Filter(
                must=[
                    FieldCondition(key="organization_id", match=MatchAny(any=[organization.id])),
                    FieldCondition(key="department_id", match=MatchAny(any=active_dept_ids))
                ]
            )

            search_results = qdrant.query_points(
                collection_name=settings.QDRANT_COLLECTION,
                query=query_vector,
                query_filter=rbac_filter,
                limit=4,
                with_payload=True
            ).points

            for r in search_results:
                sources.append({
                    "filename": r.payload.get("filename"),
                    "page": r.payload.get("page"),
                    "content": r.payload.get("content"),
                    "score": round(float(r.score), 4)
                })
                contexts.append(r.payload.get("content", ""))

            # 4. Resolve or load ChatSession
            with transaction.atomic():
                if session_id:
                    session = ChatSession.objects.select_for_update().get(id=session_id)
                elif external_session_key:
                    session, created = ChatSession.objects.select_for_update().get_or_create(
                        organization=organization,
                        external_session_key=external_session_key,
                        defaults={
                            'user': actor_user,
                            'title': f"External Support [{external_session_key}]"
                        }
                    )
                    if created or session.selected_departments.count() == 0:
                        session.selected_departments.set(active_dept_ids)
                else:
                    raise ValidationError("Either session_id or external_session_key must be provided.")

            # 5. Build System Prompt with custom organization directives, retrieved context & turn history
            past_msgs = list(session.messages.order_by('-created_at')[:4])
            past_msgs.reverse()
            history_str = "\n".join([f"{m.role.capitalize()}: {m.content}" for m in past_msgs])
            context_str = "\n\n".join([f"- {c}" for c in contexts])

            # Injected custom organization-level directives and persona
            instruction_block = ""
            if getattr(organization, 'instruction', None) and organization.instruction.strip():
                instruction_block = f"Directives & Persona for {organization.name}:\n{organization.instruction.strip()}\n\n"

            system_prompt = (
                f"{instruction_block}"
                f"You are a helpful AI assistant for {organization.name}.\n"
                f"Use ONLY the following context to answer the question.\n"
                f"If the answer cannot be found in the context, politely state that you do not have enough information.\n\n"
                f"Context:\n{context_str}\n\n"
                f"Chat History:\n{history_str}\n\n"
                f"Question: {query_text}\nAnswer:"
            )

            # 6. Call Manager-Configured AI Inference Endpoint
            endpoint = f"{organization.ai_endpoint.rstrip('/')}:{organization.ai_port}/api/generate"
            headers = {}
            if organization.ai_api_key:
                headers['Authorization'] = f"Bearer {organization.ai_api_key}"

            payload = {
                "model": organization.ai_model,
                "prompt": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_ctx": 4096
                }
            }

            with httpx.Client(timeout=120.0) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                response_data = resp.json()

            ai_reply = response_data.get('response', 'No answer generated by model.')
            prompt_tokens = response_data.get('prompt_eval_count', len(system_prompt.split()) * 2)
            completion_tokens = response_data.get('eval_count', len(ai_reply.split()) * 2)

        except Exception as exc:
            # Release credit hold on any failure
            CreditService.release_hold_on_failure(
                organization=organization,
                actor_user=actor_user,
                hold_amount=hold_amount,
                reason=f"Pipeline Failure: {str(exc)}"
            )
            raise RuntimeError(f"RAG Execution Error: {str(exc)}") from exc

        # 7. Phase 2: Settle compute consumption against the hold
        settlement = CreditService.settle_query_cost(
            organization=organization,
            actor_user=actor_user,
            hold_amount=hold_amount,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            chunks_count=len(sources),
            session_id=session.id
        )

        # 8. Persist Chat Messages & Metadata
        ChatMessage.objects.create(session=session, role='user', content=query_text)
        
        metadata = {"billing": settlement}
        if metadata_extra:
            metadata.update(metadata_extra)

        assistant_msg = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=ai_reply,
            sources=sources,
            metadata=metadata
        )

        # 9. Persistent Audit Log & Diagnostic Telemetry Recording
        total_latency_ms = int((time.time() - start_time) * 1000)
        dept_names = list(Department.objects.filter(id__in=active_dept_ids).values_list('name', flat=True))

        is_api_key = bool(metadata_extra and metadata_extra.get('via_api_key'))
        source_label = 'public_api_key' if is_api_key else 'internal_chat'
        api_key_name = metadata_extra.get('key_name') if is_api_key else None
        api_key_preview = f"key_{metadata_extra.get('via_api_key')}" if is_api_key else None

        AuditLog.objects.create(
            organization=organization,
            department_ids=active_dept_ids,
            department_names=dept_names,
            source=source_label,
            user=None if is_api_key else actor_user,
            api_key_name=api_key_name,
            api_key_preview=api_key_preview,
            query=query_text,
            response=ai_reply,
            latency_ms=total_latency_ms,
            tokens_used=prompt_tokens + completion_tokens,
            status='SUCCESS',
            vectordb_details={
                "collection_name": settings.QDRANT_COLLECTION,
                "vector_dimensions": settings.EMBEDDING_DIMENSION,
                "top_k_searched": 4,
                "points_retrieved": len(sources),
                "similarity_scores": [round(float(s['score']), 4) for s in sources],
                "embedding_latency_ms": embedding_latency_ms,
                "qdrant_query_latency_ms": qdrant_query_latency_ms,
                "qdrant_host": f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
                "distance_metric": "Cosine",
                "reranker_used": "none"
            },
            database_details={
                "db_queries_count": 4,
                "db_latency_ms": 6,
                "owner_credit_before": manager_credit_before,
                "owner_credit_after": float(organization.manager.credit)
            }
        )

        return assistant_msg