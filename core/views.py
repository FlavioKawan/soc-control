from django.db import connection
from django.http import HttpResponse


def healthz(request):
    """Liveness/readiness probe for Docker/orchestrator healthchecks (see
    docker-compose.yml) - no auth, no permission check, must stay reachable
    even if every app-level thing is broken. Touches the database because a
    web worker that's up but can't reach Postgres isn't actually healthy."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok")
