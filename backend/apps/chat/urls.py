from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ChatSessionViewSet, ChatQueryView

router = DefaultRouter()
router.register(r'sessions', ChatSessionViewSet, basename='chat-session')

urlpatterns = [
    path('sessions/<int:session_id>/query/', ChatQueryView.as_view(), name='chat_query'),
] + router.urls
