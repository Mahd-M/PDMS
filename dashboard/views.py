from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from cases.models import Case
from cases.views import visible_firs_for


@login_required
def home(request):
    """
    A server-rendered dashboard: every number and every bar in the
    chart is computed in Python and sent down as plain HTML/SVG. There
    is no charting library, no fetch call, and no client-side redraw --
    the whole page is disposable and regenerated on every request.
    """
    visible_firs = visible_firs_for(request.user)
    cases = Case.objects.filter(fir__in=visible_firs)

    status_counts = []
    total = cases.count() or 1
    for value, label in Case.Status.choices:
        count = cases.filter(status=value).count()
        status_counts.append({
            "label": label,
            "count": count,
            "bar_width_pct": round(100 * count / total / 5) * 5,
        })

    return render(request, "dashboard/home.html", {
        "total_cases": cases.count(),
        "total_firs": visible_firs.count(),
        "status_counts": status_counts,
    })
