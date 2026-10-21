import factory

from apps.accounts.models import Role, User
from apps.masterdata.models import Department, Line, Plant, Station


class DepartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Department
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"DEPT_{n}")
    name = factory.Sequence(lambda n: f"Department {n}")
    is_active = True
    is_internal = True


class PlantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Plant
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"MF{n}")
    name = factory.Sequence(lambda n: f"Plant MF{n}")
    is_active = True


class LineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Line

    plant = factory.SubFactory(PlantFactory)
    code = factory.Sequence(lambda n: f"L-{n}")
    name = factory.Sequence(lambda n: f"Line {n}")
    is_active = True


class StationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Station

    line = factory.SubFactory(LineFactory)
    code = factory.Sequence(lambda n: f"ST-{n}")
    name = factory.Sequence(lambda n: f"Station {n}")
    is_active = True


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@kspg.local")
    first_name = "Test"
    last_name = "User"
    role = Role.OPERATOR
    department = factory.SubFactory(DepartmentFactory)
    employee_id = factory.Sequence(lambda n: f"EMP-{n:04d}")
    phone = "+91-9999999999"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "password123")
        user = super()._create(model_class, *args, **kwargs)
        user.set_password(password)
        user.save()
        return user
