"""Shared test helpers."""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import EAConfig
from core.symbol_profile import SymbolProfile, AccountSettings
from core.model_rules import SimulationModelRules


def std_ctx():
    """Standard context: default EA config, XAUUSD profile, 1:500 account."""
    return EAConfig(), SymbolProfile(), AccountSettings(), SimulationModelRules()


class TempDirTestMixin:
    """Provides self.tmpdir (auto-cleaned) for store tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="sniper_test_")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
