from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class DepartmentMinimalSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class UserMeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name", read_only=True)
    department = DepartmentMinimalSerializer(read_only=True)
    department_id = serializers.IntegerField(source="department.id", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "name",
            "first_name",
            "last_name",
            "role",
            "role_label",
            "employee_id",
            "department",
            "department_id",
            "department_name",
            "phone",
            "is_staff",
            "is_superuser",
        ]
        read_only_fields = fields


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends JWT token generation to include custom claims matching the KSPG Cockpit SSO contract.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Standard claims from MODULE_INTEGRATION_SPEC.md
        token["username"] = user.username
        token["email"] = user.email or ""
        token["role"] = user.role
        token["role_category"] = user.role.lower()
        token["employee_id"] = user.employee_id or ""
        token["department_code"] = user.department.code if user.department else ""
        token["is_superadmin"] = user.is_superuser

        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserMeSerializer(self.user).data
        return data
