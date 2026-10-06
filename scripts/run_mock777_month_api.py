"""Run OPERATION against the isolated 30-day MX777 fixture only."""

from __future__ import annotations

import os

import uvicorn

from mock777_env import configure


configure()
os.environ.update({
    "HT9046MX_ANALYTICS_DB_NAME": "ht_mock777_month_analytics",
    "HT9046MX_SOURCE_DB_NAME": "ht_mock777_month_source",
    "HT9046MX_PROFILE_STATE_CONTRACT_VERSION": "MOCK777_SYNTHETIC_COLD_V1",
    "HT9046MX_PROFILE_CONTROLLER_CODEBOOK_VERSION": "MOCK777_SYNTHETIC_CONTROLLER_V1",
    "HT9046MX_PROFILE_SERVICE_EPOCH_VERSION": "MOCK777_SYNTHETIC_NO_SERVICE_V1",
    "HT9046MX_API_CORS_ORIGINS": "http://127.0.0.1:5175,http://localhost:5175",
})

uvicorn.run("apps.api.app.main:app", host="127.0.0.1", port=8002, access_log=False, log_level="warning")
