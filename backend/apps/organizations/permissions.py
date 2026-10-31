from rest_framework import permissions

class IsOrgManager(permissions.BasePermission):
    """Permission check for Organization Manager or Superuser."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        if hasattr(obj, 'manager'):
            return obj.manager == request.user
        if hasattr(obj, 'organization'):
            return obj.organization.manager == request.user
        return False

class IsDeptManagerOrStaff(permissions.BasePermission):
    """
    Managers can do everything.
    Department managers can view and manage their department.
    Staff can only view (read-only).
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or obj.organization.manager == user:
            return True
        
        # Department Manager has full manage rights inside the department
        if obj.department_manager == user:
            return True

        # Staff can only view their own department
        if request.method in permissions.SAFE_METHODS:
            return user in obj.staffs.all()

        return False
