from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User
from apps.masterdata.models import Department


class Command(BaseCommand):
    help = "Seeds demo users with one user per role (OPERATOR, SUPERVISOR, DEPT_LEAD, QA_INSPECTOR, QA_CUSTODIAN, PLANT_HEAD, ADMIN)"

    def handle(self, *args, **options):
        self.stdout.write("Seeding Demo Users...")

        prod_dept = Department.objects.filter(code="PROD").first()
        qa_dept = Department.objects.filter(code="QA").first()

        users_data = [
            {
                "username": "operator",
                "email": "operator@kspg.local",
                "first_name": "Rahul",
                "last_name": "Sharma",
                "role": Role.OPERATOR,
                "department": prod_dept,
                "employee_id": "EMP-OP-001",
                "phone": "+91-9876543210",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": "supervisor",
                "email": "supervisor@kspg.local",
                "first_name": "Rajesh",
                "last_name": "Patil",
                "role": Role.SUPERVISOR,
                "department": prod_dept,
                "employee_id": "EMP-SUP-002",
                "phone": "+91-9876543211",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": "deptlead",
                "email": "deptlead@kspg.local",
                "first_name": "Vijay",
                "last_name": "Deshmukh",
                "role": Role.DEPT_LEAD,
                "department": prod_dept,
                "employee_id": "EMP-DL-003",
                "phone": "+91-9876543212",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": "qainspector",
                "email": "qainspector@kspg.local",
                "first_name": "Sunita",
                "last_name": "Rao",
                "role": Role.QA_INSPECTOR,
                "department": qa_dept,
                "employee_id": "EMP-QA-004",
                "phone": "+91-9876543213",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "username": "qacustodian",
                "email": "qacustodian@kspg.local",
                "first_name": "Amit",
                "last_name": "Mehta",
                "role": Role.QA_CUSTODIAN,
                "department": qa_dept,
                "employee_id": "EMP-QC-005",
                "phone": "+91-9876543214",
                "is_staff": True,
                "is_superuser": False,
            },
            {
                "username": "planthead",
                "email": "planthead@kspg.local",
                "first_name": "Vikram",
                "last_name": "Sen",
                "role": Role.PLANT_HEAD,
                "department": prod_dept,
                "employee_id": "EMP-PH-006",
                "phone": "+91-9876543215",
                "is_staff": True,
                "is_superuser": False,
            },
            {
                "username": "admin",
                "email": "admin@kspg.local",
                "first_name": "System",
                "last_name": "Administrator",
                "role": Role.ADMIN,
                "department": qa_dept,
                "employee_id": "EMP-ADM-007",
                "phone": "+91-9876543216",
                "is_staff": True,
                "is_superuser": True,
            },
        ]

        for u_data in users_data:
            username = u_data["username"]
            user, created = User.objects.get_or_create(username=username)
            user.email = u_data["email"]
            user.first_name = u_data["first_name"]
            user.last_name = u_data["last_name"]
            user.role = u_data["role"]
            user.department = u_data["department"]
            user.employee_id = u_data["employee_id"]
            user.phone = u_data["phone"]
            user.is_staff = u_data["is_staff"]
            user.is_superuser = u_data["is_superuser"]
            user.set_password("demo12345")
            user.save()
            self.stdout.write(f"  {'Created' if created else 'Updated'} User: {user.username} ({user.role})")

        self.stdout.write(self.style.SUCCESS("[OK] Demo users seeding complete. Password for all: demo12345"))
