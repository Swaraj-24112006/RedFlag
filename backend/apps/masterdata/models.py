from django.db import models


class Department(models.Model):
    code = models.CharField(max_length=50, unique=True, help_text="Short unique code (e.g. PROD, QA)")
    name = models.CharField(max_length=150, help_text="Department display name")
    is_active = models.BooleanField(default=True)
    is_internal = models.BooleanField(
        default=True,
        help_text="True for plant internal departments; False for external target-only entities like Supplier/Inward"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Plant(models.Model):
    code = models.CharField(max_length=50, unique=True, help_text="Plant/Minifactory code, e.g. MF1")
    name = models.CharField(max_length=150, help_text="Full plant title")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Line(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="lines")
    code = models.CharField(max_length=50, help_text="Line code, e.g. L-01")
    name = models.CharField(max_length=150, help_text="Line descriptive name")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["plant__code", "name"]
        unique_together = [["plant", "code"]]

    def __str__(self):
        return f"{self.plant.code} / {self.name}"


class Station(models.Model):
    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name="stations")
    code = models.CharField(max_length=50, help_text="Station code, e.g. ST-01")
    name = models.CharField(max_length=150, help_text="Station descriptive name")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["line__name", "name"]
        unique_together = [["line", "code"]]

    def __str__(self):
        return f"{self.line.name} / {self.name}"
