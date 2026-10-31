from rest_framework import permissions

class CanManageDepartmentDocs(permissions.BasePermission):
    """
    Org Manager: Full control.
    Dept Manager: Full control over docs in their dept.
    Staff: Read-only access to view documents.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        org = obj.department.organization
        
        if user.is_superuser or org.manager == user or obj.department.department_manager == user:
            return True

        if request.method in permissions.SAFE_METHODS:
            return user in obj.department.staffs.all()

        return False
