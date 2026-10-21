from datetime import datetime

from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .storage import check_minio_health


class HealthCheckView(APIView):
    """
    Health check endpoint that verifies operational status of PostgreSQL and MinIO.
    Accessible without authentication for gateway and orchestrator monitors.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Service Health Check",
        description="Verifies database connectivity and MinIO S3 bucket availability.",
        responses={200: dict, 503: dict},
    )
    def get(self, request):
        db_ok = False
        db_error = None
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                row = cursor.fetchone()
                db_ok = row is not None and row[0] == 1
        except Exception as e:
            db_error = str(e)

        minio_ok = check_minio_health()

        is_healthy = db_ok and minio_ok
        status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response(
            {
                "status": "healthy" if is_healthy else "degraded",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "database": {"status": "up" if db_ok else "down", "error": db_error},
                    "minio": {"status": "up" if minio_ok else "down"},
                },
            },
            status=status_code,
        )
