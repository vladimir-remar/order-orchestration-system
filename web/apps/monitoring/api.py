from django.http import JsonResponse
from django.db import connection

def health_view(_request):
    db_ok = False
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1;")
        db_ok = True
    except Exception:
        db_ok = False

    ok = db_ok
    code = 200 if ok else 503
    return JsonResponse(
        {"ok": ok, "components": {"db": {"ok": db_ok}}},
        status=code,
    )
