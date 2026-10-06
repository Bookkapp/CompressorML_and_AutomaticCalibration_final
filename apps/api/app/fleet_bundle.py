"""Checksum verified, JSON-only Fleet packages and atomic Shadow pointers."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from functools import lru_cache
import zipfile

from .fleet_stable import FrozenFleet, SCHEMA, SEMANTICS

FILES = frozenset({"models.json", "priors.json", "curation.json", "provenance.json", "validation.json", "README.md"})
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 48 * 1024 * 1024
ID = re.compile(r"^fleet-stable-v1-[0-9a-f]{24}$")


def atomic_replace(source,target):
    # Windows scanners/sync clients or short-lived readers can temporarily
    # deny rename. Keep atomic semantics; never copy into the selected folder.
    for attempt in range(6):
        try:os.replace(source,target);return
        except PermissionError:
            if attempt==5:raise
            time.sleep(.1*(attempt+1))


def cleanup_staging(staging,root):
    if not staging.exists():return
    resolved=staging.resolve();resolved.relative_to(Path(root).resolve())
    if staging.is_symlink() or not staging.name.startswith(('.bundle-','.install-')):
        raise ValueError('refuse cleanup outside owned staging directory')
    shutil.rmtree(resolved)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bundle_identity(manifest):
    return "fleet-stable-v1-" + digest(canonical({k: v for k, v in manifest.items() if k != "bundle_id"}))[:24]


def _validate_bytes(payloads):
    if set(payloads) != FILES | {"manifest.json"} or any(len(v) > MAX_FILE for v in payloads.values()) or sum(map(len, payloads.values())) > MAX_TOTAL:
        raise ValueError("invalid bundle inventory or bounded size")
    manifest = json.loads(payloads["manifest.json"])
    if manifest.get("schema") != SCHEMA or manifest.get("semantics") != SEMANTICS:
        raise ValueError("incompatible Fleet bundle schema")
    if manifest.get("release_state") != "FROZEN_SHADOW_CANDIDATE" or manifest.get("alert_vote") is not False:
        raise ValueError("Fleet v1 supports Shadow only")
    if set(manifest.get("files", {})) != FILES or manifest.get("bundle_id") != bundle_identity(manifest):
        raise ValueError("invalid bundle identity/inventory")
    for name in FILES:
        if digest(payloads[name]) != manifest["files"][name]["sha256"] or len(payloads[name]) != manifest["files"][name]["bytes"]:
            raise ValueError(f"Fleet checksum mismatch: {name}")
    fleet = FrozenFleet(manifest, json.loads(payloads["models.json"]), json.loads(payloads["priors.json"]),json.loads(payloads['curation.json']))
    return fleet


def read_package(path):
    path = Path(path)
    if path.is_dir():
        if {p.name for p in path.iterdir()} != FILES | {"manifest.json"}:
            raise ValueError("unexpected bundle contents")
        if any(p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FILE for p in path.iterdir()):
            raise ValueError("regular bounded bundle files required")
        if sum(p.stat().st_size for p in path.iterdir())>MAX_TOTAL:
            raise ValueError('bundle total size limit')
        return {name: (path/name).read_bytes() for name in FILES | {"manifest.json"}}
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) != len(FILES)+1 or {e.filename for e in entries} != FILES | {"manifest.json"}:
            raise ValueError("flat JSON-only bundle ZIP required")
        if any(e.file_size > MAX_FILE or e.is_dir() for e in entries) or sum(e.file_size for e in entries) > MAX_TOTAL:
            raise ValueError("bundle size limit")
        return {e.filename: archive.read(e) for e in entries}


def load_package(path):
    return _validate_bytes(read_package(path))


def write_package(directory, payloads, *, metadata):
    """Training-side writer. Returns a deterministic, content-addressed package."""
    if set(payloads) != FILES:
        raise ValueError("all deployment payloads required")
    data = {name: value if isinstance(value, bytes) else canonical(value) for name, value in payloads.items()}
    manifest = {**metadata, "schema": SCHEMA, "semantics": SEMANTICS,
                "release_state": "FROZEN_SHADOW_CANDIDATE", "alert_vote": False,
                "files": {name: {"sha256": digest(value), "bytes": len(value)} for name, value in sorted(data.items())}}
    manifest["bundle_id"] = bundle_identity(manifest)
    data["manifest.json"] = canonical(manifest)
    _validate_bytes(data)
    root = Path(directory); root.mkdir(parents=True, exist_ok=True)
    path = root/manifest["bundle_id"]
    if path.exists():
        load_package(path)
        return path
    staging = Path(tempfile.mkdtemp(prefix=".bundle-", dir=root))
    try:
        for name, value in data.items():
            (staging/name).write_bytes(value)
        atomic_replace(staging,path)
    finally:
        cleanup_staging(staging,root)
    return path


def export_zip(package, destination):
    data = read_package(package); _validate_bytes(data)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(data.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, value)


@contextmanager
def store_lock(store):
    """Cross-process exclusion with fail-fast conflict; never wait in HTTP."""
    from .file_lock import exclusive_lock
    with exclusive_lock(Path(store)/'.shadow-pointer.lock',message='Fleet store busy; retry after the other deployment completes'):
        yield


def pointer(store):
    path = Path(store)/"shadow.json"
    if not path.exists():
        return {"revision": 0, "bundle_id": None, "previous_bundle_id": None}
    result = json.loads(path.read_bytes())
    if result.get("mode") != "SHADOW" or not ID.fullmatch(result.get("bundle_id", "")) or not isinstance(result.get("revision"), int):
        raise ValueError("invalid frozen Shadow pointer")
    return result


def install(store, package):
    data = read_package(package); fleet = _validate_bytes(data)
    with store_lock(store):
        root = Path(store); target = root/fleet.bundle_id
        if target.exists():
            load_package(target)
            return fleet.bundle_id
        staging = Path(tempfile.mkdtemp(prefix=".install-", dir=root))
        try:
            for name, value in data.items():
                (staging/name).write_bytes(value)
            atomic_replace(staging,target)
        finally:
            cleanup_staging(staging,root)
    return fleet.bundle_id


def switch(store, bundle_id, *, expected_revision, actor, reason):
    if not ID.fullmatch(bundle_id) or not actor.strip() or not reason.strip():
        raise ValueError("valid version, actor and reason required")
    with store_lock(store):
        current = pointer(store)
        if current["revision"] != expected_revision:
            raise ValueError("stale Fleet revision; reread status before switching")
        fleet = load_package(Path(store)/bundle_id)
        if fleet.bundle_id != bundle_id:
            raise ValueError("installed directory identity mismatch")
        if current["bundle_id"] == bundle_id:
            return current
        event = {"revision": expected_revision+1, "bundle_id": bundle_id, "previous_bundle_id": current["bundle_id"],
                 "mode": "SHADOW", "actor": actor, "reason": reason}
        # History is embedded in the same atomic document, so there is no
        # partially committed pointer/history pair after process interruption.
        result = {**event, "history": [*current.get("history", []), event]}
        path = Path(store)/"shadow.json"
        temporary = path.with_suffix(".json.tmp")
        with temporary.open("wb") as stream:
            stream.write(canonical(result)); stream.flush(); os.fsync(stream.fileno())
        atomic_replace(temporary, path)
        return result


@lru_cache(maxsize=4)
def _cached_load(path, signatures):
    return load_package(path)


def current_snapshot(store):
    current = pointer(store)
    if not current["bundle_id"]:
        raise FileNotFoundError("Fleet Stable package is not installed")
    path = Path(store)/current["bundle_id"]
    # Any file revision revalidates ALL checksums, even for warm request caches.
    signatures = tuple((name, (path/name).stat().st_mtime_ns, (path/name).stat().st_size) for name in sorted(FILES | {"manifest.json"}))
    fleet = _cached_load(str(path), signatures)
    if fleet.bundle_id != current["bundle_id"]:
        raise ValueError("Shadow pointer/package identity mismatch")
    return current, fleet


def main():
    parser = argparse.ArgumentParser(description="Install or select a frozen Fleet Shadow package")
    parser.add_argument("--store", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("install"); p.add_argument("package", type=Path)
    p = sub.add_parser("switch"); p.add_argument("bundle_id"); p.add_argument("--expected-revision", type=int, required=True)
    p.add_argument("--actor", required=True); p.add_argument("--reason", required=True)
    sub.add_parser("status")
    args = parser.parse_args()
    if args.command == "install":
        result = {"installed_bundle_id": install(args.store, args.package), "selected": False}
    elif args.command == "switch":
        result = switch(args.store, args.bundle_id, expected_revision=args.expected_revision, actor=args.actor, reason=args.reason)
    else:
        if pointer(args.store)['bundle_id'] is None:
            result={'release_state':'NOT_SELECTED','pointer':pointer(args.store),'alert_vote':False}
        else:
            selected, fleet = current_snapshot(args.store); result = {**fleet.status(), "pointer": selected}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
