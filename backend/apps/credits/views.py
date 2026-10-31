from decimal import Decimal
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import CreditRateConfig, CreditTransaction
from .serializers import CreditRateConfigSerializer, CreditTransactionSerializer
from .services import CreditService
from apps.accounts.permissions import IsSuperUser

class CreditRateView(generics.RetrieveUpdateAPIView):
    serializer_class = CreditRateConfigSerializer

    def get_object(self):
        return CreditRateConfig.get_rates()

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsSuperUser()]


class MyCreditHistoryView(generics.ListAPIView):
    """
    Allows a manager to view all transactions where their credits were consumed or topped up.
    """
    serializer_class = CreditTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return CreditTransaction.objects.all()
        return CreditTransaction.objects.filter(payer=user)


class AdminTopUpCreditView(APIView):
    """
    Superuser endpoint to manually top up credits for an organization manager.
    """
    permission_classes = [IsSuperUser]

    def post(self, request):
        user_id = request.data.get('user_id')
        amount_raw = request.data.get('amount')
        reason = request.data.get('reason', 'Admin Manual Top-up')

        if not user_id or not amount_raw:
            return Response({'error': 'user_id and amount are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(amount_raw))
            if amount <= Decimal('0.0000'):
                return Response({'error': 'Amount must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({'error': 'Invalid decimal value for amount.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        CreditService.topup_user(target_user, amount, admin_user=request.user, reason=reason)

        return Response({
            'status': 'Success',
            'user': target_user.email,
            'new_balance': str(target_user.credit)
        }, status=status.HTTP_200_OK)
