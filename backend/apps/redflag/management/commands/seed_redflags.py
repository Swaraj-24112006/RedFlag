import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.masterdata.models import Department, Line, Plant, Station
from apps.redflag.models import (
    Containment,
    ContainmentStatus,
    QaCustodianStatus,
    RedFlag,
    RedFlagCounter,
    RedFlagStatus,
)


class Command(BaseCommand):
    help = "Seeds red flags for stress testing the Master Tracker, KPIs, and search"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=5000,
            help="Number of red flags to seed (default: 5000)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        self.stdout.write(f"Seeding {count} Red Flags...")

        departments = list(Department.objects.all())
        plants = list(Plant.objects.all())
        lines = list(Line.objects.all())
        stations = list(Station.objects.all())
        users = list(User.objects.all())

        if not departments or not plants:
            self.stdout.write(self.style.ERROR("Master data missing. Run seed_masterdata first."))
            return

        user = users[0] if users else None

        # Determine year
        now = timezone.now()
        year = now.year

        counter, _ = RedFlagCounter.objects.get_or_create(year=year, defaults={"last_number": 0})
        start_num = counter.last_number + 1

        severities = ["CRITICAL", "MAJOR", "MINOR"]
        categories = ["Man", "Machine", "Material", "Method", "Measurement", "Environment"]
        rf_types = ["Quality", "Safety", "Delivery", "Cost", "Morale"]
        statuses = [
            RedFlagStatus.OPEN,
            RedFlagStatus.CONTAINED,
            RedFlagStatus.IN_PROGRESS,
            RedFlagStatus.UNDER_SUSTENANCE,
            RedFlagStatus.CLOSED,
        ]

        flags_to_create = []
        batch_size = 1000

        for i in range(count):
            num = start_num + i
            rf_no = f"RF-{year}-{num:04d}"
            status = random.choice(statuses)
            severity = random.choice(severities)
            category = random.choice(categories)
            rf_type = random.choice(rf_types)
            plant = random.choice(plants)
            orig_dept = random.choice(departments)
            target_dept = random.choice(departments)
            line = random.choice(lines) if lines else None
            station = random.choice(stations) if stations else None

            days_ago = random.randint(0, 90)
            hours_ago = random.randint(0, 23)
            raised_at = now - timedelta(days=days_ago, hours=hours_ago)

            qa_custodian_status = QaCustodianStatus.REVIEW_PENDING
            if status == RedFlagStatus.CLOSED:
                qa_custodian_status = QaCustodianStatus.CLOSURE_APPROVED
            elif status in (RedFlagStatus.CONTAINED, RedFlagStatus.IN_PROGRESS):
                qa_custodian_status = random.choice([
                    QaCustodianStatus.CONTAINMENT_VERIFIED,
                    QaCustodianStatus.REVIEW_PENDING,
                ])

            sustenance_achieved = (status == RedFlagStatus.CLOSED)
            sustenance_start_date = (raised_at + timedelta(days=5)).date() if status in (RedFlagStatus.UNDER_SUSTENANCE, RedFlagStatus.CLOSED) else None

            flag = RedFlag(
                rf_no=rf_no,
                raised_at=raised_at,
                raised_by=user,
                raised_by_name="Operator Sharma" if not user else f"{user.first_name} {user.last_name}",
                raised_by_department=orig_dept,
                target_department=target_dept,
                target_person="Supervisor Patil",
                qa_custodian=user,
                qa_custodian_status=qa_custodian_status,
                plant=plant,
                line=line,
                line_name=line.name if line else "Line 1",
                station=station,
                station_name=station.name if station else "Station 1",
                model_name="VP-200X",
                red_flag_type=rf_type,
                red_flag_subtype="Defect",
                severity=severity,
                category_5m=category,
                repetitive_occurrence=(random.random() < 0.2),
                description=f"Defect observed on batch #{num}: burr on rotor surface causing torque failure during QA audit.",
                sustenance_start_date=sustenance_start_date,
                sustenance_achieved=sustenance_achieved,
                status=status,
                version=1,
            )
            flags_to_create.append(flag)

            if len(flags_to_create) >= batch_size:
                RedFlag.objects.bulk_create(flags_to_create)
                self.stdout.write(f"  Inserted {i + 1}/{count} flags...")
                flags_to_create = []

        if flags_to_create:
            RedFlag.objects.bulk_create(flags_to_create)

        counter.last_number = start_num + count - 1
        counter.save()

        # Seed containments for all created flags
        self.stdout.write("Seeding Containment records...")
        created_flags = RedFlag.objects.filter(containment__isnull=True)
        containments = []
        for flag in created_flags.iterator(chunk_size=1000):
            is_contained = flag.status in (RedFlagStatus.CONTAINED, RedFlagStatus.IN_PROGRESS, RedFlagStatus.UNDER_SUSTENANCE, RedFlagStatus.CLOSED)
            qty = random.randint(10, 200) if is_contained else 0
            contained_at = flag.raised_at + timedelta(minutes=random.randint(20, 180)) if is_contained else None
            verified_at = contained_at + timedelta(minutes=random.randint(10, 60)) if (is_contained and flag.qa_custodian_status == QaCustodianStatus.CONTAINMENT_VERIFIED) else None

            c = Containment(
                red_flag=flag,
                qty_quarantined=qty,
                action="Quarantined WIP bin and placed red tags." if is_contained else "",
                red_tag_no=f"RT-{flag.id:04d}" if is_contained else "",
                contained_at=contained_at,
                verified_by=user if verified_at else None,
                verified_at=verified_at,
                status=ContainmentStatus.VERIFIED if verified_at else (ContainmentStatus.CONTAINED if is_contained else ContainmentStatus.PENDING),
            )
            containments.append(c)
            if len(containments) >= batch_size:
                Containment.objects.bulk_create(containments)
                containments = []

        if containments:
            Containment.objects.bulk_create(containments)

        self.stdout.write(self.style.SUCCESS(f"[OK] Successfully seeded {count} Red Flags with containments."))
