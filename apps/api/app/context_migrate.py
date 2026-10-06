"""Explicit local analytics migration. Never creates/modifies source tables."""
from sqlalchemy import inspect

from .config import get_settings
from .db import get_engine
from .unified_events import metadata as event_meta
from .context_storage import metadata as day_meta
from .context_reference import metadata as profile_meta
from .context_review import metadata as review_meta
from .operational_inbox import metadata as inbox_meta


def main(*,allow_remote=False):
    settings=get_settings()
    if not allow_remote and settings.analytics_db_host not in {"localhost","127.0.0.1","::1"}:
        raise RuntimeError("This command is scoped to the authorized local analytics database")
    if settings.analytics_db_name==settings.source_db_name:
        raise RuntimeError("Analytics must be separate from the source schema")
    engine=get_engine()
    if engine is None: raise RuntimeError("Analytics database is not configured")
    for meta in (event_meta,day_meta,profile_meta,review_meta,inbox_meta): meta.create_all(engine)
    names=inspect(engine).get_table_names()
    print({"tables":{name:name in names for meta in (event_meta,day_meta,profile_meta,review_meta,inbox_meta) for name in meta.tables},
           "source_written":False})


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description='Additive analytics Context/Event tables; source is never migrated')
    parser.add_argument('--allow-remote',action='store_true',help='Explicit Server deployment opt-in')
    main(allow_remote=parser.parse_args().allow_remote)
