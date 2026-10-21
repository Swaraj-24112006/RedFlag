from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CustomTokenObtainPairSerializer, UserMeSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """Obtain JWT access and refresh token pair with custom claims and user profile payload."""
    serializer_class = CustomTokenObtainPairSerializer


class MeView(APIView):
    """
    Returns the authenticated user's profile, role, employee_id, and department.
    Used by frontend to replace hardcoded users and persona props.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Current Authenticated User",
        description="Returns user information, role enum, department, and employee ID for the active JWT session.",
        responses={200: UserMeSerializer},
    )
    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data)
