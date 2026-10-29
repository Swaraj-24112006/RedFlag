from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.health import HealthCheckView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Health Check (Used by gateway monitors & docker compose)
    path("api/health/", HealthCheckView.as_view(), name="health"),

    # Authentication & Profile (KSPG Cockpit SSO)
    path("api/auth/", include("apps.accounts.urls", namespace="accounts")),

    # Master Data
    path("api/masterdata/", include("apps.masterdata.urls", namespace="masterdata")),

    # RedFlag Domain Module (supports both /api/redflag/v1/ and /api/v1/redflag/)
    path("api/redflag/v1/", include("apps.redflag.urls", namespace="redflag")),
    path("api/v1/redflag/", include("apps.redflag.urls", namespace="redflag_v1")),

    # OpenAPI Schema & Swagger Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

