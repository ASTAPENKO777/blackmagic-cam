import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "/tmp/purchases.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                token             TEXT UNIQUE NOT NULL,
                device_slug       TEXT NOT NULL,
                stripe_session_id TEXT UNIQUE NOT NULL,
                created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    TEXT UNIQUE NOT NULL,
                email       TEXT NOT NULL,
                device_slug TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def save_purchase(token: str, device_slug: str, order_ref: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO purchases (token, device_slug, stripe_session_id) VALUES (?, ?, ?)",
            (token, device_slug, order_ref),
        )
        conn.commit()


def get_purchase_by_token(token: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM purchases WHERE token = ?", (token,)
        ).fetchone()
    return dict(row) if row else None


def get_purchase_by_session(order_ref: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM purchases WHERE stripe_session_id = ?", (order_ref,)
        ).fetchone()
    return dict(row) if row else None


def save_pending_order(order_id: str, email: str, device_slug: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO pending_orders (order_id, email, device_slug) VALUES (?, ?, ?)",
            (order_id, email, device_slug),
        )
        conn.commit()


def get_pending_order(order_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM pending_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    return dict(row) if row else None


def purchase_exists_for_session(order_ref: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM purchases WHERE stripe_session_id = ?", (order_ref,)
        ).fetchone()
    return row is not None
