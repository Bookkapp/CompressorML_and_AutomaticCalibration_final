"""Verified at-least-once operational event boundary, not a public write API.

An existing PM outbox supplies original timestamps and scoped record IDs.
Analytics receipt + the single common ledger commit together; producer retries
the same identity. Corrections must use a new external ID and supersedes ID.
"""
from datetime import datetime
from pydantic import BaseModel,ConfigDict,Field,model_validator
from sqlalchemy import Column,String,MetaData,Table,select
from .unified_events import fingerprint,append_events,make_event
from .reference_jobs import ReviewConflict
from .inference import clean_machine_code

metadata=MetaData()
receipts=Table("ht9046mx_operational_event_receipt",metadata,
    Column("producer",String(100),primary_key=True),Column("external_event_id",String(100),primary_key=True),
    Column("payload_digest",String(64),nullable=False),Column("event_id",String(64),nullable=False))


class OperationalEvent(BaseModel):
    model_config=ConfigDict(extra="forbid")
    producer:str=Field(min_length=3,max_length=100)
    external_event_id:str=Field(min_length=1,max_length=100)
    machine_number:str=Field(min_length=1,max_length=64)
    module:int|None=Field(default=None,ge=1,le=8)
    occurred_at:datetime
    source_timezone:str=Field(min_length=1,max_length=64)
    source_database:str=Field(min_length=3,max_length=200)
    source_record_type:str=Field(min_length=3,max_length=64)
    source_record_id:str=Field(min_length=1,max_length=100)
    event_type:str
    correlation_id:str|None=Field(default=None,max_length=64)
    mode:str="LIVE"
    before:dict|None=None
    after:dict|None=None
    actor:str|None=Field(default=None,max_length=100)
    reason:str|None=Field(default=None,max_length=2000)
    supersedes_event_id:str|None=Field(default=None,min_length=64,max_length=64)

    @model_validator(mode="after")
    def validate_event(self):
        kinds={"ALERT_CREATED","ALERT_ACKNOWLEDGED","ALERT_CLOSED","ALERT_SUPPRESSED","ALERT_DELIVERY_FAILED",
               "WORK_ORDER_CREATED","WORK_ORDER_STARTED","WORK_ORDER_COMPLETED","WORK_ORDER_DELETED",
               "SERVICE_LOG_CREATED","SERVICE_LOG_UPDATED","OPERATIONAL_EVENT_CORRECTED"}
        if self.event_type not in kinds: raise ValueError("Explicit operational lifecycle event required")
        if self.mode not in {"LIVE","HISTORICAL","SHADOW"}: raise ValueError("Explicit producer mode required")
        self.machine_number=clean_machine_code(self.machine_number)
        if self.event_type=="OPERATIONAL_EVENT_CORRECTED" and not self.supersedes_event_id:
            raise ValueError("Correction must retain a supersedes event ID")
        return self


def receive(engine,event:OperationalEvent,*,before_commit=None):
    payload=event.model_dump(mode="json")
    digest=fingerprint(payload)
    record=make_event(source_key=[event.producer,event.external_event_id],machine=event.machine_number,module=event.module,
        occurred_at=event.occurred_at,timezone_name=event.source_timezone,event_type=event.event_type,
        family="NOTIFICATION" if event.event_type.startswith("ALERT") else "OPERATIONAL",mode=event.mode,
        assessment="SOURCE_RECORDED",correlation_id=event.correlation_id,details=payload)
    with engine.begin() as conn:
        old=conn.execute(select(receipts).where(receipts.c.producer==event.producer,
                                                receipts.c.external_event_id==event.external_event_id).with_for_update()).mappings().first()
        if old:
            if old["payload_digest"]!=digest: raise ReviewConflict("PRODUCER_ID_REUSED_WITH_CHANGED_PAYLOAD")
            return {"event_id":old["event_id"],"duplicate":True}
        if event.supersedes_event_id:
            from .unified_events import events
            original=conn.execute(select(events.c.machine_number,events.c.module).where(events.c.event_id==event.supersedes_event_id)).first()
            if not original or original[0]!=event.machine_number or original[1]!=event.module:
                raise ReviewConflict("CORRECTION_TARGET_IDENTITY_MISMATCH")
        append_events(conn,[record])
        conn.execute(receipts.insert().values(producer=event.producer,external_event_id=event.external_event_id,
                                              payload_digest=digest,event_id=record["event_id"]))
        if before_commit: before_commit()
    return {"event_id":record["event_id"],"duplicate":False}
