from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from cases.models import Case
from cases.views import case_status_breakdown, visible_firs_for


def _parse_date_range(request, default_days=90):
    """
    Every report shares the same "pick a date range via two GET date
    inputs" UX -- one parser, reused by all four views, with graceful
    fallback rather than a 500 if someone hand-edits the URL with a
    malformed date.
    """
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.GET["start"]) if request.GET.get("start") else today - timedelta(days=default_days)
    except ValueError:
        start = today - timedelta(days=default_days)
    try:
        end = date.fromisoformat(request.GET["end"]) if request.GET.get("end") else today
    except ValueError:
        end = today
    return start, end


@login_required
def reports_index(request):
    return render(request, "reports/index.html")


@login_required
def crime_statistics(request):
    start, end = _parse_date_range(request)
    visible_firs = visible_firs_for(request.user).filter(date_filed__date__gte=start, date_filed__date__lte=end)
    by_section = (
        visible_firs.values("sections_of_law")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    return render(request, "reports/crime_statistics.html", {
        "start": start, "end": end, "by_section": by_section, "total": visible_firs.count(),
    })


@login_required
def monthly_report(request):
    start, end = _parse_date_range(request, default_days=365)
    visible_firs = visible_firs_for(request.user).filter(date_filed__date__gte=start, date_filed__date__lte=end)
    rows = list(
        visible_firs.annotate(month=TruncMonth("date_filed"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    max_count = max((r["count"] for r in rows), default=0) or 1
    for row in rows:
        row["bar_width_pct"] = round(100 * row["count"] / max_count / 5) * 5
    return render(request, "reports/monthly_report.html", {
        "start": start, "end": end, "rows": rows, "total": visible_firs.count(),
    })


@login_required
def officer_report(request):
    start, end = _parse_date_range(request)
    visible_firs = visible_firs_for(request.user).filter(date_filed__date__gte=start, date_filed__date__lte=end)
    cases = Case.objects.filter(fir__in=visible_firs, assigned_officer__isnull=False)
    rows = (
        cases.values(
            "assigned_officer__first_name", "assigned_officer__last_name",
            "assigned_officer__officer_profile__rank", "assigned_officer__officer_profile__station",
        )
        .annotate(case_count=Count("id"))
        .order_by("-case_count")
    )
    return render(request, "reports/officer_report.html", {
        "start": start, "end": end, "rows": rows, "total_assigned": cases.count(),
    })


@login_required
def case_report(request):
    start, end = _parse_date_range(request)
    visible_firs = visible_firs_for(request.user).filter(date_filed__date__gte=start, date_filed__date__lte=end)
    cases = Case.objects.filter(fir__in=visible_firs)
    status_counts = case_status_breakdown(cases)
    return render(request, "reports/case_report.html", {
        "start": start, "end": end, "status_counts": status_counts, "total": cases.count(),
    })
