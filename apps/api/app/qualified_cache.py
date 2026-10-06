"""Shared, bounded daily minute snapshots in ANALYTICS; source is SELECT-only.

Preview/detail may reuse a one-hour CLOSED-day snapshot. Manual Build reads the
source again. Automatic preparation primes all eight modules in one streamed
pass per day, then fits each module from that preparation's cached snapshots.
Named locks serialize fills across processes; no raw seconds are persisted.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text
from .db import source_connection
from .inference import _qualified_source_table, get_machine_candidates

from .db import connection, get_engine
from .qualified_calibration import load_observed_one_minute_windows
from .qualified_windows import QualifiedWindow, WINDOW_VERSION

TABLE = "ht9046mx_qualified_day_cache"
TTL = timedelta(hours=1)
INVENTORY_TTL = timedelta(minutes=5)


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def day_key(settings, machine, day):
    # Credentials are neither serialized nor exposed. Host identifies source.
    names = ("source_db_host", "source_db_name", "source_table", "source_machine_column",
             "source_timestamp_column", "source_global_status_column", "source_timezone",
             "source_compressor_on_status", "source_module_status_template", "source_busy_template",
             "source_busy_normal_values", "source_sv_template", "source_sv_off_values",
             "source_hp1_template", "source_lp1_template", "source_hp2_template", "source_lp2_template",
             "source_valve_template", "source_temp_high_template", "source_temp_low_template",
             "source_expected_cadence_seconds", "qualified_1m_minimum_coverage",
             "qualified_1m_maximum_gap_seconds", "qualified_1m_late_arrival_seconds")
    identity = {key: getattr(settings, key) for key in names}
    identity.update(machine=machine, day=day.isoformat(), version=WINDOW_VERSION)
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def pack(windows):
    return gzip.compress(json.dumps([asdict(w) for w in windows], default=lambda v:v.isoformat(),
                                   allow_nan=False, separators=(",", ":")).encode(), compresslevel=1)


def unpack(value):
    rows = json.loads(gzip.decompress(value))
    for row in rows:
        row["window_start"] = datetime.fromisoformat(row["window_start"])
        row["window_end"] = datetime.fromisoformat(row["window_end"])
    return [QualifiedWindow(**row) for row in rows]


def read_day(key, modules, *, minimum_checked_at=None, allow_stale=False, revision=None):
    with connection() as conn:
        rows = conn.execute(text(f"SELECT module,payload,checked_at,source_revision FROM {TABLE} WHERE day_key=:key AND module IN :modules")
            .bindparams(bindparam("modules", expanding=True)), {"key":key,"modules":tuple(modules)}).mappings().all()
    valid = []
    for row in rows:
        checked = row["checked_at"]
        if isinstance(checked, str): checked = datetime.fromisoformat(checked)
        if not allow_stale and checked < (minimum_checked_at or now()-TTL): return None
        if revision is not None and row["source_revision"] != revision: return None
        valid.append(row)
    if {r["module"] for r in valid} != set(modules): return None
    if len({r["source_revision"] for r in valid}) != 1: return None
    return [w for row in valid for w in unpack(row["payload"])]


def revision_expression(settings):
    from .qualified_calibration import IDENTIFIER
    templates = (settings.source_module_status_template,settings.source_busy_template,settings.source_sv_template,
        settings.source_hp1_template,settings.source_lp1_template,settings.source_hp2_template,settings.source_lp2_template,
        settings.source_valve_template,settings.source_temp_high_template,settings.source_temp_low_template)
    columns = [settings.source_machine_column,settings.source_timestamp_column,settings.source_global_status_column,
               *(t.format(module=m) for m in range(1,9) for t in templates)]
    if not all(IDENTIFIER.fullmatch(c) for c in columns): raise ValueError("Unsafe source column mapping")
    # NULL markers and length prefixes distinguish NULL/empty/delimiter values.
    value = "CONCAT("+",".join(f"IF(`{c}` IS NULL,'N;',CONCAT('V',LENGTH(CAST(`{c}` AS CHAR)),':',CAST(`{c}` AS CHAR),';'))" for c in columns)+")"
    return f"CRC32({value})"


def source_revision(settings, machine, start, end):
    """Count/CRC sum/xor detect changes; Manual Build also checks SHA256 evidence."""
    crc = revision_expression(settings)
    table = _qualified_source_table(settings.source_db_name,settings.source_table)
    query = text(f"SELECT COUNT(*) AS n,COALESCE(SUM({crc}),0) AS total,BIT_XOR({crc}) AS x FROM {table} "
        f"WHERE `{settings.source_machine_column}` IN :machines AND `{settings.source_timestamp_column}`>=:start AND `{settings.source_timestamp_column}`<:end")
    with source_connection() as conn:
        row = conn.execute(query.bindparams(bindparam("machines",expanding=True)),
            {"machines":get_machine_candidates(machine),"start":start.replace(tzinfo=None),"end":end.replace(tzinfo=None)}).mappings().one()
    return f"{row['n']}:{row['total']}:{row['x']}"


@contextmanager
def fill_lock(key, *, engine_override=None):
    engine = engine_override if engine_override is not None else get_engine()
    if engine is None: raise RuntimeError("Analytics database is not configured")
    with engine.connect() as conn:
        mysql = conn.dialect.name == "mysql"
        name = "qday-"+key[:50]
        if mysql and conn.execute(text("SELECT GET_LOCK(:name,60)"), {"name":name}).scalar() != 1:
            raise RuntimeError("QUALIFIED_CACHE_BUSY")
        try: yield
        finally:
            if mysql: conn.execute(text("SELECT RELEASE_LOCK(:name)"), {"name":name})


def load_cached_windows(settings, *, machine_number, start, end, as_of=None,
                        modules=range(1,9), progress=None, fresh=False, minimum_checked_at=None):
    modules = tuple(modules)
    if any(m not in range(1,9) for m in modules) or not modules or len(set(modules)) != len(modules):
        raise ValueError("modules must be unique numbers 1..8")
    zone = ZoneInfo(settings.source_timezone)
    if start.tzinfo is None or end.tzinfo is None or (as_of and as_of.tzinfo is None):
        raise ValueError("start, end and as_of must be timezone-aware")
    if fresh:
        # Final Manual Build checks exact SHA256 evidence from current raw
        # seconds. It needs neither a fleet-wide CRC nor cached window writes.
        return load_observed_one_minute_windows(settings,machine_number=machine_number,
            start=start,end=end,as_of=as_of,modules=modules,progress=progress,compact_json=True)
    first, stop = start.astimezone(zone), end.astimezone(zone)
    cursor = first
    result = []
    while cursor < stop:
        day_end = min(stop, cursor.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1))
        if progress: progress(cursor.date().isoformat())
        closed = (as_of or end).astimezone(zone) - timedelta(seconds=settings.qualified_1m_late_arrival_seconds)
        full = cursor.time().isoformat() == "00:00:00" and day_end-cursor == timedelta(days=1) and day_end <= closed
        if not full:
            windows = load_observed_one_minute_windows(settings, machine_number=machine_number,
                start=cursor,end=day_end,as_of=as_of,modules=modules)
        else:
            key = day_key(settings,machine_number,cursor.date())
            windows = None if fresh else read_day(key,modules,minimum_checked_at=minimum_checked_at)
            if windows is None:
                with fill_lock(key):
                    windows = None if fresh else read_day(key,modules,minimum_checked_at=minimum_checked_at)
                    if windows is None:
                        previous = None if fresh else read_day(key,modules,allow_stale=True)
                        revision = source_revision(settings,machine_number,cursor,day_end) if previous is not None else None
                        unchanged = read_day(key,modules,allow_stale=True,revision=revision) if revision is not None else None
                        if unchanged is not None:
                            with connection() as conn:
                                conn.execute(text(f"UPDATE {TABLE} SET checked_at=:checked WHERE day_key=:key AND source_revision=:revision"),
                                    {"key":key,"checked":now(),"revision":revision})
                            result.extend(unchanged)
                            cursor = day_end
                            continue
                        # Preview fills all modules once; Build refreshes only
                        # requested modules against current source, never TTL.
                        collect = modules if fresh else tuple(range(1,9))
                        revision_out = {}
                        all_windows = load_observed_one_minute_windows(settings,machine_number=machine_number,
                            start=cursor,end=day_end,as_of=as_of,modules=collect,revision_out=revision_out,compact_json=True)
                        revision = revision_out[cursor.date().isoformat()]
                        checked = now()
                        with connection() as conn:
                            for module in collect:
                                items = [w for w in all_windows if w.module == module]
                                conn.execute(text(f"DELETE FROM {TABLE} WHERE day_key=:key AND module=:module"),{"key":key,"module":module})
                                conn.execute(text(f"INSERT INTO {TABLE}(day_key,module,checked_at,payload,source_revision) VALUES(:key,:module,:checked,:payload,:revision)"),
                                    {"key":key,"module":module,"checked":checked,"payload":pack(items),"revision":revision})
                        windows = [w for w in all_windows if w.module in modules]
        result.extend(windows)
        cursor = day_end
    return sorted(result,key=lambda w:(w.machine_number,w.module,w.window_start))


def invalidate_period(settings, machine, start, end):
    """Invalidate only derived snapshots when a fresh Build detects changed data."""
    zone=ZoneInfo(settings.source_timezone)
    cursor=start.astimezone(zone).replace(hour=0,minute=0,second=0,microsecond=0)
    keys=[]
    while cursor < end.astimezone(zone):
        keys.append(day_key(settings,machine,cursor.date()));cursor+=timedelta(days=1)
    with connection() as conn:
        conn.execute(text(f"DELETE FROM {TABLE} WHERE day_key IN :keys").bindparams(bindparam("keys",expanding=True)),{"keys":keys})


def prime_period(settings, *, machine_number, start, end, as_of, progress=None):
    """Prime one source day at a time: RAM never holds the fleet's raw period."""
    checked_after = now()
    cursor = start
    while cursor < end:
        day_end = min(end,cursor+timedelta(days=1))
        load_cached_windows(settings,machine_number=machine_number,start=cursor,end=day_end,
            as_of=as_of,modules=range(1,9),progress=progress)
        cursor = day_end
    # Cached days can predate this preparation by TTL. Subsequent reads must
    # reuse exactly the primed snapshots even if the first day's TTL expires.
    return checked_after-TTL


