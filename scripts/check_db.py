"""Docker コンテナ内から PostgreSQL への接続を確認するスクリプト.

Usage (from host):
    docker compose exec app python scripts/check_db.py
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 1

    print(f"Connecting to: {url.split('@')[-1]}")
    engine = create_engine(url)

    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
            db, user = conn.execute(
                text("SELECT current_database(), current_user")
            ).first()

            print("✓ Connected successfully")
            print(f"  PostgreSQL : {version}")
            print(f"  Database   : {db}")
            print(f"  User       : {user}")
            return 0

    except Exception as e:  # noqa: BLE001
        print(f"✗ Connection failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
