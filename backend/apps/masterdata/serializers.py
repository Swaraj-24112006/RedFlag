from rest_framework import serializers

from .models import Department, Line, Plant, Station


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name", "is_active", "is_internal"]


class PlantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plant
        fields = ["id", "code", "name", "is_active"]


class LineSerializer(serializers.ModelSerializer):
    plant_code = serializers.CharField(source="plant.code", read_only=True)
    plant_name = serializers.CharField(source="plant.name", read_only=True)

    class Meta:
        model = Line
        fields = ["id", "plant", "plant_code", "plant_name", "code", "name", "is_active"]


class StationSerializer(serializers.ModelSerializer):
    line_code = serializers.CharField(source="line.code", read_only=True)
    line_name = serializers.CharField(source="line.name", read_only=True)
    plant_id = serializers.IntegerField(source="line.plant.id", read_only=True)
    plant_code = serializers.CharField(source="line.plant.code", read_only=True)

    class Meta:
        model = Station
        fields = ["id", "line", "line_code", "line_name", "plant_id", "plant_code", "code", "name", "is_active"]
