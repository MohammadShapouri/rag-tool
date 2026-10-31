from rest_framework import serializers
from .models import CreditRateConfig, CreditTransaction

class CreditRateConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditRateConfig
        fields = '__all__'

class CreditTransactionSerializer(serializers.ModelSerializer):
    payer_email = serializers.ReadOnlyField(source='payer.email')
    actor_username = serializers.ReadOnlyField(source='actor.username')
    organization_name = serializers.ReadOnlyField(source='organization.name')

    class Meta:
        model = CreditTransaction
        fields = (
            'id', 'payer_email', 'actor_username', 'organization_name',
            'transaction_type', 'amount', 'balance_after', 'description', 
            'metadata', 'created_at'
        )
