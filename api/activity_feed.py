"""/api/v1/activity-feed/ — surfaces harbor's Activity to Keel's /ops/ page.

Row 2 on Keel's /ops/ fans out across products to render the cross-product
system-events lane. Scoped to ``actor__isnull=True`` so user-action rows stay
on detail pages, not the ops surface. See keel/feed/activity_feed_example.py
for the rollout pattern.
"""
from __future__ import annotations

from datetime import datetime, timezone

from django.db.models import Q
from django.utils import timezone as dj_tz

from keel.core.utils import get_product_code
from keel.feed import activity_feed_view

from applications.activity_models import Activity


def _parse_iso(value, default):
    if not value:
        return default
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return default
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@activity_feed_view
def build_activity(request):
    now = dj_tz.now()
    window_start = _parse_iso(request.GET.get('window_start'), now)
    window_end = _parse_iso(request.GET.get('window_end'), now)
    q = (request.GET.get('q') or '').strip()
    verbs = [v for v in (request.GET.get('verbs') or '').split(',') if v]
    status = (request.GET.get('status') or 'any').strip().lower()
    try:
        limit = int(request.GET.get('limit') or 200)
    except (TypeError, ValueError):
        limit = 200
    limit = max(1, min(limit, 200))

    # Scope to system events — user-action rows belong on detail pages, not
    # the cross-product ops surface.
    qs = Activity.objects.select_related('actor').filter(
        created_at__gte=window_start, created_at__lte=window_end,
        actor__isnull=True,
    ).order_by('-created_at')

    # Filters applied BEFORE the cap so rare-verb / rare-status results
    # don't get silently truncated.
    if verbs:
        qs = qs.filter(verb__in=verbs)
    if status != 'any':
        qs = qs.filter(metadata__status=status)
    if q:
        qs = qs.filter(
            Q(source_label__icontains=q)
            | Q(verb__icontains=q)
            | Q(actor__username__icontains=q),
        )

    total = qs.count()
    rows = []
    for entry in qs[:limit]:
        rows.append({
            'id': str(entry.id),
            'timestamp': entry.created_at.isoformat(),
            'verb': entry.verb,
            'summary': entry.source_label or '',
            'status': (entry.metadata or {}).get('status', 'ok'),
            'actor_username': entry.actor.username if entry.actor_id else '',
            'target_type': entry.target_ct.model if entry.target_ct_id else '',
            'target_id': entry.target_id or '',
            'visibility': entry.visibility,
            'deep_link': entry.deep_link or '',
            'metadata': entry.metadata or {},
            'product': get_product_code(),
        })

    return {
        'items': rows,
        'total_in_window': total,
        'capped': total > limit,
        'window': [window_start.isoformat(), window_end.isoformat()],
        'fetched_at': dj_tz.now().isoformat(),
        'product': get_product_code(),
    }
