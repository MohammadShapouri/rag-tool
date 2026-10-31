from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Organization, Department
from .serializers import OrganizationSerializer, DepartmentSerializer
from .permissions import IsOrgManager, IsDeptManagerOrStaff

class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Organization.objects.all()
        # Return organizations where user is manager or staff member
        return Organization.objects.filter(Q(manager=user) | Q(staffs=user)).distinct()

    def get_permissions(self):
        if self.action in ['create']:
            return [permissions.IsAuthenticated()]
        if self.action in ['update', 'partial_update', 'destroy', 'assign_staff']:
            return [IsOrgManager()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='assign-staff')
    def assign_staff(self, request, pk=None):
        org = self.get_object()
        user_ids = request.data.get('user_ids', [])
        department_id = request.data.get('department_id')

        org.staffs.add(*user_ids)
        
        # Assignment logic: if specific department provided, assign there; otherwise default
        if department_id:
            dept = org.departments.filter(id=department_id).first()
            if dept:
                dept.staffs.add(*user_ids)
        else:
            default_dept = org.departments.filter(is_default=True).first()
            if default_dept:
                default_dept.staffs.add(*user_ids)

        return Response({'status': 'Staff assigned successfully'}, status=status.HTTP_200_OK)

class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        org_id = self.request.query_params.get('organization')
        qs = Department.objects.all()
        if org_id:
            qs = qs.filter(organization_id=org_id)

        if user.is_superuser:
            return qs

        # Org manager sees all depts of their org
        # Dept manager sees their managed dept
        # Staff sees only assigned departments
        return qs.filter(
            Q(organization__manager=user) |
            Q(department_manager=user) |
            Q(staffs=user)
        ).distinct()

    def get_permissions(self):
        if self.action in ['destroy']:
            return [IsOrgManager()]
        if self.action in ['update', 'partial_update']:
            return [IsDeptManagerOrStaff()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        org = serializer.validated_data['organization']
        if org.manager != self.request.user and not self.request.user.is_superuser:
            raise permissions.PermissionDenied("Only organization managers can create departments.")
        serializer.save()
