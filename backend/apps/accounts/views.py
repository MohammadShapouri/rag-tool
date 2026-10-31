from rest_framework import generics, viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import User, GlobalConfig
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    GlobalConfigSerializer,
    StaffUserBriefSerializer,
    AdminUserSerializer,
)
from .permissions import IsSuperUser

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class GlobalConfigView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request):
        config = GlobalConfig.get_config()
        return Response(GlobalConfigSerializer(config).data)

    def put(self, request):
        config = GlobalConfig.get_config()
        serializer = GlobalConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserRosterView(generics.ListAPIView):
    """
    GET /api/auth/users/
    Lists all users with brief attributes for staff assignment.
    Accessible to all authenticated users.
    """
    queryset = User.objects.all().order_by('username')
    serializer_class = StaffUserBriefSerializer
    permission_classes = [IsAuthenticated]


class SuperuserUserViewSet(viewsets.ModelViewSet):
    """
    CRUD viewset for root administration of accounts at /api/auth/users/.
    - GET /api/auth/users/ (list): Accessible to authenticated users (returns brief roster for staff/managers).
    - POST, PUT, PATCH, DELETE: Strictly restricted to Superusers.
    """
    queryset = User.objects.all().order_by('username')
    serializer_class = AdminUserSerializer

    def get_permissions(self):
        if self.action == 'list':
            return [IsAuthenticated()]
        return [IsSuperUser()]

    def get_serializer_class(self):
        if self.action == 'list' and not getattr(self.request.user, 'is_superuser', False):
            return StaffUserBriefSerializer
        return AdminUserSerializer