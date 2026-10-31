from rest_framework.routers import DefaultRouter
from .views import OrganizationViewSet, DepartmentViewSet

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'', OrganizationViewSet, basename='organization')

urlpatterns = router.urls
