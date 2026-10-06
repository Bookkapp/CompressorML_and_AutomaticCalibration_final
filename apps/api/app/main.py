from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import Body, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import logging
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .demo import DemoEvidence
from .calibration import run_candidate_calibration
from .repository import AnalyticsRepository
from .reference_review import ReferencePreviewRequest, ReferenceBuildRequest
from .reference_availability import source_availability
from . import reference_jobs
from .schemas import (
    AutomationStatus,
    CalibrationBatch,
    CalibrationProfile,
    CalibrationReviewCreate,
    CalibrationReviewResult,
    CalibrationShadowPoint,
    FleetMachine,
    FleetSummary,
    Incident,
    MachineApprovalRequest,
    MachineApprovalResult,
    ManualCalibrationRequest,
    ManualCalibrationResult,
    SourceMachine,
    TechnicianConfirmationCreate,
    TechnicianConfirmationCreated,
    TimelineResponse,
)


settings = get_settings()
app = FastAPI(
    title="HT9046MX Analytics API",
    version="0.1.0",
    description="Read-only shadow analytics and controlled technician feedback API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Technician-Id", "X-Approver-Id"],
)

from .context_api import router as context_router
app.include_router(context_router)
from .fleet_reference_api import router as fleet_reference_router
app.include_router(fleet_reference_router)
from .fleet_management import router as fleet_management_router
app.include_router(fleet_management_router)


log = logging.getLogger("adi.operation")

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request, exc):
    log.error("Database error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=503,
        content={"error": "Database temporarily unavailable", "detail": str(exc)[:200]},
    )

@app.exception_handler(Exception)
async def general_error_handler(request, exc):
    log.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)[:200]},
    )


def is_demo() -> bool:
    return get_settings().app_mode.lower() == "demo"


def source():
    current_settings = get_settings()
    if is_demo():
        return DemoEvidence()
    if current_settings.database_url is None:
        raise HTTPException(status_code=503, detail="Live mode requires Analytics MySQL credentials")
    return AnalyticsRepository()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "mode": "demo_verified_offline_evidence" if is_demo() else "live_shadow",
        "release_state": "SHADOW_ONLY_NOT_AUTHORIZED",
        "plc_write_path": False,
    }


@app.get("/api/v1/rehearsal/{run_id}/points")
def rehearsal_points(run_id: str, machine: str = Query("MX080"),
                     module: int = Query(6, ge=1, le=8)) -> dict:
    """Explicit local QA view; never mixed into the operational alert queue."""
    from .db import get_engine
    from .qualified_persistence import PersistentRehearsal, runs
    from sqlalchemy import select
    import json
    current = get_settings()
    if (not current.local_rehearsal_dashboard_enabled
            or current.analytics_db_host not in ("127.0.0.1", "localhost", "::1")):
        raise HTTPException(404, "Local rehearsal view is disabled")
    engine = get_engine()
    if engine is None:
        raise HTTPException(503, "Local analytics database is not configured")
    with engine.connect() as conn:
        saved = conn.execute(select(runs).where(runs.c.run_id == run_id)).mappings().first()
    if saved is None:
        raise HTTPException(404, "Rehearsal run not found")
    contract = json.loads(saved["contract_json"])
    return {"mode": "LOCAL_REHEARSAL_NOT_ACTIVE", "run_id": run_id,
            "source_timezone": contract["policy"]["source_timezone"],
            "source_cursor": saved["source_cursor"], "revision": saved["revision"],
            "episodes": PersistentRehearsal(engine).episode_summaries(run_id),
            "points": PersistentRehearsal(engine).points(run_id, machine_number=machine, module=module)}


