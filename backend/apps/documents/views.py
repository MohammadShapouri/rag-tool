import os
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.db.models import Q
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector
from django.conf import settings
from .models import Document
from .serializers import DocumentSerializer
from .permissions import CanManageDepartmentDocs
from .tasks import process_document_task

class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageDepartmentDocs]

    def get_queryset(self):
        user = self.request.user
        dept_id = self.request.query_params.get('department')
        qs = Document.objects.select_related('department__organization')
        
        if dept_id:
            qs = qs.filter(department_id=dept_id)

        if user.is_superuser:
            return qs

        return qs.filter(
            Q(department__organization__manager=user) |
            Q(department__department_manager=user) |
            Q(department__staffs=user)
        ).distinct()

    def perform_create(self, serializer):
        dept = serializer.validated_data['department']
        user = self.request.user
        
        # Staff cannot upload files, only Org Manager or Dept Manager
        if not (user.is_superuser or dept.organization.manager == user or dept.department_manager == user):
            raise permissions.PermissionDenied("Staff cannot upload documents to this department.")

        doc = serializer.save()
        # Trigger Celery Background Processing
        process_document_task.delay(doc.id)

    def perform_destroy(self, instance):
        # Delete vectors from Qdrant first
        try:
            client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
            client.delete(
                collection_name=settings.QDRANT_COLLECTION,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="document_id", match=MatchValue(value=instance.id))]
                    )
                )
            )
        except Exception:
            pass
        
        # Remove physical file
        if instance.file and os.path.exists(instance.file.path):
            os.remove(instance.file.path)
            
        instance.delete()
