import django_filters
from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from .models import Attachment, AttachmentKind, RedFlag, RedFlagStatus

CONTAINMENT_SLA_MINUTES_THRESHOLD = 120  # 2 Hours SLA


def calculate_containment_sla(flag: RedFlag) -> dict:
    """
    Computes real SLA containment minutes and breach status.
    - containment_sla_minutes: (contained_at - raised_at) in minutes, or None if still uncontained.
    - containment_sla_breached: true if minutes > 120 or if still OPEN and (now - raised_at) > 120 min.
    """
    contained_at = getattr(flag, "containment", None) and flag.containment.contained_at
    raised_at = flag.raised_at

    if contained_at:
        diff_minutes = max(0, int((contained_at - raised_at).total_seconds() / 60))
        return {
            "containment_sla_minutes": diff_minutes,
            "containment_sla_breached": diff_minutes > CONTAINMENT_SLA_MINUTES_THRESHOLD,
        }
    else:
        elapsed_minutes = max(0, int((timezone.now() - raised_at).total_seconds() / 60))
        is_breached = flag.status == RedFlagStatus.OPEN and elapsed_minutes > CONTAINMENT_SLA_MINUTES_THRESHOLD
        return {
            "containment_sla_minutes": None,
            "containment_sla_breached": is_breached,
        }


def get_base_flags_queryset():
    """
    Returns an optimized base queryset with all foreign keys and active before-attachment prefetched.
    Prevents N+1 database queries. Always ordered by latest to oldest raised_at dates.
    """
    return (
        RedFlag.objects.select_related(
            "raised_by",
            "raised_by_department",
            "target_department",
            "plant",
            "qa_custodian",
            "containment",
            "containment__verified_by",
        )
        .prefetch_related(
            Prefetch(
                "attachments",
                queryset=Attachment.objects.filter(kind=AttachmentKind.EVIDENCE_BEFORE, is_current=True),
                to_attr="current_evidence",
            )
        )
        .filter(is_void=False)
        .order_by("-raised_at", "-id")
    )


class RedFlagFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    status = django_filters.CharFilter(method="filter_status")
    target_department = django_filters.CharFilter(method="filter_target_department")
    raised_by_department = django_filters.CharFilter(method="filter_raised_by_department")
    category_5m = django_filters.CharFilter(field_name="category_5m", lookup_expr="iexact")
    severity = django_filters.CharFilter(field_name="severity", lookup_expr="iexact")
    plant = django_filters.CharFilter(field_name="plant__code", lookup_expr="iexact")
    raised_from = django_filters.DateFilter(field_name="raised_at", lookup_expr="date__gte")
    raised_to = django_filters.DateFilter(field_name="raised_at", lookup_expr="date__lte")
    sla_breached = django_filters.BooleanFilter(method="filter_sla_breached")

    ordering = django_filters.OrderingFilter(
        fields=(
            ("raised_at", "raised_at"),
            ("severity", "severity"),
            ("status", "status"),
            ("rf_no", "rf_no"),
        ),
    )

    class Meta:
        model = RedFlag
        fields = [
            "search",
            "status",
            "target_department",
            "raised_by_department",
            "category_5m",
            "severity",
            "plant",
            "raised_from",
            "raised_to",
            "sla_breached",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = value.strip()
        return queryset.filter(
            Q(rf_no__icontains=val)
            | Q(description__icontains=val)
            | Q(raised_by_name__icontains=val)
            | Q(target_person__icontains=val)
            | Q(line_name__icontains=val)
            | Q(station_name__icontains=val)
            | Q(model_name__icontains=val)
        )

    def filter_status(self, queryset, name, value):
        if not value or value.lower() == "all":
            return queryset
        # Normalizes status string (e.g. 'under-sustenance' -> 'UNDER_SUSTENANCE')
        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        return queryset.filter(status=normalized)

    def filter_target_department(self, queryset, name, value):
        if not value or value.lower() == "all":
            return queryset
        val = value.strip()
        if val.isdigit():
            return queryset.filter(target_department_id=int(val))
        return queryset.filter(target_department__code__iexact=val)

    def filter_raised_by_department(self, queryset, name, value):
        if not value or value.lower() == "all":
            return queryset
        val = value.strip()
        if val.isdigit():
            return queryset.filter(raised_by_department_id=int(val))
        return queryset.filter(raised_by_department__code__iexact=val)

    def filter_sla_breached(self, queryset, name, value):
        if value is None:
            return queryset
        threshold_time = timezone.now() - timezone.timedelta(minutes=CONTAINMENT_SLA_MINUTES_THRESHOLD)
        breached_query = (
            Q(containment__contained_at__isnull=False, containment__contained_at__gt=timezone.F("raised_at") + timezone.timedelta(minutes=CONTAINMENT_SLA_MINUTES_THRESHOLD))
            | Q(status=RedFlagStatus.OPEN, containment__contained_at__isnull=True, raised_at__lt=threshold_time)
        )
        return queryset.filter(breached_query) if value else queryset.exclude(breached_query)


def get_flags_summary(queryset, is_scoped: bool = False) -> dict:
    """
    Executes a single high-performance aggregation query to compute Master Tracker KPIs.
    If is_scoped is False (default), calculates totals across all flags in the system.
    """
    target_qs = queryset if is_scoped else RedFlag.objects.filter(is_void=False)

    counts = target_qs.aggregate(
        total_raised=Count("id"),
        open_count=Count("id", filter=Q(status=RedFlagStatus.OPEN)),
        contained_count=Count("id", filter=Q(status=RedFlagStatus.CONTAINED)),
        under_sustenance=Count("id", filter=Q(status=RedFlagStatus.UNDER_SUSTENANCE)),
        closed_sustained=Count("id", filter=Q(status=RedFlagStatus.CLOSED, sustenance_achieved=True)),
        qa_custodian_backlog=Count("id", filter=Q(qa_custodian_status="REVIEW_PENDING")),
    )

    open_action_needed = counts["open_count"] + counts["contained_count"]

    return {
        "total_raised": counts["total_raised"],
        "open_action_needed": open_action_needed,
        "contained_count": counts["contained_count"],
        "under_sustenance": counts["under_sustenance"],
        "closed_sustained": counts["closed_sustained"],
        "qa_custodian_backlog": counts["qa_custodian_backlog"],
    }
