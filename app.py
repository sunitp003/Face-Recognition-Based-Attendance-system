"""Application factory and backwards-compatible WSGI entry point."""
import logging
import os
import secrets

from dotenv import load_dotenv

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(APP_ROOT, ".env"))

from flask import Flask, redirect, session, url_for

from database import close_db, conn, get_db
import modelTrain
import recognition
from services.file_storage import unzip_file
from services.pending_attendance import _clear_pending_attendance, _load_pending_attendance, _store_pending_attendance
from services.security import role_required

from services.security import register_security
from routes.auth import bp as auth_bp
from routes.admin import bp as admin_bp
from routes.student import bp as student_bp
from routes.faculty import bp as faculty_bp
from routes.pages import bp as pages_bp


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0").lower() in {"1", "true", "yes"},
    )
    is_production = (
        os.environ.get("FLASK_ENV", "").lower() == "production"
        or os.environ.get("APP_ENV", "").lower() == "production"
    )
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key and is_production:
        raise RuntimeError("SECRET_KEY must be configured in production")
    if not secret_key:
        logging.warning("SECRET_KEY is not configured; local sessions reset after restart")
        secret_key = secrets.token_hex(32)
    app.secret_key = secret_key

    if is_production:
        if len(secret_key) < 32:
            raise RuntimeError("Production SECRET_KEY must contain at least 32 characters")
        if not os.environ.get("DB_PASSWORD") or os.environ.get("DB_USER", "root").lower() == "root":
            raise RuntimeError("Configure a dedicated DB_USER and non-empty DB_PASSWORD in production")
        if not app.config["SESSION_COOKIE_SECURE"]:
            raise RuntimeError("Set COOKIE_SECURE=1 when running behind HTTPS in production")

    if config:
        app.config.update(config)

    app.teardown_appcontext(close_db)
    register_security(app)

    @app.after_request
    def set_response_headers(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    blueprints = (auth_bp, admin_bp, student_bp, faculty_bp, pages_bp)
    for blueprint in blueprints:
        app.register_blueprint(blueprint)

    # Preserve legacy endpoint names used by templates, redirects, and integrations.
    for rule in list(app.url_map.iter_rules()):
        if "." not in rule.endpoint or rule.endpoint.startswith("static."):
            continue
        legacy_endpoint = rule.endpoint.split(".", 1)[1]
        if legacy_endpoint in app.view_functions:
            continue
        app.add_url_rule(
            rule.rule,
            endpoint=legacy_endpoint,
            view_func=app.view_functions[rule.endpoint],
            defaults=rule.defaults,
            methods=sorted(rule.methods - {"HEAD", "OPTIONS"}),
            provide_automatic_options=("OPTIONS" in rule.methods),
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False)
