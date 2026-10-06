"""Run the OPERATION API against isolated local HT9046MX-777 mock schemas."""

from __future__ import annotations

import uvicorn

from mock777_env import configure

configure()

uvicorn.run("apps.api.app.main:app", host="127.0.0.1", port=8001, access_log=False, log_level="warning")
