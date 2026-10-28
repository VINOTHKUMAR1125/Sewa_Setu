# -*- coding: utf-8 -*-
"""Settings: config/app.ini for non-secret defaults, environment for secrets.

Secrets (DB password, session signing key, admin password) are never read from
the repository. The application refuses to start without them.
"""
import os
import configparser
from dataclasses import dataclass
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INI_PATH = os.path.join(BASE_DIR, "config", "app.ini")


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_pool_max: int
    secret_key: str
    admin_username: str
    admin_password: str
    sms_gateway_url: str
    otp_validity_seconds: int
    upload_dir: str
    max_upload_bytes: int
    session_minutes: int
    min_age: int
    sla_days: int
    scheme_deadline: datetime


def _read_ini():
    parser = configparser.ConfigParser()
    if not parser.read(INI_PATH):
        raise ConfigError("configuration file not found: %s" % INI_PATH)
    return parser


def load_settings(environ=None):
    env = os.environ if environ is None else environ
    ini = _read_ini()

    def pick(env_name, section, key, default=None):
        if env.get(env_name):
            return env[env_name]
        if ini.has_option(section, key):
            return ini.get(section, key)
        return default

    def secret(env_name):
        value = env.get(env_name, "")
        if not value:
            raise ConfigError("%s must be set in the environment" % env_name)
        return value

    return Settings(
        db_host=pick("DB_HOST", "database", "host", "db"),
        db_port=int(pick("DB_PORT", "database", "port", "5432")),
        db_name=pick("DB_NAME", "database", "name", "sewasetu"),
        db_user=pick("DB_USER", "database", "user", "sewasetu"),
        db_password=secret("DB_PASSWORD"),
        db_pool_max=int(pick("DB_POOL_MAX", "database", "pool_max", "8")),
        secret_key=secret("SECRET_KEY"),
        admin_username=pick("ADMIN_USERNAME", "admin", "username", "admin"),
        admin_password=secret("ADMIN_PASSWORD"),
        sms_gateway_url=pick("SMS_GATEWAY_URL", "app", "sms_gateway_url",
                             "http://smsgw:8025"),
        otp_validity_seconds=int(pick("OTP_VALIDITY_SECONDS", "app",
                                      "otp_validity_seconds", "300")),
        upload_dir=pick("UPLOAD_DIR", "app", "upload_dir",
                        "/var/sewasetu/uploads"),
        max_upload_bytes=int(float(pick("MAX_UPLOAD_MB", "app",
                                        "max_upload_mb", "5")) * 1024 * 1024),
        session_minutes=int(pick("SESSION_MINUTES", "app",
                                 "session_minutes", "30")),
        min_age=int(pick("MIN_AGE", "pension", "min_age", "60")),
        sla_days=int(pick("SLA_DAYS", "pension", "sla_days", "15")),
        scheme_deadline=datetime.strptime(
            pick("SCHEME_DEADLINE", "pension", "scheme_deadline",
                 "2026-10-31 23:59"), "%Y-%m-%d %H:%M"),
    )
