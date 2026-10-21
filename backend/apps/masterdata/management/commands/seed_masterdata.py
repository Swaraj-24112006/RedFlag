from django.core.management.base import BaseCommand

from apps.masterdata.models import Department, Line, Plant, Station


class Command(BaseCommand):
    help = "Seeds standard master data (Departments, Plants, Lines, Stations) for KSPG SFC/RedFlag"

    def handle(self, *args, **options):
        self.stdout.write("Seeding Master Data...")

        # 1. Departments
        departments_data = [
            {"code": "PROD", "name": "Production", "is_internal": True},
            {"code": "QA", "name": "Quality", "is_internal": True},
            {"code": "MAINT", "name": "Maintenance", "is_internal": True},
            {"code": "TOOL", "name": "Tooling & Die", "is_internal": True},
            {"code": "EHS", "name": "Safety & EHS", "is_internal": True},
            {"code": "LOG", "name": "Logistics & Stores", "is_internal": True},
            {"code": "ENG", "name": "Engineering", "is_internal": True},
            {"code": "SUPP", "name": "Supplier / Inward", "is_internal": False},
        ]

        dept_objs = {}
        for d in departments_data:
            dept, created = Department.objects.update_or_create(
                code=d["code"],
                defaults={"name": d["name"], "is_internal": d["is_internal"], "is_active": True},
            )
            dept_objs[d["code"]] = dept
            self.stdout.write(f"  {'Created' if created else 'Updated'} Department: {dept.name} ({dept.code})")

        # 2. Plants
        plants_data = [
            {"code": "MF1", "name": "MF1 (Assembly & Testing)"},
            {"code": "MF2", "name": "MF2 (Machining & CNC)"},
            {"code": "MF3", "name": "MF3 (Moulding & Tooling)"},
        ]

        plant_objs = {}
        for p in plants_data:
            plant, created = Plant.objects.update_or_create(
                code=p["code"],
                defaults={"name": p["name"], "is_active": True},
            )
            plant_objs[p["code"]] = plant
            self.stdout.write(f"  {'Created' if created else 'Updated'} Plant: {plant.name} ({plant.code})")

        # 3. Lines & Stations
        lines_and_stations = [
            {
                "plant": "MF1",
                "code": "MF1-L1",
                "name": "Vacuum Pump Assembly",
                "stations": [
                    {"code": "ST-01", "name": "Rotor & Vane Press Sub-Assembly"},
                    {"code": "ST-02", "name": "Housing Fastening & Gasket Fitment"},
                    {"code": "ST-03", "name": "Pneumatic Final Leak Test Bench"},
                ],
            },
            {
                "plant": "MF1",
                "code": "MF1-L2",
                "name": "EGR Valve Assembly Line",
                "stations": [
                    {"code": "ST-01", "name": "Actuator Fitting & Screw Torquing"},
                    {"code": "ST-02", "name": "Sensor Calibration & Resistance Test"},
                    {"code": "ST-03", "name": "Optical Vision Inspection & Packing"},
                ],
            },
            {
                "plant": "MF2",
                "code": "MF2-L1",
                "name": "CNC Housing Machining",
                "stations": [
                    {"code": "ST-01", "name": "Horizontal CNC Rough Boring"},
                    {"code": "ST-02", "name": "Finish Facing & Thread Tapping"},
                    {"code": "ST-03", "name": "Automated CMM Quality Check"},
                ],
            },
            {
                "plant": "MF2",
                "code": "MF2-L2",
                "name": "Rotary Grinding Line",
                "stations": [
                    {"code": "ST-01", "name": "Rotary Surface Grinder Station #2"},
                    {"code": "ST-02", "name": "De-burring & Washing Bath"},
                ],
            },
            {
                "plant": "MF3",
                "code": "MF3-L1",
                "name": "Plastic Injection Moulding",
                "stations": [
                    {"code": "ST-01", "name": "Mould Clamping & Polymer Injection"},
                    {"code": "ST-02", "name": "Degating & Cooling Conveyor"},
                ],
            },
        ]

        for item in lines_and_stations:
            plant = plant_objs[item["plant"]]
            line, _ = Line.objects.update_or_create(
                plant=plant,
                code=item["code"],
                defaults={"name": item["name"], "is_active": True},
            )
            self.stdout.write(f"  Line: {line.plant.code} - {line.name}")

            for s in item["stations"]:
                st, _ = Station.objects.update_or_create(
                    line=line,
                    code=s["code"],
                    defaults={"name": s["name"], "is_active": True},
                )
                self.stdout.write(f"    Station: {st.code} ({st.name})")

        self.stdout.write(self.style.SUCCESS("[OK] Master data seeding complete."))
