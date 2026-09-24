"""Tests: EX5 integrity record — hash validation, missing file, mismatch."""
import hashlib
import os
import unittest

from core.ex5_integrity import (
    EX5_FILENAME,
    HISTORICAL_MD5,
    HISTORICAL_SHA256,
    INTEGRITY_MATCH,
    INTEGRITY_MISMATCH,
    SOURCE_FILE_NOT_PRESENT,
    Ex5IntegrityRecord,
    find_ex5_file,
    inspect_ex5,
    record_ex5_integrity,
)
from tests import TempDirTestMixin


class TestMissingFile(TempDirTestMixin, unittest.TestCase):
    def test_workspace_has_no_ex5_by_default(self):
        self.assertIsNone(find_ex5_file())

    def test_missing_file_gives_not_present_without_hash(self):
        rec = inspect_ex5(None)
        self.assertEqual(rec.status, SOURCE_FILE_NOT_PRESENT)
        self.assertIsNone(rec.sha256)      # never fabricated
        self.assertIsNone(rec.md5)
        self.assertIsNone(rec.file_size)

    def test_historical_baseline_kept_as_external_record(self):
        rec = inspect_ex5(None)
        self.assertEqual(rec.historical_sha256, HISTORICAL_SHA256)
        self.assertEqual(rec.historical_md5, HISTORICAL_MD5)
        self.assertEqual(rec.historical_status, "RECORDED_EXTERNAL_BASELINE")

    def test_no_fake_file_created(self):
        record_ex5_integrity()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertFalse(os.path.exists(os.path.join(project_root, EX5_FILENAME)))


class TestRealFileHashing(TempDirTestMixin, unittest.TestCase):
    def _make_file(self, content: bytes, name=EX5_FILENAME) -> str:
        # a REAL test fixture file (not the EA, never named as the EA on disk
        # inside the project): hashes must come from actual bytes only
        path = os.path.join(self.tmpdir, name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_hashes_computed_from_real_bytes(self):
        content = b"phase1 integrity fixture"
        path = self._make_file(content, "fixture.bin")
        rec = inspect_ex5(path)
        self.assertEqual(rec.sha256,
                         hashlib.sha256(content).hexdigest().upper())
        self.assertEqual(rec.md5,
                         hashlib.md5(content).hexdigest().upper())
        self.assertEqual(rec.file_size, len(content))

    def test_match_when_expected_equals_computed(self):
        content = b"fixture"
        path = self._make_file(content, "fixture2.bin")
        rec = inspect_ex5(path,
                          expected_sha256=hashlib.sha256(content).hexdigest(),
                          expected_md5=hashlib.md5(content).hexdigest())
        self.assertEqual(rec.status, INTEGRITY_MATCH)

    def test_mismatch_when_file_differs_from_baseline(self):
        path = self._make_file(b"different bytes entirely", "fixture3.bin")
        rec = inspect_ex5(path)     # expected = historical EA baseline
        self.assertEqual(rec.status, INTEGRITY_MISMATCH)

    def test_extra_path_discovery(self):
        path = self._make_file(b"abc", EX5_FILENAME)
        self.assertEqual(find_ex5_file([path]), path)

    def test_record_serializes(self):
        rec = Ex5IntegrityRecord(status=SOURCE_FILE_NOT_PRESENT)
        d = rec.to_dict()
        self.assertEqual(d["schema"], "SNIPER_EX5_INTEGRITY_V1")
        self.assertIn("historical_sha256", d)


if __name__ == "__main__":
    unittest.main()
