"""OUR EA Strategy Core (§7 architecture, §10-§13 rules, §14-§17 runtime).

Tick-driven decision loop binding the frozen behavioral model to
execution:

  on_tick(prices) -> decisions via VERIFIED rules only
                   -> PARTIAL rules behind hypothesis_id
                   -> UNKNOWN rules -> MODEL_UNCERTAINTY + safe policy
                   -> Risk Guard gate -> ExecutionIntent -> Adapter

Model version is verified against the frozen contract at construction;
mismatch raises ModelVersionMismatch and execution never starts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from core.our_ea.config import OurEaConfig
from core.our_ea.contract import ModelVersion, ModelVersionMismatch, contract_version
from core.our_ea.rule_registry import (RuleRegistry, ModelUncertainty,
                                       UNCERTAINTY_REQUIRED_EVIDENCE,
                                       RULE_PARTIAL_EXISTS)
from core.our_ea.state_machine import StateMachine, SAFE_STOP
from core.our_ea.events import EventLog
from core.our_ea.basket import Basket, PositionRef, BasketAccounting, make_cycle_id
from core.our_ea.lot_engine import LotEngine, LotConfig
from core.our_ea.grid_engine import GridEngine, GridConfig
from core.our_ea.partial_engine import (BasketCloseEngine, BasketTriggerConfig,
                                        PartialEngine, PartialDecisionUnavailable)
from core.our_ea.broker_constraints import (BrokerProfile, normalize_volume,
                                             IdempotencyLedger, IdempotencyKey)
from core.our_ea.risk_guard import RiskGuard, RiskLimits
from core.our_ea.execution import (ExecutionAdapter, ExecutionIntent,
                                   ExecutionResult)


class StrategyCore:
    def __init__(self, config: OurEaConfig, adapter: ExecutionAdapter,
                 event_log: EventLog, registry: RuleRegistry,
                 state_store=None, clock=None):
        self.config = config.validate()
        self.registry = registry
        self.adapter = adapter
        self.log = event_log
        self.store = state_store
        self.clock = clock or (lambda: datetime.now().isoformat(timespec="milliseconds"))

        # §8: bind + verify model version (runtime cannot change it)
        self.model_version: ModelVersion = registry.model_version
        bound = contract_version()
        if (self.model_version.model_id, self.model_version.model_hash) != \
                (bound.model_id, bound.model_hash):
            raise ModelVersionMismatch(bound, self.model_version)

        # engines from config
        self.lot_engine = LotEngine(LotConfig(**config.lot))
        self.grid_engine = GridEngine(GridConfig(**config.grid))
        self.close_engine = BasketCloseEngine(BasketTriggerConfig(**config.basket))
        self.partial_engine = PartialEngine()
        self.accounting = BasketAccounting(config.broker.get("contract_size", 1.0))
        self.broker = BrokerProfile(**config.broker)
        self.risk = RiskGuard(RiskLimits(
            **{k: (tuple(v) if k == "allowed_symbols" and isinstance(v, list) else v)
               for k, v in config.risk.items()
               if k in RiskLimits.__dataclass_fields__}))
        self.idem = IdempotencyLedger()

        # runtime state
        self.sm = StateMachine(self.model_version.model_id)
        self.cycle_sequence = 0
        self.basket: Optional[Basket] = None
        self.position_pl: Dict[str, float] = {}
        self.realized_gross = 0.0
        self.tick_no = 0
        self.uncertainties: List[ModelUncertainty] = []
        self.sm.transition("INIT", condition="startup",
                           reason="strategy core constructed",
                           trace_id=self._trace())
        self.sm.transition("INIT_OK", condition="contract hash verified",
                           reason=f"model {self.model_version.model_hash[:12]}…",
                           trace_id=self._trace())
        self._persist()

    # ------------------------------------------------------------------ ids
    def _trace(self) -> str:
        return f"T{self.tick_no:08d}"

    def _key(self, event_type: str) -> tuple:
        return IdempotencyKey.build(self.config.account, self.config.symbol,
                                    self.basket.cycle_id if self.basket else "-",
                                    event_type, self.tick_no)

    # ------------------------------------------------------------------ tick
    def on_tick(self, buy_price: float, sell_price: float,
                spread_usd: float = 0.0) -> Dict:
        """Process one market tick. Prices are the executable prices per
        side (BUY fills at buy_price, SELL fills at sell_price)."""
        self.tick_no += 1
        prices = {"BUY": buy_price, "SELL": sell_price}
        trace = self._trace()

        if self.sm.state in (SAFE_STOP,):
            return self._diag("safe_stop")

        # risk: loss / drawdown surveillance on open basket
        if self.basket and not self.basket.is_flat():
            floating = self.accounting.floating(self.basket, prices)
            equity_view = -floating        # simplistic surveillance view
            loss = self.risk.check_loss(floating)
            em = self.risk.emergency_policy(
                floating_usd=floating, equity=max(equity_view, 1e-9),
                grid_depth=max(len(self.basket.levels("BUY")),
                               len(self.basket.levels("SELL"))),
                margin_used=0.0)
            if em.emergency_stop:
                self._emit("SAFE_STOP", reason=";".join(em.violations),
                           state_after=SAFE_STOP, trace_id=trace)
                self.sm.transition("SAFE_STOP", reason="OUR_EA policy",
                                   trace_id=trace)
                self._persist()
                return self._diag("emergency_policy_stop")
            if loss.violations:
                self._emit("RISK_BLOCK", reason=";".join(loss.violations),
                           trace_id=trace)

        # flat -> open a new cycle (R-BOTH-SIDES: initial BUY+SELL pair)
        if self.basket is None or self.basket.is_flat():
            if self.basket is not None:
                self._finish_cycle(prices, trace)
            self._open_cycle(prices, spread_usd, trace)
            return self._diag("cycle_opened")

        # basket running -> evaluate grid adds per side (VERIFIED direction)
        for side in ("BUY", "SELL"):
            self._maybe_grid_add(side, prices, spread_usd, trace)

        # basket close evaluation (PARTIAL trigger -> hypothesis recorded)
        floating = self.accounting.floating(self.basket, prices)
        ev = self.close_engine.evaluate(floating, self.basket.total_lots(),
                                        self.realized_gross)
        if ev.should_close:
            self._close_basket(prices, trace, ev.hypothesis_id,
                               ev.threshold, ev.watched_value)
            return self._diag("basket_closed")

        # partial close: only if explicitly enabled; UNKNOWN rules ->
        # MODEL_UNCERTAINTY + safe skip (never guessed as V1.68)
        if self.config.partial.get("enabled"):
            try:
                self.partial_engine.decide_trigger(floating,
                                                   self.basket.total_lots())
            except PartialDecisionUnavailable as ex:
                self._uncertainty(RULE_PARTIAL_EXISTS, state=self.sm.state,
                                  reason=str(ex), trace_id=trace)
        return self._diag("tick")

    # ------------------------------------------------------------- actions
    def _open_cycle(self, prices: Dict[str, float], spread_usd: float,
                    trace: str) -> None:
        key = self._key("OPEN_BOTH")
        if not self.idem.check_and_record(key):
            self._emit("DUPLICATE_EVENT", reason="open-cycle duplicate",
                       trace_id=trace)
            return
        self.cycle_sequence += 1
        cid = make_cycle_id(self.config.account, self.config.symbol,
                            self.cycle_sequence)
        self.basket = Basket(cid, self.clock())
        self.realized_gross = 0.0
        self.position_pl = {}
        before = self.sm.state
        self.sm.transition("OPEN_BOTH", condition="flat + both-sides rule",
                            reason="R-BOTH-SIDES VERIFIED (99.4%)",
                            rule_id="R-BOTH-SIDES", trace_id=trace)
        self._emit("CYCLE_OPEN", state_before=before, state_after=self.sm.state,
                   cycle_id=cid, basket_id=self.basket.basket_id,
                   trace_id=trace, rule_id="R-BOTH-SIDES", evidence_ref="E015")
        for side in ("BUY", "SELL"):
            self._submit_entry(side, prices[side], level=1,
                               rule_id="R-BASE-LOT", spread_usd=spread_usd,
                               trace=trace)
        self._persist()

    def _maybe_grid_add(self, side: str, prices: Dict[str, float],
                        spread_usd: float, trace: str) -> None:
        lv = self.basket.levels(side)
        prev = lv[-1].entry_price if lv else None
        open_prices = [p.entry_price for p in lv] or [prices[side]]
        dec = self.grid_engine.evaluate(side, prices[side], open_prices, prev)
        if not dec.should_add:
            return
        level = self.basket.next_level(side)
        lot = self.lot_engine.lot(level)
        total_after = self.basket.total_lots() + lot
        guard = self.risk.check_entry(
            open_positions=len(self.basket.positions),
            side_levels=len(lv), total_lot_after=total_after,
            spread_usd=spread_usd, symbol=self.config.symbol)
        if not guard.allowed:
            self._emit("RISK_BLOCK", side=side, level=level,
                       reason=";".join(guard.violations), trace_id=trace)
            return
        if self.sm.state in ("BOTH_SIDES_ACTIVE", "GRID_ACTIVE", "LONG_ACTIVE",
                             "SHORT_ACTIVE"):
            if self.sm.can("GRID_ADD"):
                self.sm.transition("GRID_ADD",
                                   reason=f"spacing {self.config.grid['step_usd']}",
                                   rule_id="R-GRID-DIRECTION", trace_id=trace)
        self._submit_entry(side, prices[side], level=level,
                           rule_id="R-GRID-DIRECTION", spread_usd=spread_usd,
                           trace=trace, hypothesis_id=dec.hypothesis_id,
                           trigger_price=dec.trigger_price)

    def _submit_entry(self, side: str, price: float, level: int,
                      rule_id: str, spread_usd: float, trace: str,
                      hypothesis_id: str = "", trigger_price: float = 0.0) -> None:
        lot_dec = self.lot_engine.decide(level)
        vol = normalize_volume(lot_dec.raw_lot, self.broker)
        if not vol.valid:
            self._emit("ORDER_REJECTED", side=side, level=level,
                       reason=f"ORDER_VOLUME_INVALID {vol.reason}",
                       trace_id=trace)
            return
        guard = self.risk.check_entry(
            open_positions=len(self.basket.positions),
            side_levels=len(self.basket.levels(side)),
            total_lot_after=self.basket.total_lots() + vol.normalized,
            spread_usd=spread_usd, symbol=self.config.symbol)
        if not guard.allowed:
            self._emit("RISK_BLOCK", side=side, level=level,
                       reason=";".join(guard.violations), trace_id=trace)
            return
        intent = ExecutionIntent(
            intent_id=f"I{self.tick_no:08d}-{side}-{level}",
            action="OPEN", symbol=self.config.symbol, side=side,
            lot=vol.normalized, price=None, cycle_id=self.basket.cycle_id,
            rule_id=rule_id, hypothesis_id=hypothesis_id,
            reason=f"level {level} lot {vol.normalized} "
                   f"(trigger {trigger_price})" if trigger_price else
                   f"level {level}",
            trace_id=trace)
        res = self.adapter.submit(intent, market_price=price)
        if res.status != "FILLED":
            self._emit("ORDER_REJECTED", side=side, level=level, lot=vol.normalized,
                       reason=res.reason, trace_id=trace)
            return
        self.basket.add(PositionRef(
            position_id=res.position_id, side=side, lot=res.filled_lot,
            entry_price=res.price, level=level, opened_at=self.clock()))
        self._emit("ENTRY" if level == 1 else "GRID_ADD",
                   side=side, lot=res.filled_lot, price=res.price, level=level,
                   cycle_id=self.basket.cycle_id,
                   basket_id=self.basket.basket_id,
                   position_id=res.position_id, rule_id=rule_id,
                   hypothesis_id=hypothesis_id,
                   execution_mode=self.adapter.mode, trace_id=trace)

    def _close_basket(self, prices: Dict[str, float], trace: str,
                      hypothesis_id: str, threshold: float,
                      watched: float) -> None:
        before = self.sm.state
        self.sm.transition("BASKET_INTENT",
                           reason=f"hypothesis {hypothesis_id} thr {threshold}",
                           rule_id="R-BASKET-TRIGGER", trace_id=trace)
        self.sm.transition("CLOSE_START", trace_id=trace)
        closed_pl = []
        for p in list(self.basket.positions):
            intent = ExecutionIntent(
                intent_id=f"I{self.tick_no:08d}-CLOSE-{p.position_id}",
                action="CLOSE", symbol=self.config.symbol,
                side="SELL" if p.side == "BUY" else "BUY",
                lot=p.lot, price=None, cycle_id=self.basket.cycle_id,
                position_id=p.position_id, rule_id="R-BASKET-TRIGGER",
                hypothesis_id=hypothesis_id,
                reason=f"basket close at {watched:+.2f} >= {threshold}",
                trace_id=trace)
            fill_px = prices["SELL" if p.side == "BUY" else "BUY"]
            res = self.adapter.submit(intent, market_price=fill_px)
            if res.status != "FILLED":
                self._emit("ORDER_REJECTED", reason=res.reason,
                           trace_id=trace)
                self.sm.transition("CLOSE_FAIL", trace_id=trace)
                self._uncertainty("R-BASKET-TRIGGER", self.sm.state,
                                  "close order rejected mid-burst", trace)
                return
            closed = self.basket.close_position(p.position_id)
            pl = self.accounting.position_pl(closed.side, closed.entry_price,
                                             res.price, closed.lot)
            closed_pl.append(pl)
            self._emit("BASKET_CLOSE", side=closed.side, lot=closed.lot,
                       price=res.price, position_id=closed.position_id,
                       cycle_id=self.basket.cycle_id,
                       basket_id=self.basket.basket_id,
                       rule_id="R-BASKET-TRIGGER", hypothesis_id=hypothesis_id,
                       execution_mode=self.adapter.mode, trace_id=trace,
                       reason=f"pl {pl:+.2f}")
        self.realized_gross += sum(closed_pl)
        self.sm.transition("CLOSED_ALL", trace_id=trace)
        self._emit("CYCLE_END", state_before=before, state_after=self.sm.state,
                   cycle_id=self.basket.cycle_id,
                   basket_id=self.basket.basket_id,
                   rule_id="R-BASKET-TRIGGER", hypothesis_id=hypothesis_id,
                   reason=f"realized this cycle {sum(closed_pl):+.2f}",
                   execution_mode=self.adapter.mode, trace_id=trace)
        # R-NORMAL-RESUME (VERIFIED <=2s): resume waiting immediately
        self.sm.transition("RESUME_NEW_CYCLE",
                           reason="normal resume <=2s VERIFIED (E018)",
                           rule_id="R-NORMAL-RESUME", trace_id=trace)
        self._persist()

    def _finish_cycle(self, prices: Dict[str, float], trace: str) -> None:
        self.basket = None

    # ------------------------------------------------------------- helpers
    def _uncertainty(self, rule_id: str, state: str, reason: str,
                     trace: str) -> ModelUncertainty:
        u = ModelUncertainty(
            timestamp=self.clock(), model_version=self.model_version.model_id,
            rule_id=rule_id, state=state, reason=reason,
            required_evidence=UNCERTAINTY_REQUIRED_EVIDENCE.get(rule_id, "n/a"),
            execution_mode=self.adapter.mode, trace_id=trace)
        self.uncertainties.append(u)
        self._emit("MODEL_UNCERTAINTY", reason=reason, rule_id=rule_id,
                   execution_mode=self.adapter.mode, trace_id=trace)
        return u

    def _emit(self, event_type: str, **kw) -> None:
        kw.setdefault("account", self.config.account)
        kw.setdefault("symbol", self.config.symbol)
        kw.setdefault("cycle_id", self.basket.cycle_id if self.basket else "")
        kw.setdefault("basket_id",
                      self.basket.basket_id if self.basket else "")
        kw.setdefault("state_before", self.sm.state)
        kw.setdefault("state_after", self.sm.state)
        kw.setdefault("execution_mode", self.adapter.mode)
        self.log.emit(event_type=event_type, **kw)

    def _persist(self) -> None:
        if self.store is None:
            return
        from core.our_ea.persistence import snapshot
        last = self.log.all()[-1] if self.log.all() else None
        self.store.save(snapshot(
            model_version=self.model_version.model_id,
            model_hash=self.model_version.model_hash,
            config_version=self.config.schema,
            execution_mode=self.adapter.mode,
            state_machine_state=self.sm.state,
            basket=self.basket or Basket("-"),
            cycle_sequence=self.cycle_sequence,
            last_event_id=last.event_id if last else "",
            last_event_ts=last.timestamp if last else "",
            risk_state=self.risk.snapshot()["state"],
            account=self.config.account, symbol=self.config.symbol))

    def _diag(self, phase: str) -> Dict:
        d = {"phase": phase, "tick": self.tick_no, "state": self.sm.state,
             "cycle_sequence": self.cycle_sequence,
             "model_version": self.model_version.model_id,
             "model_hash": self.model_version.model_hash[:16],
             "execution_mode": self.adapter.mode,
             "uncertainties": len(self.uncertainties)}
        if self.basket:
            d["basket"] = self.basket.summary()
        return d
