# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

# Utility to safely reset TMP directory
import os, shutil, time
from pathlib import Path

def _acquire_lock(lock_path: Path, timeout=5.0, interval=0.1):
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
            return
        except FileExistsError:
            if time.time() - start >= timeout:
                raise TimeoutError("Lock timeout")
            time.sleep(interval)

def _release_lock(lock_path: Path):
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass

def reset_tmp_directory(tmp_dir: Path):
    tmp_path = Path(tmp_dir)
    lock = tmp_path / ".reset.lock"
    tmp_path.mkdir(parents=True, exist_ok=True)
    _acquire_lock(lock)
    try:
        for p in tmp_path.iterdir():
            if p == lock:
                continue
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
    finally:
        _release_lock(lock)
