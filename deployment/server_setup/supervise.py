"""One Windows task per service, with process exclusion, rotating logs and backoff."""
import argparse
import ctypes
from ctypes import wintypes
import logging
from logging.handlers import RotatingFileHandler
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time


def kill_on_close_job():
    """Windows kills children when a task/supervisor ends, avoiding orphan workers."""
    class Limits(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                    ('flags', wintypes.DWORD), ('minimum_ws', ctypes.c_size_t),
                    ('maximum_ws', ctypes.c_size_t), ('active_processes', wintypes.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                    ('scheduling', wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ['read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes']]
    class Extended(ctypes.Structure):
        _fields_ = [('limits', Limits), ('io', IO), ('process_memory', ctypes.c_size_t),
                    ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t),
                    ('peak_job', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    info = Extended()
    info.limits.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not job or not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    return kernel, job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('service', choices=['api', 'worker'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    from dotenv import load_dotenv
    load_dotenv(root / '.env', override=True)
    logs = root / 'runtime/server-logs'
    logs.mkdir(parents=True, exist_ok=True)
    lock = (logs / (args.service + '.lock')).open('a+b')
    lock.seek(0)
    if not lock.read(1):
        lock.write(b'0')
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return  # Already supervised; never start a second scheduler.
    (logs / (args.service + '-supervisor.pid')).write_text(str(os.getpid()), encoding='ascii')
    log = logging.getLogger(args.service)
    log.setLevel(logging.INFO)
    handler = RotatingFileHandler(logs / (args.service + '.log'), maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    log.addHandler(handler)
    command = ([sys.executable, '-m', 'uvicorn', 'deployment.server_setup.asgi:app', '--host', '127.0.0.1', '--port', '8000', '--workers', '1']
               if args.service == 'api' else [sys.executable, '-m', 'apps.api.app.worker', '--detector-only'])
    backoff = 5
    kernel, job = kill_on_close_job()
    while True:
        started = time.monotonic()
        log.info('Starting %s', args.service)
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding='utf-8', errors='replace',
                                 env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1'},
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        if not kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(child._handle))):
            child.terminate()
            child.wait(timeout=30)
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            for line in child.stdout:
                log.info('%s', line.rstrip())
            code = child.wait()
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=30)
        log.warning('%s stopped: exit %s; restarting in %ss', args.service, code, backoff)
        if time.monotonic() - started > 300:
            backoff = 5
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


if __name__ == '__main__':
    main()
