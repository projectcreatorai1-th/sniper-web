"""Application state shared by all GUI pages (GUI-free data lives in core)."""
from __future__ import annotations

import os
from typing import Optional

from core.assumptions import AssumptionRegistry, default_registry
from core.backtest_analysis import BacktestAnalysis, analyze_backtest
from core.backtest_io import BacktestSummary
from core.config import EAConfig
from core.model_rules import ModelVersionStore, SimulationModelRules
from core.risk import RiskThresholds
from core.sessions import SessionStore, TestSession
from core.setbuilder import SetStore
from core.symbol_profile import AccountSettings, SymbolProfile


class AppState:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        os.makedirs(self.data_dir, exist_ok=True)

        self.capital: float = 500.0
        self.config = EAConfig()
        self.profile = SymbolProfile()
        self.account = AccountSettings()
        self.thresholds = RiskThresholds()

        self.model_store = ModelVersionStore(os.path.join(self.data_dir, "model_versions.json"))
        self.registry: AssumptionRegistry = default_registry()
        self.set_store = SetStore(os.path.join(self.data_dir, "sets.json"))
        self.session_store = SessionStore(os.path.join(self.data_dir, "sessions"))

        self.backtest_summary: Optional[BacktestSummary] = None
        self.backtest_analysis: Optional[BacktestAnalysis] = None

        self.project_path: Optional[str] = None
        self.dirty = False
        self.current_session: Optional[TestSession] = None
        # subscribers refresh on state change
        self._listeners = []

    # ------------------------------------------------------------------
    def rules(self) -> SimulationModelRules:
        return self.model_store.active_rules()

    def reload_rules(self) -> None:
        # rules are re-read from store each access; kept for API clarity
        pass

    # -- backtest -------------------------------------------------------
    def set_backtest(self, summary: BacktestSummary) -> BacktestAnalysis:
        self.backtest_summary = summary
        self.backtest_analysis = analyze_backtest(summary)
        return self.backtest_analysis

    # -- change notification ----------------------------------------------
    def add_listener(self, fn) -> None:
        self._listeners.append(fn)

    def notify_changed(self) -> None:
        self.dirty = True
        for fn in self._listeners:
            try:
                fn()
            except Exception:
                pass

    # -- project save/load --------------------------------------------------
    def to_project_data(self):
        from core.report import ProjectData
        return ProjectData(
            capital=self.capital,
            config=self.config.to_dict(),
            symbol_profile=self.profile.to_dict(),
            account=self.account.to_dict(),
            risk_thresholds=self.thresholds.to_dict(),
            model_rules=self.rules().to_dict(),
            backtest_summary=self.backtest_summary.to_dict() if self.backtest_summary else None,
            saved_sets_names=self.set_store.names(),
        )

    def load_project_data(self, data) -> None:
        from core.report import ProjectData
        self.capital = float(data.capital or 500.0)
        self.config = EAConfig.from_dict(data.config or {})
        self.profile = SymbolProfile.from_dict(data.symbol_profile or {})
        self.account = AccountSettings.from_dict(data.account or {})
        self.thresholds = RiskThresholds.from_dict(data.risk_thresholds or {})
        if data.backtest_summary:
            self.backtest_summary = BacktestSummary.from_dict(data.backtest_summary)
            self.backtest_analysis = analyze_backtest(self.backtest_summary)
        else:
            self.backtest_summary = None
            self.backtest_analysis = None
        self.notify_changed()

    def reset(self) -> None:
        self.capital = 500.0
        self.config = EAConfig()
        self.profile = SymbolProfile()
        self.account = AccountSettings()
        self.thresholds = RiskThresholds()
        self.backtest_summary = None
        self.backtest_analysis = None
        self.project_path = None
        self.notify_changed()
