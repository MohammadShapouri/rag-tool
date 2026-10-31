# apps/apikeys/external_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.exceptions import PermissionDenied
from django.db.models import F

from .authentication import APIKeyAuthentication
from .external_serializers import ExternalQueryRequestSerializer
from .models import OrganizationAPIKey
from apps.organizations.models import Department
from apps.chat.services import RAGService


class ExternalSupportRAGView(APIView):
    """
    Public query endpoint authenticated via X-API-Key or Authorization Bearer header.
    Rate-limited by config/throttling.py via rate_limits.yml.
    Delegates retrieval, inference, and two-phase billing directly to RAGService.
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ExternalQueryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query_text = serializer.validated_data['query']
        client_session_key = serializer.validated_data.get('session_id', 'default')
        requested_dept_ids = serializer.validated_data.get('department_ids', [])

        api_key_obj = request.api_key_obj
        org = request.organization
        manager = org.manager

        # 1. Organization Public Access Check
        if not getattr(org, 'is_public', True):
            return Response(
                {"error": f"Public API access is disabled for organization '{org.name}'."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Scope Verification: Filter accessible departments to only those where dept.is_public == True
        permitted_dept_ids = api_key_obj.get_scoped_department_ids()
        public_dept_ids = list(Department.objects.filter(
            id__in=permitted_dept_ids,
            is_public=True
        ).values_list('id', flat=True))

        if not public_dept_ids:
            return Response(
                {"error": "No public departments are available for external queries under this API key."},
                status=status.HTTP_403_FORBIDDEN
            )

        if requested_dept_ids:
            if not set(requested_dept_ids).issubset(set(public_dept_ids)):
                raise PermissionDenied("One or more requested departments are either not public or exceed this API key's authorized scope.")
            active_dept_ids = requested_dept_ids
        else:
            active_dept_ids = public_dept_ids

        # 3. Delegate directly to RAGService (Reuses shared Qdrant client & embedding model singleton)
        try:
            assistant_msg = RAGService.execute_rag(
                organization=org,
                actor_user=manager,
                active_dept_ids=active_dept_ids,
                query_text=query_text,
                external_session_key=client_session_key,
                metadata_extra={
                    "via_api_key": api_key_obj.id,
                    "key_name": api_key_obj.name
                }
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to complete query: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # 4. Atomically increment request_count on the API Key
        OrganizationAPIKey.objects.filter(id=api_key_obj.id).update(request_count=F('request_count') + 1)

        # 5. Format response matching frontend PublicChatQueryResponse interface
        billing = assistant_msg.metadata.get("billing", {})
        active_depts = list(Department.objects.filter(id__in=active_dept_ids).values_list('name', flat=True))

        return Response({
            "answer": assistant_msg.content,
            "sources": assistant_msg.sources,
            "session_id": client_session_key,
            "credits_deducted": str(billing.get("total_deduction", "0.0000")),
            "credit_deducted": float(billing.get("total_deduction", 1.0)),
            "organization": org.name,
            "model": org.ai_model,
            "departments_queried": active_depts,
            "created_at": assistant_msg.created_at.isoformat()
        }, status=status.HTTP_200_OK)