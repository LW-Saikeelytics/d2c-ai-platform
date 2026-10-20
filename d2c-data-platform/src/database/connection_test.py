
import getpass
import json
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[2]


def test_connection():

    config_path = (
        ROOT / "config" / "database_config.json"
    )

    with config_path.open(
        "r", encoding="utf-8"
    ) as file:
        config = json.load(file)["database"]

    password = getpass.getpass(
        "Enter dreamnest_app password: "
    )

    print("\nConnecting to PostgreSQL...")

    with psycopg.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["name"],
        user=config["user"],
        password=password,
        connect_timeout=10
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT
                    current_database(),
                    current_user,
                    current_setting('server_version'),
                    current_setting('server_encoding'),
                    has_database_privilege(
                        current_user,
                        current_database(),
                        'CREATE'
                    )
            """)

            result = cursor.fetchone()

            if result is None:
                raise RuntimeError(
                    "Database query returned no result"
                )

            (
                database,
                username,
                server_version,
                encoding,
                can_create_schema
            ) = result

            if database != config["name"]:
                raise RuntimeError(
                    "Connected to unexpected database"
                )

            if username != config["user"]:
                raise RuntimeError(
                    "Connected with unexpected user"
                )

            if not can_create_schema:
                raise RuntimeError(
                    "Application user lacks CREATE permission"
                )

            print("\nDATABASE CONNECTION DETAILS")
            print("Database:", database)
            print("Connected user:", username)
            print("PostgreSQL version:", server_version)
            print("Encoding:", encoding)
            print("Can create schemas:", can_create_schema)

    print("\nPYTHON POSTGRESQL CONNECTION TEST PASSED.")


if __name__ == "__main__":

    print("=" * 70)
    print("PHASE 8 - PYTHON POSTGRESQL CONNECTION TEST")
    print("=" * 70)

    test_connection()
