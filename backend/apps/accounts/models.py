from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    OPERATOR = "OPERATOR", "Operator"
    SUPERVISOR = "SUPERVISOR", "Supervisor"
    DEPT_LEAD = "DEPT_LEAD", "Department Lead"
    QA_INSPECTOR = "QA_INSPECTOR", "QA Inspector"
    QA_CUSTODIAN = "QA_CUSTODIAN", "QA Custodian"
    PLANT_HEAD = "PLANT_HEAD", "Plant Head"
    ADMIN = "ADMIN", "Administrator"


class User(AbstractUser):
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    department = models.ForeignKey(
        "masterdata.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    phone = models.CharField(max_length=20, blank=True, default="")
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.OPERATOR,
    )

    class Meta:
        ordering = ["username"]

    def __str__(self):
        full = self.get_full_name()
        return f"{full or self.username} ({self.role})"

    @property
    def full_name(self):
        return self.get_full_name() or self.username
