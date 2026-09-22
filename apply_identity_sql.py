from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg


# ============================================================
# AutoPulse
# Identity Governance SQL Installer
#
# Purpose:
# Persist the database objects required by:
#
# /api/v1/data-confidence
#
# Important:
# Some AutoPulse SQL migration files open an explicit
# transaction. This installer explicitly COMMITs each script
# so the created views/tables remain after the connection closes.
# ============================================================


ROOT_DIR = Path(__file__).resolve().parent


SQL_FILES = [
    ROOT_DIR
    / "sql"
    / "identity"
    / "007_entity_resolution_review_queue.sql",

    ROOT_DIR
    / "sql"
    / "identity"
    / "008_model_alias_audit.sql",
]


def get_password() -> str:

    password = os.environ.get(
        "AUTOPULSE_DB_PASSWORD"
    )

    if not password:
        raise RuntimeError(
            "AUTOPULSE_DB_PASSWORD is not set "
            "in this PowerShell session."
        )

    return password


def get_connection() -> psycopg.Connection:

    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname="autopulse_ops",
        user="autopulse_app",
        password=get_password(),
        connect_timeout=10,
        autocommit=True,
    )


def verify_files() -> None:

    for sql_file in SQL_FILES:

        if not sql_file.exists():

            raise FileNotFoundError(
                f"SQL file not found: {sql_file}"
            )


def execute_sql_file(
    connection: psycopg.Connection,
    sql_file: Path,
) -> None:

    print()
    print("=" * 72)
    print(f"RUNNING: {sql_file.name}")
    print("=" * 72)

    sql = sql_file.read_text(
        encoding="utf-8"
    )

    with connection.cursor() as cursor:

        cursor.execute(
            "SET lock_timeout = '20s';"
        )

        cursor.execute(
            "SET statement_timeout = '180s';"
        )

        cursor.execute(
            sql
        )

        # ----------------------------------------------------
        # CRITICAL
        #
        # Some migration SQL files contain BEGIN statements.
        # With autocommit enabled, an explicit BEGIN remains
        # open until COMMIT or connection close.
        #
        # Without this COMMIT, PostgreSQL rolls the migration
        # back when this script exits.
        # ----------------------------------------------------

        cursor.execute(
            "COMMIT;"
        )

    print(
        f"SUCCESS + COMMITTED: {sql_file.name}"
    )


def verify_objects(
    connection: psycopg.Connection,
) -> None:

    print()
    print("=" * 72)
    print("VERIFYING PERSISTED DATABASE OBJECTS")
    print("=" * 72)

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT
                to_regclass(
                    'identity.entity_resolution_review_queue'
                )::text
                    AS review_queue,

                to_regclass(
                    'identity.model_alias_audit'
                )::text
                    AS model_alias_audit;
            """
        )

        row = cursor.fetchone()

    if not row:

        raise RuntimeError(
            "Database object verification returned no result."
        )

    review_queue = row[0]
    model_alias_audit = row[1]

    print(
        "entity_resolution_review_queue:",
        review_queue,
    )

    print(
        "model_alias_audit:",
        model_alias_audit,
    )

    if (
        review_queue
        != "identity.entity_resolution_review_queue"
    ):

        raise RuntimeError(
            "identity.entity_resolution_review_queue "
            "does not exist after COMMIT."
        )

    if (
        model_alias_audit
        != "identity.model_alias_audit"
    ):

        raise RuntimeError(
            "identity.model_alias_audit "
            "does not exist after COMMIT."
        )


def verify_with_new_connection() -> None:

    # --------------------------------------------------------
    # This is deliberately a NEW database connection.
    #
    # If the objects are visible here, they were genuinely
    # committed and are not merely visible inside the migration
    # transaction.
    # --------------------------------------------------------

    connection = get_connection()

    try:

        print()
        print("=" * 72)
        print("VERIFYING FROM A NEW DATABASE SESSION")
        print("=" * 72)

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    to_regclass(
                        'identity.entity_resolution_review_queue'
                    )::text,

                    to_regclass(
                        'identity.model_alias_audit'
                    )::text;
                """
            )

            row = cursor.fetchone()

        review_queue = (
            row[0]
            if row
            else None
        )

        model_alias_audit = (
            row[1]
            if row
            else None
        )

        print(
            "entity_resolution_review_queue:",
            review_queue,
        )

        print(
            "model_alias_audit:",
            model_alias_audit,
        )

        if (
            review_queue
            != "identity.entity_resolution_review_queue"
        ):

            raise RuntimeError(
                "Review queue did not persist "
                "to a new database session."
            )

        if (
            model_alias_audit
            != "identity.model_alias_audit"
        ):

            raise RuntimeError(
                "Model alias audit did not persist "
                "to a new database session."
            )

    finally:

        connection.close()


def main() -> int:

    print()
    print("=" * 72)
    print("AUTOPULSE IDENTITY GOVERNANCE INSTALLER")
    print("=" * 72)

    connection = None

    try:

        verify_files()

        print(
            "Migration files located."
        )

        connection = get_connection()

        print(
            "Connected to autopulse_ops."
        )

        for sql_file in SQL_FILES:

            execute_sql_file(
                connection,
                sql_file,
            )

        verify_objects(
            connection
        )

        connection.close()
        connection = None

        verify_with_new_connection()

        print()
        print("=" * 72)
        print("AUTOPULSE IDENTITY GOVERNANCE READY")
        print("DATABASE OBJECTS ARE PERSISTED")
        print("=" * 72)

        return 0

    except Exception as exc:

        print()
        print("=" * 72)
        print("INSTALLATION FAILED")
        print("=" * 72)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        return 1

    finally:

        if connection is not None:

            try:
                connection.close()
            except Exception:
                pass


if __name__ == "__main__":

    sys.exit(
        main()
    )