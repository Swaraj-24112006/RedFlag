from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, LineViewSet, PlantViewSet, StationViewSet

app_name = "masterdata"

router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"plants", PlantViewSet, basename="plant")
router.register(r"lines", LineViewSet, basename="line")
router.register(r"stations", StationViewSet, basename="station")

urlpatterns = router.urls
