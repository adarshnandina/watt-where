from asgiref.sync import sync_to_async
from django.db import connection
from django.http import JsonResponse

from .models import DataMeta, EnergyUnit, Municipality


def _health_sync() -> dict:
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
    meta = {m.key: m.value for m in DataMeta.objects.all()}
    counts = {
        "municipalities": Municipality.objects.count(),
        "units": EnergyUnit.objects.count(),
    }
    return {"status": "ok", "data": {"snapshot": meta, "counts": counts}}


async def health(request):
    """GET /api/health: DB connectivity plus data freshness (snapshot date, row counts)."""
    try:
        payload = await sync_to_async(_health_sync)()
        return JsonResponse(payload)
    except Exception:  # never leak internals
        return JsonResponse({"status": "error", "message": "database unavailable"}, status=503)
