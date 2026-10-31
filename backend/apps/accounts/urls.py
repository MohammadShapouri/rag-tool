from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView,
    ProfileView,
    GlobalConfigView,
    UserRosterView,
    SuperuserUserViewSet,
)

router = DefaultRouter()
router.register(r'users', SuperuserUserViewSet, basename='user')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', ProfileView.as_view(), name='profile'),
    path('admin/global-config/', GlobalConfigView.as_view(), name='global_config'),
] + router.urls
