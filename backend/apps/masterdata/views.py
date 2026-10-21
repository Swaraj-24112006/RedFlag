from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Department, Line, Plant, Station
from .serializers import DepartmentSerializer, LineSerializer, PlantSerializer, StationSerializer


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve plant departments.
    Supports filtering by active status and internal/external flag.
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active", "is_internal"]
    search_fields = ["code", "name"]
    ordering_fields = ["name", "code"]
    pagination_class = None  # Master data is small and typically displayed in full dropdowns


class PlantViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve production plants / minifactories.
    """
    queryset = Plant.objects.all()
    serializer_class = PlantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_active"]
    search_fields = ["code", "name"]
    pagination_class = None


class LineViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve manufacturing lines.
    Supports filtering by plant: GET /api/masterdata/lines/?plant=<plant_id>
    """
    queryset = Line.objects.select_related("plant").all()
    serializer_class = LineSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["plant", "is_active"]
    search_fields = ["code", "name", "plant__code", "plant__name"]
    pagination_class = None


class StationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve stations.
    Supports filtering by line: GET /api/masterdata/stations/?line=<line_id>
    """
    queryset = Station.objects.select_related("line", "line__plant").all()
    serializer_class = StationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["line", "line__plant", "is_active"]
    search_fields = ["code", "name", "line__name"]
    pagination_class = None
