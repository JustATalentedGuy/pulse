import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import dotenv_values


BACKEND_DIR = Path(__file__).resolve().parents[1]


def psql_url(value: str) -> str:
    parts = urlsplit(value)
    scheme = parts.scheme.split("+", 1)[0]
    if scheme == "postgres":
        scheme = "postgresql"
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


def run(command: list[str], *, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def main() -> None:
    env = dotenv_values(BACKEND_DIR / ".env")
    parser = argparse.ArgumentParser(
        description="Copy all Pulse data from local Docker Postgres to Supabase"
    )
    parser.add_argument("--source-container", default="pulse-db-1")
    parser.add_argument(
        "--source-user",
        default=env.get("POSTGRES_USER") or "pulse",
    )
    parser.add_argument(
        "--source-database",
        default=env.get("POSTGRES_DB") or "pulse",
    )
    parser.add_argument(
        "--target-url",
        default=os.environ.get("SUPABASE_DB_URL"),
    )
    args = parser.parse_args()
    if not args.target_url:
        parser.error("Set SUPABASE_DB_URL or pass --target-url")

    dump = run(
        [
            "docker",
            "exec",
            args.source_container,
            "pg_dump",
            "-U",
            args.source_user,
            "-d",
            args.source_database,
            "--data-only",
            "--column-inserts",
            "--on-conflict-do-nothing",
            "--no-owner",
            "--no-privileges",
            "--exclude-table=alembic_version",
        ]
    )
    target_url = psql_url(args.target_url)
    run(
        [
            "docker",
            "run",
            "--rm",
            "-i",
            "postgres:17",
            "psql",
            "--set",
            "ON_ERROR_STOP=on",
            target_url,
        ],
        input_bytes=dump,
    )
    print("Pulse data migration completed successfully.")


if __name__ == "__main__":
    main()
