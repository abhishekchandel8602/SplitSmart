import os
import re

import pymysql
from dotenv import load_dotenv


load_dotenv()


def required_setting(name, default=None):
    value = os.getenv(name, default)
    if not value:
        raise RuntimeError(f"Missing {name} in .env")
    return value


def create_database():
    database_name = required_setting("DB_NAME")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database_name):
        raise RuntimeError("DB_NAME may contain only letters, numbers, and underscores.")

    connection = pymysql.connect(
        host=required_setting("DB_HOST"),
        port=int(required_setting("DB_PORT", "3306")),
        user=required_setting("DB_USER"),
        password=required_setting("DB_PASSWORD"),
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


def migrate_legacy_schema():
    connection = pymysql.connect(
        host=required_setting("DB_HOST"),
        port=int(required_setting("DB_PORT", "3306")),
        user=required_setting("DB_USER"),
        password=required_setting("DB_PASSWORD"),
        database=required_setting("DB_NAME"),
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM users")
            columns = {row[0] for row in cursor.fetchall()}
            if "password" in columns and "password_hash" not in columns:
                cursor.execute(
                    "ALTER TABLE users "
                    "CHANGE COLUMN password password_hash VARCHAR(255) NOT NULL"
                )
    finally:
        connection.close()


if __name__ == "__main__":
    create_database()

    # Import only after the database exists. Creating the Flask app calls
    # SQLAlchemy's create_all(), which creates any missing application tables.
    from app import app

    migrate_legacy_schema()

    print(
        "MySQL database is ready. Tables: users, groups, group_members, "
        "expenses, expense_shares, settlements"
    )
