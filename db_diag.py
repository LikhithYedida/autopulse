import os
import psycopg

password = os.environ.get("AUTOPULSE_DB_PASSWORD")

conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="autopulse_ops",
    user="autopulse_app",
    password=password,
    connect_timeout=5,
    autocommit=True,
)

with conn.cursor() as cur:

    print("Attempting to terminate blocker PID 1704...")

    cur.execute(
        "SELECT pg_terminate_backend(%s);",
        (1704,),
    )

    result = cur.fetchone()

    print("Terminate result:", result)

conn.close()