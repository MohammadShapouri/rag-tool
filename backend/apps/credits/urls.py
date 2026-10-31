from django.urls import path
from .views import CreditRateView, MyCreditHistoryView, AdminTopUpCreditView

urlpatterns = [
    path('rates/', CreditRateView.as_view(), name='credit_rates'),
    path('history/', MyCreditHistoryView.as_view(), name='credit_history'),
    path('admin/topup/', AdminTopUpCreditView.as_view(), name='admin_topup'),
]
