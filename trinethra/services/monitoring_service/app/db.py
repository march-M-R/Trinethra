from __future__ import annotations

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_conn():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(db_url)
def db_healthcheck():
    try:
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        finally:
            conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}