def cached_machine_inventory(settings):
    """Share the small selector inventory across tabs/processes for five minutes."""
    from .calibration import discover_source_machines
    key = hashlib.sha256(json.dumps({"kind":"source-inventory-v1","host":settings.source_db_host,
        "database":settings.source_db_name,"table":settings.source_table,"machine":settings.source_machine_column,
        "timestamp":settings.source_timestamp_column},sort_keys=True).encode()).hexdigest()
    def existing():
        with connection() as conn:
            row = conn.execute(text(f"SELECT payload,checked_at FROM {TABLE} WHERE day_key=:key AND module=0"),{"key":key}).mappings().first()
        if row:
            stamp = row["checked_at"] if isinstance(row["checked_at"],datetime) else datetime.fromisoformat(row["checked_at"])
            if stamp >= now()-INVENTORY_TTL: return json.loads(gzip.decompress(row["payload"]))
        return None
    result = existing()
    if result is not None: return result
    with fill_lock(key):
        result = existing()
        if result is not None: return result
        result = discover_source_machines(settings)
        if result:
            with connection() as conn:
                conn.execute(text(f"DELETE FROM {TABLE} WHERE day_key=:key AND module=0"),{"key":key})
                conn.execute(text(f"INSERT INTO {TABLE}(day_key,module,checked_at,payload,source_revision) VALUES(:key,0,:stamp,:payload,'inventory')"),
                    {"key":key,"stamp":now(),"payload":gzip.compress(json.dumps(result,default=str).encode(),compresslevel=1)})
        return result