@app.get("/api/v1/rehearsal/{run_id}/episodes/{episode_id}/raw")
def rehearsal_episode_raw(run_id: str, episode_id: str, limit: int = Query(20000, ge=1, le=20000),
                          start: datetime | None = None, end: datetime | None = None):
    from .db import get_engine
    from .qualified_persistence import PersistentRehearsal
    current = get_settings()
    if (not current.local_rehearsal_dashboard_enabled
            or current.analytics_db_host not in ("127.0.0.1", "localhost", "::1")):
        raise HTTPException(404, "Local rehearsal view is disabled")
    engine = get_engine()
    if engine is None:
        raise HTTPException(503, "Local analytics database is not configured")
    try:
        result = PersistentRehearsal(engine).episode_raw(run_id, episode_id, limit=limit, start=start, end=end)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if result is None:
        raise HTTPException(404, "Episode not found")
    return result


@app.get("/api/v1/fleet/summary", response_model=FleetSummary)
def fleet_summary(hours: int = Query(24, ge=1, le=24 * 31)) -> FleetSummary:
    provider = source()
    raw = provider.fleet_machines() if is_demo() else provider.fleet_machines(hours)
    if not is_demo():
        observed_days = max(hours / 24.0, 1.0 / 24.0)
        for item in raw:
            item["alerts_per_machine_day"] = float(item["alerts"]) / observed_days
            item["condition_status"] = (
                "Deviation detected" if int(item["alerts"]) else "Normal within this profile"
            )
    machines = [FleetMachine.model_validate(item) for item in raw]
    locked_cadence = DemoEvidence().manifest().get("cadence_minutes", 5)
    cadence_gate = (
        "MATCHED"
        if settings.scoring_interval_minutes == locked_cadence
        else "RECALIBRATION_REQUIRED"
    )
    return FleetSummary(
        mode="DEMO — verified offline replay" if is_demo() else "LIVE SHADOW",
        release_state="SHADOW_ONLY_NOT_AUTHORIZED",
        configured_machines=19,
        scored_machines=len(machines),
        open_incidents=sum(item.alerts for item in machines),
        data_quality_issues=0,
        condition_index_available=False,
        dashboard_refresh_minutes=settings.dashboard_refresh_minutes,
        scoring_interval_minutes=settings.scoring_interval_minutes,
        cadence_gate=cadence_gate,
        machines=machines,
    )


@app.get("/api/v1/incidents", response_model=list[Incident])
def incidents(limit: int = Query(100, ge=1, le=500), prospective_only: bool = Query(True)) -> list[Incident]:
    rows = source().incidents(prospective_only=prospective_only)
    return [Incident.model_validate(row) for row in rows[:limit]]


@app.post("/api/v1/incidents/simulate_prospective", response_model=Incident)
def simulate_prospective(payload: dict[str, Any] = Body(default_factory=dict)) -> Incident:
    machine = payload.get("machine", "MX080")
    module = int(payload.get("module", 6))
    row = source().simulate_prospective_alert(machine=machine, module=module)
    return Incident.model_validate(row)


