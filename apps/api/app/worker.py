from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from .calibration import run_candidate_calibration
from .config import get_settings
from .db import connection


settings = get_settings()


def _record(job_type: str, status: str, detail: dict) -> None:
    if settings.database_url is None:
        return
    with connection() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ht9046mx_automation_run
                    (job_type, started_at, completed_at, result_status, detail_json)
                VALUES (:job_type, :started_at, :completed_at, :status, :detail)
                """
            ),
            {
                "job_type": job_type,
                "started_at": datetime.now(timezone.utc),
                "completed_at": datetime.now(timezone.utc),
                "status": status,
                "detail": json.dumps(detail, ensure_ascii=False),
            },
        )


def run_candidate_job(job_type: str, command: str) -> None:
    if not command.strip():
        _record(job_type, "SKIPPED_NOT_CONFIGURED", {"auto_activation_allowed": False})
        return
    started = datetime.now(timezone.utc)
    try:
        result = subprocess.run(
            shlex.split(command),
            cwd=settings.project_root,
            capture_output=True,
            text=True,
            timeout=6 * 60 * 60,
            check=False,
        )
        _record(
            job_type,
            "CANDIDATE_CREATED" if result.returncode == 0 else "FAILED",
            {
                "started_at": started.isoformat(),
                "return_code": result.returncode,
                "stdout_tail": result.stdout[-2000:],
                "stderr_tail": result.stderr[-2000:],
                "auto_activation_allowed": False,
            },
        )
    except Exception as exc:
        _record(job_type, "FAILED", {"error": str(exc), "auto_activation_allowed": False})


def run_profile_candidate_job(machines: list[str] | None = None) -> None:
    """Run the built-in, read-only source-to-candidate calibration cycle."""
    if not settings.profile_candidate_enabled:
        run_candidate_job("PROFILE_CANDIDATE", settings.profile_candidate_command)
        return
    try:
        result = ({"status":"SCOPED_AUTOMATIC_REFERENCE_CYCLE","machine_results":[
            run_candidate_calibration(settings,target_machine=machine) for machine in machines],"auto_activation_allowed":False}
            if machines else run_candidate_calibration(settings))
        status = str(result.pop("status", "COMPLETED"))
        _record("PROFILE_CANDIDATE", status, {**result, "auto_activation_allowed": False})
    except Exception as exc:
        _record("PROFILE_CANDIDATE", "FAILED", {"error": str(exc), "auto_activation_allowed": False})


def run_detector_job() -> None:
    """Opt-in qualified stream and durable PM outbox; no model/profile activation."""
    if not settings.detector_worker_enabled:
        return
    from .qualified_detector import run_configured_cycle
    from .qualified_bridge import run_configured_bridge
    try:
        result = run_configured_cycle(settings)
        result["bridge"] = run_configured_bridge(settings)
        _record("QUALIFIED_DETECTOR", "COMPLETED", result)
    except Exception as exc:
        # Do not persist connector exceptions that can contain credential-bearing URLs/SQL.
        _record("QUALIFIED_DETECTOR", "FAILED", {"error_type": type(exc).__name__,
                "detail": "Inspect the local worker service; no profile was activated."})


def main(*, profiles_only: bool = False, machines: list[str] | None = None, detector_only:bool=False) -> None:
    scheduler = BlockingScheduler(timezone="Asia/Bangkok")
    if detector_only:
        scheduler.add_job(run_detector_job,CronTrigger.from_crontab(settings.detector_cron,timezone='Asia/Bangkok'),
                          id='qualified-detector',max_instances=1,coalesce=True)
        scheduler.start()
        return
    if not profiles_only:
        scheduler.add_job(run_detector_job,
            CronTrigger.from_crontab(settings.detector_cron, timezone="Asia/Bangkok"),
            id="qualified-detector", max_instances=1, coalesce=True)
        scheduler.add_job(run_candidate_job,
            CronTrigger.from_crontab(settings.shadow_score_cron, timezone="Asia/Bangkok"),
            args=["SHADOW_SCORE", settings.shadow_score_command],id="shadow-score",max_instances=1,coalesce=True)
    scheduler.add_job(
        run_profile_candidate_job,
        CronTrigger.from_crontab(settings.profile_candidate_cron, timezone="Asia/Bangkok"),
        id="profile-candidate",
        args=[machines],
        max_instances=1,
        coalesce=True,
    )
    if not profiles_only: scheduler.add_job(
        run_candidate_job,
        CronTrigger.from_crontab(settings.model_candidate_cron, timezone="Asia/Bangkok"),
        args=["MODEL_CANDIDATE", settings.model_candidate_command],
        id="model-candidate",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Candidate preparation scheduler")
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--profiles-only",action="store_true",help="Schedule profile preparation only")
    group.add_argument("--detector-only",action="store_true",help="Observe/scoring/Event worker only; no scheduled training")
    parser.add_argument("--machines",nargs="*",help="Limit preparation to selected source machines")
    args = parser.parse_args()
    main(profiles_only=args.profiles_only,machines=args.machines,detector_only=args.detector_only)
