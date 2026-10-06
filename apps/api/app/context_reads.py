"""Bounded shared inspection cache; coalesce concurrent tabs, never fit here."""
from collections import OrderedDict
from copy import deepcopy
from threading import Event, Lock
from time import monotonic
from .reference_jobs import ReviewConflict

_cache=OrderedDict()
_inflight={}
_lock=Lock()
_wire_cache=OrderedDict()
_wire_bytes=0


def inspection_response(key,fn,*,accept_encoding="",ttl=300):
    """Serialize immutable inspections once, without FastAPI's recursive copy.

    Wire cache is separately bounded by both count and bytes. Mutable internal
    reads still return isolated copies; HTTP callers share only frozen bytes.
    """
    import gzip,json
    from fastapi import Response
    global _wire_bytes
    with _lock:
        saved=_wire_cache.get(key)
        if saved and saved[0]>monotonic():
            _wire_cache.move_to_end(key)
            pair=saved[1]
        else: pair=None
    if pair is None:
        def encode():
            body=json.dumps(fn(),ensure_ascii=False,allow_nan=False,separators=(",",":"),default=str).encode()
            return gzip.compress(body,compresslevel=1,mtime=0)
        pair=shared_read(("wire-fill",key),encode,ttl=ttl)
        size=len(pair)
        with _lock:
            old=_wire_cache.pop(key,None)
            if old:_wire_bytes-=len(old[1])
            _wire_cache[key]=(monotonic()+ttl,pair);_wire_bytes+=size
            # Four machines × eight modules × Reference/day = 64 immutable
            # views. Keep these warm while still enforcing the same byte cap.
            # The separate mutable Raw cache stays at 24 entries.
            while len(_wire_cache)>128 or _wire_bytes>32*1024*1024:
                _,old=_wire_cache.popitem(last=False);_wire_bytes-=len(old[1])
    compressed=False
    for part in accept_encoding.split(","):
        options=part.lower().replace(" ","").split(";")
        if options[0]!="gzip":continue
        try:compressed=next((float(o[2:]) for o in options[1:] if o.startswith("q=")),1)>0
        except ValueError:compressed=False
    headers={"Vary":"Accept-Encoding","Cache-Control":"private, no-cache"}
    if compressed:headers["Content-Encoding"]="gzip"
    return Response(pair if compressed else gzip.decompress(pair),media_type="application/json",headers=headers)


def shared_read(key,fn,*,ttl=60):
    with _lock:
        saved=_cache.get(key)
        if saved and saved[0]>monotonic():
            _cache.move_to_end(key)
            return deepcopy(saved[1])
        flight=_inflight.get(key)
        leader=flight is None
        if leader:
            if len(_inflight)>=32: raise ReviewConflict("INSPECTION_BUSY_RETRY")
            flight=Event();_inflight[key]=flight
    if not leader:
        if not flight.wait(10): raise ReviewConflict("INSPECTION_BUSY_RETRY")
        with _lock:
            saved=_cache.get(key)
            if saved and saved[0]>monotonic(): return deepcopy(saved[1])
        raise ReviewConflict("INSPECTION_BUSY_RETRY")
    try:
        value=fn()
        with _lock:
            _cache[key]=(monotonic()+ttl,value)
            _cache.move_to_end(key)
            while len(_cache)>24: _cache.popitem(last=False)
        return deepcopy(value)
    finally:
        with _lock:
            _inflight.pop(key,None);flight.set()


def cached_raw(settings,machine,module,start,end):
    from .context_storage import source_namespace
    from .reference_raw import READERS,read_raw
    def read():
        if not READERS.acquire(timeout=3): raise ReviewConflict("RAW_READER_BUSY_RETRY")
        try: return read_raw(settings,machine,module,start,end)
        finally: READERS.release()
    return shared_read(("raw",source_namespace(settings),settings.source_pressure_unit,machine,module,start,end),read)
