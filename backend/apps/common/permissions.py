from rest_framework.permissions import BasePermission

from apps.accounts.models import Role


class HasRole(BasePermission):
    """Factory-like permission class checking if the user has any of the required roles."""
    allowed_roles = []

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.role == Role.ADMIN:
            return True
        return request.user.role in self.allowed_roles


class IsQACustodian(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == Role.QA_CUSTODIAN or request.user.role == Role.ADMIN or request.user.is_superuser)
        )


class IsSupervisorOrAbove(BasePermission):
    def has_permission(self, request, view):
        allowed = {Role.SUPERVISOR, Role.DEPT_LEAD, Role.QA_CUSTODIAN, Role.PLANT_HEAD, Role.ADMIN}
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role in allowed or request.user.is_superuser)
        )
