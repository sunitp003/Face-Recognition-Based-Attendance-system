"""Request-scoped MySQL connection management."""
import os
from flask import g
from werkzeug.local import LocalProxy
import MySQLdb

# Request-scoped connections prevent concurrent requests sharing one connection.
def get_db():
    if "db" not in g:
        g.db = MySQLdb.connect(
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            db=os.environ.get("DB_NAME", "attendance_database1"),
            charset="utf8mb4",
        )
        g.db.autocommit(True)
    return g.db

def close_db(error=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()

app.teardown_appcontext(close_db)
conn = LocalProxy(get_db)
