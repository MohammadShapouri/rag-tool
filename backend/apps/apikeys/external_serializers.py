from rest_framework import serializers

class ExternalQueryRequestSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=2000, required=True)
    # Optional: External system session identifier (e.g., end-user cookie or customer ID)
    session_id = serializers.CharField(max_length=128, required=False, default="default")
    # Optional subset filter of department IDs (must fall within the key's allowed scopes)
    department_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )

class ExternalQueryResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    sources = serializers.ListField()
    session_id = serializers.CharField()
    credits_deducted = serializers.CharField()