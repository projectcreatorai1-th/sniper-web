"""EX5 integrity record (Phase 1).

Reads ONLY safe metadata (presence, size) and computes hashes from a real
file when one is available. It never modifies, decompiles, reverse
engineers, or copies the .ex5, and never fabricates a hash: hashes marked
RECORDED_EXTERNAL_BASELINE are historical records supplied externally,
clearly separated from anything computed here.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

SCHEMA = "SNIPER_EX5_INTEGRITY_V1"

EX5_FILENAME = "SNIPER CashFlow V 1.68.ex5"
EX5_FORMAT = "EX5 format 2"          # recorded historical metadata
EX5_EA_VERSION = "1.68"

# historical baselines supplied as external records (NOT computed here)
HISTORICAL_SHA256 = "31E5176E794C29BE265EBF1B449B1047F2125C57A1CD227B257F89A54BF9CE37"
HISTORICAL_MD5 = "3972D8436537F36F08FDF1E35C45750A"

SOURCE_FILE_NOT_PRESENT = "SOURCE_FILE_NOT_PRESENT"
INTEGRITY_MATCH = "INTEGRITY MATCH"
INTEGRITY_MISMATCH = "INTEGRITY MISMATCH"


@dataclass
class Ex5IntegrityRecord:
    filename: str = EX5_FILENAME
    file_size: Optional[int] = None
    sha256: Optional[str] = None        # computed from the real file only
    md5: Optional[str] = None           # computed from the real file only
    format: str = EX5_FORMAT
    ea_version: str = EX5_EA_VERSION
    recorded_at: str = ""
    status: str = SOURCE_FILE_NOT_PRESENT
    historical_sha256: str = HISTORICAL_SHA256
    historical_md5: str = HISTORICAL_MD5
    historical_status: str = "RECORDED_EXTERNAL_BASELINE"
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def find_ex5_file(extra_paths: Optional[list] = None) -> Optional[str]:
    """Look for the .ex5 in the project workspace / given evidence locations.
    Never searches outside the provided scope; never touches file content."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(project_root, EX5_FILENAME),
        os.path.join(project_root, "assets", EX5_FILENAME),
        os.path.join(project_root, "data", EX5_FILENAME),
        os.environ.get("SNIPER_EX5_PATH", ""),
        *(extra_paths or []),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def inspect_ex5(path: Optional[str], expected_sha256: str = HISTORICAL_SHA256,
                expected_md5: str = HISTORICAL_MD5) -> Ex5IntegrityRecord:
    """Build the integrity record for the .ex5.

    - file present  -> compute SHA-256/MD5 from the real file, compare with
                       the expected baselines -> INTEGRITY MATCH / MISMATCH
    - file missing  -> status SOURCE_FILE_NOT_PRESENT, no computed hashes,
                       historical baselines kept as RECORDED_EXTERNAL_BASELINE
    """
    rec = Ex5IntegrityRecord(recorded_at=datetime.now().isoformat(timespec="seconds"))
    if not path or not os.path.isfile(path):
        rec.status = SOURCE_FILE_NOT_PRESENT
        rec.notes = ("Source .ex5 not present in this workspace; no fake file is "
                     "created and no hash is fabricated. Historical baselines are "
                     "external records only.")
        return rec

    rec.filename = os.path.basename(path)
    rec.file_size = os.path.getsize(path)
    rec.sha256 = _sha256(path)      # computed from the real file only
    rec.md5 = _md5(path)
    match = (rec.sha256.upper() == expected_sha256.upper()
             and rec.md5.upper() == expected_md5.upper())
    rec.status = INTEGRITY_MATCH if match else INTEGRITY_MISMATCH
    rec.notes = "Hashes computed from the real file; compared with the recorded baseline."
    return rec


def record_ex5_integrity(extra_paths: Optional[list] = None) -> Ex5IntegrityRecord:
    return inspect_ex5(find_ex5_file(extra_paths))
