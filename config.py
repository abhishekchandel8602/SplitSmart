import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def mysql_database_uri():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    settings = {
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_PORT": os.getenv("DB_PORT", "3306"),
        "DB_NAME": os.getenv("DB_NAME"),
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing MySQL settings in .env: " + ", ".join(missing)
        )

    user = quote_plus(settings["DB_USER"])
    password = quote_plus(settings["DB_PASSWORD"])
    host = settings["DB_HOST"]
    port = settings["DB_PORT"]
    database = settings["DB_NAME"]
    return (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        "?charset=utf8mb4"
    )

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = mysql_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    MAIL_HOST = os.getenv("MAIL_HOST")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_FROM = os.getenv("MAIL_FROM", MAIL_USERNAME)
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://127.0.0.1:5000")
