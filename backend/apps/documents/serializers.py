import os
from rest_framework import serializers
from .models import Document

class DocumentSerializer(serializers.ModelSerializer):
    uploaded_at = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Document
        fields = (
            'id', 'department', 'uploaded_by', 'file', 'filename', 
            'file_size', 'status', 'error_message', 'chunk_count',
            'vector_count', 'created_at', 'uploaded_at'
        )
        read_only_fields = (
            'id', 'uploaded_by', 'filename', 'file_size', 'status',
            'error_message', 'chunk_count', 'vector_count', 'created_at', 'uploaded_at'
        )

    def create(self, validated_data):
        file = validated_data['file']
        validated_data['filename'] = os.path.basename(file.name)
        validated_data['file_size'] = file.size
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)
