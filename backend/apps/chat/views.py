from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import ChatSession
from .serializers import ChatSessionSerializer, ChatMessageSerializer
from .services import RAGService

class ChatSessionViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = ChatSession.objects.select_related('organization').prefetch_related('messages', 'selected_departments')
        # Superuser cross-tenant auditing: superusers can inspect all chat sessions across all tenants
        if user.is_superuser:
            return qs.all()
        return qs.filter(user=user)

    @action(detail=True, methods=['get'], url_path='messages')
    def messages(self, request, pk=None):
        """
        GET /api/chat/sessions/<id>/messages/
        Returns array of conversation turns for this session.
        """
        session = self.get_object()
        serializer = ChatMessageSerializer(session.messages.all(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ChatQueryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        query_text = request.data.get('query', '').strip()
        if not query_text:
            return Response({'error': 'query field is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = ChatSession.objects.select_related('organization').prefetch_related('selected_departments').get(
                id=session_id, user=request.user
            )
        except ChatSession.DoesNotExist:
            return Response({'error': 'Chat session not found'}, status=status.HTTP_404_NOT_FOUND)

        dept_ids = list(session.selected_departments.values_list('id', flat=True))
        
        # Validate access
        RAGService.verify_department_access(request.user, session.organization, dept_ids)

        try:
            response_message = RAGService.execute_rag(
                organization=session.organization,
                actor_user=request.user,
                active_dept_ids=dept_ids,
                query_text=query_text,
                session_id=session.id
            )
            return Response(ChatMessageSerializer(response_message).data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)