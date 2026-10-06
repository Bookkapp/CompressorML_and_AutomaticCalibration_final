"""Process-local environment for isolated HT9046MX-777 integration tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def configure() -> None:
    dashboard_root = Path(__file__).resolve().parents[2] / "Compressor_and_VacuumPump"
    operation_root = Path(__file__).resolve().parents[1]
    if not dashboard_root.is_dir():
        raise RuntimeError("Dashboard sibling repository was not found")
    sys.path.insert(0, str(operation_root))
    sys.path.insert(0, str(dashboard_root))
    from app.config import settings as dashboard_settings

    if dashboard_settings.db_host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Mock operation requires a local MySQL server")
    os.environ.update({
        "HT9046MX_APP_MODE": "live",
        "HT9046MX_ANALYTICS_DB_HOST": "127.0.0.1",
        "HT9046MX_ANALYTICS_DB_NAME": "ht_mock777_analytics",
        "HT9046MX_ANALYTICS_DB_USER": dashboard_settings.db_user,
        "HT9046MX_ANALYTICS_DB_PASSWORD": dashboard_settings.db_password,
        "HT9046MX_SOURCE_DB_HOST": "127.0.0.1",
        "HT9046MX_SOURCE_DB_NAME": "ht_mock777_source",
        "HT9046MX_SOURCE_DB_USER": dashboard_settings.db_user,
        "HT9046MX_SOURCE_DB_PASSWORD": dashboard_settings.db_password,
        "HT9046MX_SOURCE_TABLE": "ht9046mx_readings",
        "HT9046MX_SOURCE_TIMEZONE": "Asia/Bangkok",
        "HT9046MX_PROFILE_CANDIDATE_ENABLED": "true",
        "HT9046MX_API_CORS_ORIGINS": "http://localhost:5174,http://127.0.0.1:5174",
    })
