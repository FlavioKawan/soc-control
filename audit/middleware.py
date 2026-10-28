import threading

_state = threading.local()


def get_current_user():
    """
    Read by audit/signals.py, which has no access to the request. Model
    signals fire inside the save()/delete() call itself, so the only way to
    know "who did this" is to stash the user somewhere signals can reach -
    a thread-local set by this middleware for the duration of the request.
    """
    return getattr(_state, "user", None)


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        _state.user = user if user is not None and user.is_authenticated else None
        try:
            return self.get_response(request)
        finally:
            _state.user = None
