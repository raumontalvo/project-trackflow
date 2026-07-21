import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine
from tinydb import TinyDB

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "suppliers_db.json"

db = TinyDB(DB_PATH)

suppliers_table = db.table("suppliers")
users_table = db.table("users")
incidents_table = db.table("incidents")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required for Supabase PostgreSQL."
    )

engine = create_engine(
    DATABASE_URL,
    echo=False,
)


def create_db_and_tables() -> None:
    from services.api import models  # noqa: F401

    with engine.begin() as connection:
        connection.execute(
            text("CREATE SCHEMA IF NOT EXISTS reporting")
        )

    SQLModel.metadata.create_all(engine)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session