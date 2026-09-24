"""MT5 Trade History report loader (xlsx, five sections).

Parses Positions / Orders / Deals / Open Positions / Results tables from
the single-sheet xlsx that MT5 exports, with file hashing for provenance.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import List, Optional

SECTION_NAMES = ("Positions", "Orders", "Deals", "Open Positions", "Results")


def _sf(v) -> float:
    if v is None:
        return 0.0
    s = str(v).strip()
    if "/" in s:
        s = s.split("/")[0].strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _ss(v) -> str:
    return str(v).strip() if v is not None else ""


@dataclass(frozen=True)
class Position:
    ticket: str
    side: str
    volume: float
    open_time: str
    open_price: float
    close_time: str
    close_price: float
    commission: float
    swap: float
    profit: float

    @property
    def net(self) -> float:
        return self.profit + self.commission + self.swap


@dataclass(frozen=True)
class Order:
    order_id: str
    side: str
    vol_req: float
    vol_filled: float
    price_type: str
    time: str
    fill_time: str
    state: str
    comment: str


@dataclass(frozen=True)
class Deal:
    deal_id: str
    side: str
    direction: str          # in / out
    volume: float
    price: float
    time: str
    order_id: str
    commission: float
    fee: float
    swap: float
    profit: float
    balance: float
    comment: str


@dataclass(frozen=True)
class MT5Report:
    account_id: str
    account_line: str
    sha256: str
    source_path: str
    positions: List[Position]
    orders: List[Order]
    deals: List[Deal]
    open_positions: List[dict]
    balance_rows: List[dict]

    @property
    def in_deals(self) -> List[Deal]:
        return [d for d in self.deals if d.direction == "in"]

    @property
    def out_deals(self) -> List[Deal]:
        return [d for d in self.deals if d.direction == "out"]


def _find_sections(rows):
    marks = {}
    for i, r in enumerate(rows):
        v = _ss(r[0]) if r else ""
        if v in SECTION_NAMES:
            marks.setdefault(v, i)
    return marks


def load_report(path: str, account_id: Optional[str] = None) -> MT5Report:
    import openpyxl
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest().upper()
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if account_id is None:
        account_id = os.path.splitext(os.path.basename(path))[0].replace("ReportHistory-", "")
    account_line = _ss(rows[2][3]) if len(rows) > 2 else ""

    marks = _find_sections(rows)
    p_end = marks.get("Orders", len(rows))
    o_end = marks.get("Deals", len(rows))
    d_end = marks.get("Open Positions", len(rows))
    op_end = marks.get("Results", len(rows))

    positions = []
    for r in rows[7:p_end]:
        if _ss(r[2]) != "GOLDmicro":
            continue
        vol = _sf(r[4])
        if vol <= 0:
            continue
        positions.append(Position(
            ticket=_ss(r[1]),
            side="BUY" if _ss(r[3]).lower() == "buy" else "SELL",
            volume=vol, open_time=_ss(r[0]), open_price=_sf(r[5]),
            close_time=_ss(r[8]), close_price=_sf(r[9]),
            commission=_sf(r[10]), swap=_sf(r[11]), profit=_sf(r[12])))

    orders = []
    for r in rows[marks.get("Orders", 0) + 2:o_end]:
        if _ss(r[2]) != "GOLDmicro":
            continue
        vols = _ss(r[4])
        req, filled = (_sf(x) for x in vols.split("/")) if "/" in vols else (_sf(vols), _sf(vols))
        orders.append(Order(
            order_id=_ss(r[1]),
            side="BUY" if _ss(r[3]).lower() == "buy" else "SELL",
            vol_req=req, vol_filled=filled, price_type=_ss(r[5]),
            time=_ss(r[0]), fill_time=_ss(r[8]), state=_ss(r[9]),
            comment=_ss(r[11]) if len(r) > 11 else ""))

    deals, balance_rows = [], []
    for r in rows[marks.get("Deals", 0) + 2:d_end]:
        if _ss(r[2]) != "GOLDmicro":
            if _ss(r[3]) in ("balance", "credit"):
                balance_rows.append({"time": _ss(r[0]), "type": _ss(r[3]),
                                     "profit": _sf(r[11]), "balance": _sf(r[12]),
                                     "comment": _ss(r[13]) if len(r) > 13 else ""})
            continue
        deals.append(Deal(
            deal_id=_ss(r[1]),
            side="BUY" if _ss(r[3]).lower() == "buy" else "SELL",
            direction=_ss(r[4]), volume=_sf(r[5]), price=_sf(r[6]),
            time=_ss(r[0]), order_id=_ss(r[7]),
            commission=_sf(r[8]), fee=_sf(r[9]), swap=_sf(r[10]),
            profit=_sf(r[11]), balance=_sf(r[12]),
            comment=_ss(r[13]) if len(r) > 13 else ""))

    open_positions = []
    for r in rows[marks.get("Open Positions", 0) + 2:op_end]:
        if _ss(r[2]) != "GOLDmicro":
            continue
        if _sf(r[4]) <= 0:
            continue
        open_positions.append({"ticket": _ss(r[1]), "side": _ss(r[3]),
                               "volume": _sf(r[4]), "open_time": _ss(r[0]),
                               "open_price": _sf(r[5]), "profit": _sf(r[11]),
                               "comment": _ss(r[12]) if len(r) > 12 else ""})

    return MT5Report(account_id=account_id, account_line=account_line, sha256=sha,
                     source_path=os.path.abspath(path), positions=positions,
                     orders=orders, deals=deals, open_positions=open_positions,
                     balance_rows=balance_rows)
