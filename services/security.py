"""Session role checks and CSRF protection for Flask routes."""
import hmac
import secrets
from functools import wraps
from flask import abort, request, session, url_for, redirect

def role_required(*allowed_roles):
    """Protect routes using the authenticated role in the session."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") not in allowed_roles or "user" not in session:
                return redirect(url_for("index"))
            if session.get("must_change_password") and request.endpoint not in {"change_password", "auth.change_password"}:
                return redirect(url_for("change_password"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token

def protect_post_requests():
    if request.method == "POST":
        expected = session.get("_csrf_token", "")
        supplied = request.form.get("_csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
            abort(400, description="Invalid or missing CSRF token")


def register_security(app):
    app.context_processor(lambda: {"csrf_token": csrf_token})
    app.before_request(protect_post_requests)