@app.get(
    "/api/v1/machines/{machine}/modules/{module}/timeline",
    response_model=TimelineResponse,
)
def timeline(
    machine: str,
    module: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> TimelineResponse:
    if not 1 <= module <= 8:
        raise HTTPException(status_code=422, detail="module must be between 1 and 8")
    end = end or datetime.now(timezone.utc)
    start = start or end - timedelta(hours=24)
    if end <= start or end - start > timedelta(days=31):
        raise HTTPException(status_code=422, detail="timeline range must be 1 second to 31 days")
    rows = source().timeline(machine, module) if is_demo() else source().timeline(machine, module, start, end)
    return TimelineResponse(
        machine_number=machine.upper(),
        module=module,
        source_grain="5-minute verified replay fixture" if is_demo() else "incident snapshot / configured source",
        source_timezone="Source timezone unverified",
        condition_index_available=False,
        points=rows,
    )


@app.get("/api/v1/calibration/batches", response_model=list[CalibrationBatch])
def calibration_batches(limit: int = Query(30, ge=1, le=100)) -> list[CalibrationBatch]:
    rows = source().calibration_batches(limit) if is_demo() else source().calibration_batches(limit)
    return [CalibrationBatch.model_validate(row) for row in rows]


@app.get("/api/v1/calibration/batches/{batch_id}/profiles", response_model=list[CalibrationProfile])
def calibration_profiles(batch_id: str, limit: int = Query(500, ge=1, le=1000)) -> list[CalibrationProfile]:
    rows = source().calibration_profiles(batch_id, limit) if is_demo() else source().calibration_profiles(batch_id, limit)
    return [CalibrationProfile.model_validate(row) for row in rows]


@app.get("/api/v1/calibration/profiles/{profile_id}/shadow", response_model=list[CalibrationShadowPoint])
def calibration_shadow(profile_id: int, limit: int = Query(10000, ge=1, le=20000)) -> list[CalibrationShadowPoint]:
    rows = source().calibration_shadow_points(profile_id, limit) if is_demo() else source().calibration_shadow_points(profile_id, limit)
    return [CalibrationShadowPoint.model_validate(row) for row in rows]


@app.post(
    "/api/v1/calibration/profiles/{profile_id}/review",
    response_model=CalibrationReviewResult,
    status_code=201,
)
def review_calibration_profile(
    profile_id: int,
    payload: CalibrationReviewCreate,
    x_approver_id: str | None = Header(default=None),
) -> CalibrationReviewResult:
    if is_demo():
        raise HTTPException(status_code=409, detail="Demo mode is read-only; calibration review was not saved")
    if not x_approver_id or len(x_approver_id.strip()) < 2:
        raise HTTPException(status_code=401, detail="X-Approver-Id is required")
    try:
        review_id, status, batch_id = source().review_calibration_profile(profile_id, x_approver_id.strip(), payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    message = (
        "อนุมัติแล้ว: Active Profile ถูกเปลี่ยนแบบ transactional พร้อม rollback pointer"
        if status == "APPROVED"
        else "ปฏิเสธ candidate แล้ว: Active Profile เดิมไม่เปลี่ยน และรอบถัดไปจะรอข้อมูลใหม่"
    )
    return CalibrationReviewResult(batch_id=batch_id, profile_id=profile_id, batch_status=status, review_id=review_id, message=message)


@app.post("/api/v1/calibration/machines/{machine_number}/approve_all", response_model=MachineApprovalResult)
def approve_machine_all(
    machine_number: str,
    payload: MachineApprovalRequest,
    x_approver_id: str | None = Header(default=None),
) -> MachineApprovalResult:
    approver = x_approver_id or payload.approver_id
    if not approver or len(str(approver).strip()) < 2:
        raise HTTPException(status_code=401, detail="X-Approver-Id or approver_id is required")
    if is_demo():
        return MachineApprovalResult(
            approved_count=8,
            profile_ids=[1, 2, 3, 4, 5, 6, 7, 8],
            message=f"Demo mode: อนุมัติทั้ง 8 โมดูลสำหรับเครื่อง {machine_number} สำเร็จเรียบร้อย",
        )
    try:
        res = source().approve_machine_profiles(machine_number, str(approver).strip(), batch_id=payload.batch_id, review_note=payload.review_note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MachineApprovalResult.model_validate(res)


@app.get("/api/v1/calibration/active_profiles")
def get_active_profiles() -> list[dict[str, Any]]:
    return source().active_profiles()


@app.get("/api/v1/source/machines", response_model=list[SourceMachine])
def source_machines() -> list[SourceMachine]:
    if is_demo():
        return [SourceMachine.model_validate(m) for m in DemoEvidence().source_machines()]
    rows = source().source_machines()
    return [SourceMachine.model_validate(row) for row in rows]


def reference_actor(value: str | None) -> str:
    if is_demo():
        raise HTTPException(409, "Reference review needs configured source data; demo is read-only")
    if not value or not 2 <= len(value.strip()) <= 100:
        raise HTTPException(401, "X-Approver-Id is required")
    return value.strip()


def reference_call(callback):
    try:
        return callback()
    except reference_jobs.ReviewConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, "Reference review job not found") from exc
    except SQLAlchemyError as exc:
        log.exception("Reference review database unavailable")
        args = getattr(getattr(exc, "orig", None), "args", ())
        code = args[0] if args else None
        if code in (1205, 1213):
            detail = "REFERENCE_STORAGE_BUSY_RETRY"
        elif code == 1054 and reference_jobs.TABLE in str(getattr(exc, "statement", "")):
            detail = "REFERENCE_STORAGE_SCHEMA_MISMATCH"
        elif code == 1146 and reference_jobs.TABLE in str(getattr(exc, "statement", "")):
            detail = "Reference review storage unavailable; apply mysql_reference_review.sql to the analytics schema"
        else:
            detail = "REFERENCE_STORAGE_CONNECTION_OR_PERMISSION_ERROR"
        raise HTTPException(503, detail) from exc
    except RuntimeError as exc:
        raise HTTPException(503, "Reference review requires configured analytics storage and read-only source MySQL") from exc


@app.get("/api/v1/calibration/reference/availability")
def reference_availability(machine_number: str, module: int = Query(ge=1, le=8),
                           history_days: int = Query(default=28, ge=7, le=90)):
    if is_demo():
        raise HTTPException(409, "Source availability needs configured source data")
    try:
        return source_availability(get_settings(), machine_number=machine_number, module=module, history_days=history_days)
    except ValueError as exc:
        raise HTTPException(422, "Invalid machine, source mapping or historical-shadow configuration") from exc
    except (SQLAlchemyError, RuntimeError) as exc:
        log.exception("Reference source inventory unavailable")
        raise HTTPException(503, "Source availability unavailable; verify read-only source connection") from exc


@app.post("/api/v1/calibration/reference/automatic", status_code=202)
def prepare_automatic(payload: dict, x_approver_id: str | None = Header(default=None)):
    from .automatic_reference import PreparationRequest, create_preparation
    actor = reference_actor(x_approver_id)
    try:
        request = PreparationRequest.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(422, "Choose one machine and 7–90 Reference days") from exc
    job_id = reference_call(lambda: create_preparation(request,actor))
    reference_jobs.dispatch(job_id)
    return reference_call(lambda: reference_jobs.get_job(job_id,actor))


@app.get("/api/v1/calibration/reference/automatic")
def latest_automatic(machine_number: str, x_approver_id: str | None = Header(default=None)):
    from .automatic_reference import latest_preparation
    reference_actor(x_approver_id)
    job = reference_call(lambda: latest_preparation(machine_number))
    if job and job["status"] == "PREVIEW_QUEUED": reference_jobs.dispatch(job["job_id"])
    return job


@app.post("/api/v1/calibration/reference/jobs/{job_id}/copy", status_code=201)
def copy_automatic_review(job_id: str, x_approver_id: str | None = Header(default=None)):
    from .automatic_reference import copy_review
    actor = reference_actor(x_approver_id)
    copied = reference_call(lambda: copy_review(job_id,actor))
    return JSONResponse(reference_call(lambda: reference_jobs.get_job(copied,actor)),status_code=201)


@app.post("/api/v1/calibration/reference/preview", status_code=202)
def reference_preview(payload: ReferencePreviewRequest, x_approver_id: str | None = Header(default=None)):
    actor = reference_actor(x_approver_id)
    job = reference_call(lambda: reference_jobs.create_preview(payload, actor))
    reference_jobs.dispatch(job)
    return reference_call(lambda: reference_jobs.get_job(job, actor))


@app.get("/api/v1/calibration/reference/jobs")
def reference_recent_jobs(machine_number: str, module: int = Query(ge=1, le=8), x_approver_id: str | None = Header(default=None)):
    actor = reference_actor(x_approver_id)
    return reference_call(lambda: reference_jobs.recent_jobs(actor, machine_number, module))


@app.get("/api/v1/calibration/reference/jobs/{job_id}")
def reference_job(job_id: str, x_approver_id: str | None = Header(default=None)):
    actor = reference_actor(x_approver_id)
    job = reference_call(lambda: reference_jobs.get_job(job_id, actor))
    if job["status"] in ("PREVIEW_QUEUED", "BUILD_QUEUED"):
        reference_jobs.dispatch(job_id)
    # The durable job already contains JSON-safe primitives. Avoid recursively
    # walking every chart point again before the C JSON serializer.
    return JSONResponse(job)


@app.post("/api/v1/calibration/reference/jobs/{job_id}/build", status_code=202)
def reference_build(job_id: str, payload: ReferenceBuildRequest, x_approver_id: str | None = Header(default=None)):
    actor = reference_actor(x_approver_id)
    reference_call(lambda: reference_jobs.queue_build(job_id, actor, payload.source_digest, payload.review_note))
    reference_jobs.dispatch(job_id)
    return reference_call(lambda: reference_jobs.get_job(job_id, actor))


@app.get("/api/v1/calibration/reference/jobs/{job_id}/day")
def reference_day(job_id: str, day: date, x_approver_id: str | None = Header(default=None)):
    actor = reference_actor(x_approver_id)
    return JSONResponse(reference_call(lambda: reference_jobs.get_day(job_id, actor, day)))


@app.get("/api/v1/calibration/reference/jobs/{job_id}/raw")
def reference_raw(job_id: str, start: datetime, end: datetime, x_approver_id: str | None = Header(default=None)):
    from .reference_raw import get_raw
    actor=reference_actor(x_approver_id)
    return JSONResponse(reference_call(lambda:get_raw(job_id,actor,start,end)))


@app.get("/api/v1/calibration/source-contract")
def calibration_source_contract():
    current=get_settings()
    fields={"source_pressure_unit":"หน่วยแรงดัน","source_timezone":"เขตเวลาข้อมูล",
        "profile_state_contract_version":"กติกาสภาวะการทำงาน","profile_controller_codebook_version":"คำจำกัดความรหัส controller",
        "profile_service_epoch_version":"ช่วงประวัติซ่อมหรือเปลี่ยนการตั้งค่า"}
    result=[{"key":key,"title":title,"value":getattr(current,key),"verified":bool(getattr(current,key))} for key,title in fields.items()]
    if current.source_pressure_unit=="psi":
        result.append({"key":"pressure_basis","title":"แรงดันเกจหรือสัมบูรณ์","value":"ยังไม่ทราบ psig/psia","verified":False})
    return {"items":result,"scope":"ใช้ร่วมกันทุกโมดูลของแหล่งข้อมูลนี้","configuration":"ตั้งค่าแหล่งข้อมูลครั้งเดียว แล้วสร้างรอบใหม่หลังยืนยัน","auto_activation_allowed":False}


@app.post("/api/v1/calibration/run", response_model=ManualCalibrationResult)
def run_manual_calibration(payload: ManualCalibrationRequest) -> ManualCalibrationResult:
    if is_demo():
        target = payload.machine_number or "MX080"
        return ManualCalibrationResult(
            status="DEMO_SIMULATED",
            batch_id="demo-manual-batch",
            target_machine=target,
            profile_count=8,
            ready_count=7,
            message=f"Demo mode: การจำลองรัน Calibration สำหรับ {target} สำเร็จเรียบร้อย (Demo Verified Evidence)",
        )
    target = payload.machine_number or payload.target_machine
    if get_settings().profile_window_contract == "qualified_observed_1m" and payload.shadow_days != 3:
        raise HTTPException(status_code=422, detail="Reference preparation requires three complete Shadow days")
    if target and target.upper() == "ALL":
        target = None
    result = run_candidate_calibration(
        target_machine=target,
        history_days=payload.history_days,
        shadow_days=payload.shadow_days,
        force=True,
    )
    status = str(result.get("status", "COMPLETED"))
    target_str = target or "ทุกเครื่อง"
    msg = (
        f"รัน Calibration สำหรับ {target_str} สำเร็จ (พบ {result.get('qualified_windows', 0)} qualified windows)"
        if status == "COMPLETED"
        else f"รัน Calibration สำหรับ {target_str} ไม่สำเร็จ: {status}"
    )
    return ManualCalibrationResult(
        status=status,
        batch_id=result.get("batch_id"),
        target_machine=payload.machine_number,
        profile_count=result.get("profiles", 0),
        ready_count=result.get("status_counts", {}).get("READY_FOR_APPROVAL", 0),
        message=msg,
    )


@app.post("/api/v1/inference/run")
def trigger_inference_scoring(
    machine_number: str | None = None,
    limit: int = Query(200, ge=10, le=5000),
    sync_to_pm: bool = Query(True),
) -> dict[str, Any]:
    """Trigger real-time inference scoring using Active Profiles and sync to PM database."""
    if is_demo():
        return {
            "status": "DEMO_SIMULATED",
            "scored_windows": 100,
            "raw_flags": 0,
            "persistent_alerts": 0,
            "synced_diagnostics_to_pm": 100,
            "machines_processed": [machine_number or "MX080"],
            "message": "Demo mode simulated inference run.",
        }
    from .inference import run_inference_and_sync
    targets = [machine_number] if machine_number else None
    return run_inference_and_sync(
        target_machines=targets,
        limit_rows_per_machine=limit,
        sync_to_pm=sync_to_pm,
    )



@app.post(
    "/api/v1/incidents/{alert_id}/confirmations",
    response_model=TechnicianConfirmationCreated,
    status_code=201,
)
def create_confirmation(
    alert_id: int,
    payload: TechnicianConfirmationCreate,
    x_technician_id: str | None = Header(default=None),
) -> TechnicianConfirmationCreated:
    if is_demo():
        raise HTTPException(status_code=409, detail="Demo mode is read-only; confirmation was not saved")
    if not x_technician_id or len(x_technician_id.strip()) < 2:
        raise HTTPException(status_code=401, detail="X-Technician-Id is required")
    if settings.technician_feedback_start_at is None:
        raise HTTPException(
            status_code=503,
            detail="Prospective feedback is disabled until TECHNICIAN_FEEDBACK_START_AT is configured",
        )
    alert = source().alert_metadata(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert episode was not found")
    detected_at = alert["detected_at"]
    if detected_at.tzinfo is None:
        if settings.alert_timezone is None:
            raise HTTPException(
                status_code=503,
                detail="Prospective feedback is disabled until ALERT_DATETIME_TIMEZONE is configured",
            )
        detected_at = detected_at.replace(tzinfo=settings.alert_timezone)
    detected_at = detected_at.astimezone(timezone.utc)
    if detected_at < settings.technician_feedback_start_at:
        raise HTTPException(
            status_code=409,
            detail="Only alerts detected on or after the prospective-feedback start time can be confirmed",
        )
    confirmation_id = source().create_confirmation(alert_id, x_technician_id.strip(), payload)
    return TechnicianConfirmationCreated(
        confirmation_id=confirmation_id,
        alert_id=alert_id,
        label_status="PENDING_QA",
        message="บันทึกการยืนยันแล้ว และรอ Label QA ก่อนเข้าสู่ชุดข้อมูลฝึกแบบ binary anomaly",
    )


@app.get("/api/v1/automation/status", response_model=AutomationStatus)
def automation_status() -> AutomationStatus:
    locked = int(DemoEvidence().manifest().get("cadence_minutes", 5))
    runs = [] if is_demo() else source().automation_runs()
    return AutomationStatus(
        dashboard_refresh_minutes=settings.dashboard_refresh_minutes,
        desired_scoring_interval_minutes=settings.scoring_interval_minutes,
        locked_release_interval_minutes=locked,
        cadence_gate="MATCHED" if locked == settings.scoring_interval_minutes else "RECALIBRATION_REQUIRED",
        profile_schedule=settings.profile_candidate_cron,
        model_schedule=settings.model_candidate_cron,
        scoring_schedule=settings.shadow_score_cron,
        profile_activation="HUMAN_APPROVAL_REQUIRED",
        model_activation="HUMAN_APPROVAL_REQUIRED",
        latest_runs=runs,
    )
