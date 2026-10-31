from decimal import Decimal
from django.db import transaction
from django.core.exceptions import PermissionDenied
from .models import CreditRateConfig, CreditTransaction

class CreditService:
    @staticmethod
    def hold_credit_for_query(organization, actor_user) -> Decimal:
        """
        PHASE 1 (Pre-Authorization Hold):
        Atomically locks the manager row with select_for_update(), validates balance,
        and immediately places a hold equal to 'min_query_balance'.
        Prevents multiple parallel requests from bypassing the balance check.
        """
        rates = CreditRateConfig.get_rates()
        hold_amount = rates.min_query_balance

        with transaction.atomic():
            manager = organization.manager.__class__.objects.select_for_update().get(id=organization.manager.id)

            if manager.credit < hold_amount:
                raise PermissionDenied(
                    f"Insufficient credits. Required to initiate query: {hold_amount:.4f}. "
                    f"Current balance: {manager.credit:.4f}"
                )

            # Deduct the hold upfront
            manager.credit -= hold_amount
            manager.save(update_fields=['credit'])

            CreditTransaction.objects.create(
                payer=manager,
                actor=actor_user,
                organization=organization,
                transaction_type='RAG_QUERY',
                amount=-hold_amount,
                balance_after=manager.credit,
                description=f"Query pre-authorization hold by {actor_user.username}",
                metadata={"status": "HOLD", "held_amount": str(hold_amount)}
            )

        return hold_amount

    @staticmethod
    def settle_query_cost(organization, actor_user, hold_amount: Decimal, prompt_tokens: int, completion_tokens: int, chunks_count: int, session_id: int) -> dict:
        """
        PHASE 2 (Settlement Reconciliation):
        Calculates exact compute consumption and reconciles against the upfront hold.
        - If actual_cost < hold_amount: Refunds the difference.
        - If actual_cost > hold_amount: Deducts the remainder.
        """
        rates = CreditRateConfig.get_rates()
        prompt_cost = (Decimal(prompt_tokens) / Decimal(1000)) * rates.cost_per_1k_prompt_tokens
        completion_cost = (Decimal(completion_tokens) / Decimal(1000)) * rates.cost_per_1k_completion_tokens
        chunk_cost = Decimal(chunks_count) * rates.cost_per_chunk_retrieved
        actual_cost = (rates.base_query_fee + prompt_cost + completion_cost + chunk_cost).quantize(Decimal('0.0001'))

        # Positive adjustment means refund; negative means additional charge
        adjustment = (hold_amount - actual_cost).quantize(Decimal('0.0001'))

        with transaction.atomic():
            manager = organization.manager.__class__.objects.select_for_update().get(id=organization.manager.id)

            manager.credit += adjustment
            if manager.credit < Decimal('0.0000'):
                manager.credit = Decimal('0.0000')
            manager.save(update_fields=['credit'])

            CreditTransaction.objects.create(
                payer=manager,
                actor=actor_user,
                organization=organization,
                transaction_type='RAG_QUERY',
                amount=adjustment,
                balance_after=manager.credit,
                description=f"Query settlement (Cost: {actual_cost:.4f}, Hold: {hold_amount:.4f})",
                metadata={
                    "status": "SETTLED",
                    "session_id": session_id,
                    "actual_cost": str(actual_cost),
                    "hold_amount": str(hold_amount),
                    "adjustment": str(adjustment),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "chunks_retrieved": chunks_count
                }
            )

        return {
            "actual_cost": actual_cost,
            "hold_amount": hold_amount,
            "adjustment": adjustment,
            "total_deduction": actual_cost
        }

    @staticmethod
    def release_hold_on_failure(organization, actor_user, hold_amount: Decimal, reason: str = "Inference Failure"):
        """
        Rollback handler: If Qdrant or the LLM fails, releases the pre-authorized hold.
        """
        with transaction.atomic():
            manager = organization.manager.__class__.objects.select_for_update().get(id=organization.manager.id)
            manager.credit += hold_amount
            manager.save(update_fields=['credit'])

            CreditTransaction.objects.create(
                payer=manager,
                actor=actor_user,
                organization=organization,
                transaction_type='RAG_QUERY',
                amount=hold_amount,
                balance_after=manager.credit,
                description=f"Hold refunded: {reason}",
                metadata={"status": "REFUNDED", "refunded_amount": str(hold_amount)}
            )

    @staticmethod
    def charge_document_ingestion(organization, actor_user, document_id: int, filename: str, page_count: int):
        """
        Charges the Organization Manager for OCR, embedding compute, and vector indexing.
        """
        rates = CreditRateConfig.get_rates()
        deduction = (Decimal(page_count) * rates.cost_per_document_page).quantize(Decimal('0.0001'))

        with transaction.atomic():
            manager = organization.manager.__class__.objects.select_for_update().get(id=organization.manager.id)

            manager.credit = max(Decimal('0.0000'), manager.credit - deduction)
            manager.save(update_fields=['credit'])

            CreditTransaction.objects.create(
                payer=manager,
                actor=actor_user,
                organization=organization,
                transaction_type='DOCUMENT_INGESTION',
                amount=-deduction,
                balance_after=manager.credit,
                description=f"Ingested '{filename}' ({page_count} pages)",
                metadata={
                    "document_id": document_id,
                    "filename": filename,
                    "page_count": page_count,
                    "cost_per_page": str(rates.cost_per_document_page)
                }
            )

    @staticmethod
    def topup_user(user, amount: Decimal, admin_user=None, reason="Admin Top-up"):
        """
        Manual balance adjustment by a Superuser.
        """
        with transaction.atomic():
            locked_user = user.__class__.objects.select_for_update().get(id=user.id)
            locked_user.credit += amount
            locked_user.save(update_fields=['credit'])

            CreditTransaction.objects.create(
                payer=locked_user,
                actor=admin_user,
                transaction_type='ADMIN_TOPUP',
                amount=amount,
                balance_after=locked_user.credit,
                description=reason,
                metadata={"granted_by": admin_user.username if admin_user else "System"}
            )
