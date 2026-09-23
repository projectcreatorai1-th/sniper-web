"""MT5 Backtest Import (Module 6).

Parses MT5 Strategy Tester output into a BacktestSummary:

  - CSV  : MT5 "Report" / deals export (tab or comma separated,
           UTF-16LE/UTF-8/ANSI tolerant). If the deal list is present the
           summary is COMPUTED from the deals; missing values stay None (=N/A)
  - HTML : MT5 backtest report - parses the summary label/value table and,
           if present, the Deals table for deeper analysis
  - TXT  : plain-text report - regex label/value extraction

Every field that cannot be found or computed is left None and the UI shows
N/A - nothing is invented.
"""
from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import dataclass, field, asdict
from html.parser import HTMLParser
from typing import List, Optional, Tuple

SCHEMA = "SNIPER_BACKTEST_SUMMARY_V1"


@dataclass
class DealRecord:
    time: str
    deal_id: str = ""
    symbol: str = ""
    type: str = ""           # buy / sell / balance ...
    direction: str = ""      # in / out / inout / ""
    volume: float = 0.0
    price: float = 0.0
    order: str = ""
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0
    balance: Optional[float] = None
    comment: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestSummary:
    source_file: str = ""
    source_format: str = ""                 # csv / html / txt
    net_profit: Optional[float] = None
    gross_profit: Optional[float] = None
    gross_loss: Optional[float] = None
    profit_factor: Optional[float] = None
    expected_payoff: Optional[float] = None
    max_drawdown: Optional[float] = None            # absolute value (money)
    max_drawdown_percent: Optional[float] = None
    relative_drawdown: Optional[float] = None       # percent
    trades: Optional[int] = None
    winning_trades: Optional[int] = None
    losing_trades: Optional[int] = None
    largest_profit: Optional[float] = None
    largest_loss: Optional[float] = None
    average_profit: Optional[float] = None
    average_loss: Optional[float] = None
    initial_deposit: Optional[float] = None
    balance_curve: List[float] = field(default_factory=list)   # balance after each closed deal
    deals: List[DealRecord] = field(default_factory=list)
    ea_name: Optional[str] = None
    symbol: Optional[str] = None
    period: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestSummary":
        s = cls()
        deals = d.pop("deals", []) if isinstance(d, dict) else []
        for k, v in (d or {}).items():
            if hasattr(s, k) and v is not None and k != "schema":
                setattr(s, k, v)
        s.deals = [DealRecord(**dd) for dd in deals if isinstance(dd, dict)]
        return s


# ---------------------------------------------------------------------------
# tolerant primitives
# ---------------------------------------------------------------------------
def _read_text(path: str) -> str:
    raw = open(path, "rb").read()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    for enc in ("utf-8", "cp1252", "tis-620"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_number(text: str) -> Optional[float]:
    """Parse '1 234.56', '1,234.56', '1234,56', '-12.34%', '0.00'."""
    if text is None:
        return None
    t = str(text).strip().replace("\xa0", " ").replace("%", "")
    t = t.split("(")[0].strip()
    if not re.search(r"\d", t):
        return None
    t = re.sub(r"\s+", "", t)
    # decide decimal separator: last '.' or ',' wins
    last_dot, last_com = t.rfind("."), t.rfind(",")
    if last_dot > last_com:
        t = t.replace(",", "")
    elif last_com > last_dot:
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _parse_percent_in_parens(text: str) -> Optional[float]:
    m = re.search(r"\(([-\d.,\s]+)%\)", str(text))
    if not m:
        return None
    return _parse_number(m.group(1))


def _detect_dialect(sample: str) -> dict:
    sniffer = csv.Sniffer()
    for delim in ("\t", ";", ","):
        try:
            header = sample.splitlines()[0]
            if header.count(delim) >= 2:
                return {"delimiter": delim}
        except IndexError:
            break
    try:
        return sniffer.sniff(sample, delimiters="\t;,")
    except csv.Error:
        return {"delimiter": ","}


# ---------------------------------------------------------------------------
# CSV parsing (deals export or summary-like csv)
# ---------------------------------------------------------------------------
_COL_ALIASES = {
    "time": {"time", "เวลา", "date", "opens"},
    "deal": {"deal", "deal #", "ticket"},
    "symbol": {"symbol", "สัญลักษณ์", "market"},
    "type": {"type", "ประเภท", "deal type"},
    "direction": {"direction", "ทิศทาง"},
    "volume": {"volume", "lots", "ปริมาณ", "size"},
    "price": {"price", "ราคา"},
    "order": {"order", "order #"},
    "commission": {"commission", "ค่าคอมมิชชั่น"},
    "swap": {"swap", "สว็อป", "storage"},
    "profit": {"profit", "กำไร", "p/l", "net"},
    "balance": {"balance", "ยอดคงเหลือ"},
    "comment": {"comment", "ความคิดเห็น"},
}


def _map_columns(header: List[str]) -> dict:
    mapping = {}
    for idx, col in enumerate(header):
        key = col.strip().lower()
        for canonical, aliases in _COL_ALIASES.items():
            if key in aliases and canonical not in mapping:
                mapping[canonical] = idx
    return mapping


def parse_deals_csv(path: str) -> Tuple[List[DealRecord], List[str]]:
    """Parse an MT5 deals CSV into DealRecords. Returns (records, notes)."""
    text = _read_text(path)
    notes: List[str] = []
    rows: List[List[str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        delim = "\t" if line.count("\t") >= max(line.count(","), line.count(";")) else \
            (";" if line.count(";") > line.count(",") else ",")
        rows.append([c.strip() for c in line.split(delim)])
    if not rows:
        return [], ["empty file"]
    # locate header row: the row containing 'time' and ('profit' or 'volume')
    header_idx, mapping = -1, {}
    for i, row in enumerate(rows[:10]):
        m = _map_columns(row)
        if "time" in m and ("profit" in m or "volume" in m or "balance" in m):
            header_idx, mapping = i, m
            break
    deals: List[DealRecord] = []
    if header_idx < 0:
        notes.append("no recognizable header row - cannot parse deals")
        return deals, notes

    def get(row, canonical) -> str:
        idx = mapping.get(canonical)
        return row[idx] if idx is not None and idx < len(row) else ""

    for row in rows[header_idx + 1:]:
        if not row or not get(row, "time"):
            continue
        # skip separator rows like '-----'
        if re.fullmatch(r"[-=]+", get(row, "time")):
            continue
        deals.append(DealRecord(
            time=get(row, "time"),
            deal_id=get(row, "deal"),
            symbol=get(row, "symbol"),
            type=get(row, "type").lower(),
            direction=get(row, "direction").lower(),
            volume=_parse_number(get(row, "volume")) or 0.0,
            price=_parse_number(get(row, "price")) or 0.0,
            order=get(row, "order"),
            commission=_parse_number(get(row, "commission")) or 0.0,
            swap=_parse_number(get(row, "swap")) or 0.0,
            profit=_parse_number(get(row, "profit")) or 0.0,
            balance=_parse_number(get(row, "balance")),
            comment=get(row, "comment"),
        ))
    if not deals:
        notes.append("header found but no data rows")
    return deals, notes


def summary_from_deals(deals: List[DealRecord], notes: List[str]) -> BacktestSummary:
    """Compute a BacktestSummary from a deal list. Missing info stays None."""
    s = BacktestSummary(notes=list(notes))
    if not deals:
        return s
    balance_deals = [d for d in deals if d.type == "balance"]
    if balance_deals:
        s.initial_deposit = balance_deals[0].profit
    trade_deals = [d for d in deals if d.type in ("buy", "sell")]
    closed = [d for d in trade_deals if d.direction in ("out", "inout")]
    # profit column holds commission/swap-inclusive values in MT5 reports;
    # if all zeros fall back to in+out combined view is impossible -> N/A handled below
    profits = [d.profit + d.commission + d.swap for d in closed] if closed else \
              [d.profit + d.commission + d.swap for d in trade_deals]
    if closed or trade_deals:
        s.trades = len(closed) if closed else len(trade_deals)
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        s.net_profit = round(sum(profits), 2)
        s.gross_profit = round(sum(wins), 2) if wins else 0.0
        s.gross_loss = round(sum(losses), 2) if losses else 0.0
        s.profit_factor = round(s.gross_profit / abs(s.gross_loss), 4) if s.gross_loss else None
        s.expected_payoff = round(s.net_profit / s.trades, 4) if s.trades else None
        s.winning_trades = len(wins)
        s.losing_trades = len(losses)
        s.largest_profit = round(max(profits), 2) if profits else None
        s.largest_loss = round(min(profits), 2) if profits else None
        s.average_profit = round(sum(wins) / len(wins), 4) if wins else None
        s.average_loss = round(sum(losses) / len(losses), 4) if losses else None
    # balance curve + drawdown from running balance column
    balances = [d.balance for d in deals if d.balance is not None]
    if balances:
        s.balance_curve = balances
        peak, max_dd, max_dd_pct = balances[0], 0.0, 0.0
        for b in balances:
            peak = max(peak, b)
            dd = peak - b
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd / peak * 100.0 if peak else 0.0
        s.max_drawdown = round(max_dd, 2)
        s.max_drawdown_percent = round(max_dd_pct, 4)
        s.relative_drawdown = round(max_dd_pct, 4)
        if s.net_profit is None and len(balances) >= 2 and s.initial_deposit:
            s.net_profit = round(balances[-1] - s.initial_deposit, 2)
    else:
        notes.append("no balance column - drawdown and equity curve unavailable (N/A)")
    symbols = {d.symbol for d in deals if d.symbol}
    s.symbol = sorted(symbols)[0] if len(symbols) == 1 else (",".join(sorted(symbols)) or None)
    s.deals = deals
    return s


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------
class _ReportHTMLParser(HTMLParser):
    """Extracts (a) plain text, (b) all <table> rows as cell lists."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts: List[str] = []
        self.tables: List[List[List[str]]] = []
        self._cur_table: Optional[List[List[str]]] = None
        self._cur_row: Optional[List[str]] = None
        self._cur_cell: Optional[List[str]] = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._cur_table = []
        elif tag == "tr" and self._cur_table is not None:
            self._cur_row = []
        elif tag in ("td", "th") and self._cur_row is not None:
            self._cur_cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cur_cell is not None:
            self._cur_row.append("".join(self._cur_cell).strip())
            self._cur_cell = None
        elif tag == "tr" and self._cur_row is not None:
            if self._cur_table is not None:
                self._cur_table.append(self._cur_row)
            self._cur_row = None
        elif tag == "table" and self._cur_table is not None:
            self.tables.append(self._cur_table)
            self._cur_table = None

    def handle_data(self, data):
        self.text_parts.append(data)
        if self._cur_cell is not None:
            self._cur_cell.append(data)

    def plain_text(self) -> str:
        return re.sub(r"[ \t]+", " ", " ".join(self.text_parts))


_LABEL_MAP = [
    ("net_profit", ("total net profit",)),
    ("gross_profit", ("gross profit",)),
    ("gross_loss", ("gross loss",)),
    ("profit_factor", ("profit factor",)),
    ("expected_payoff", ("expected payoff",)),
    ("max_drawdown", ("balance drawdown maximal", "maximal drawdown", "max drawdown")),
    ("relative_drawdown", ("balance drawdown relative", "relative drawdown")),
    ("trades", ("total trades", "trades")),
    ("winning_trades", ("winning trades",)),
    ("losing_trades", ("losing trades", "losing trades (% of total)")),
    ("largest_profit", ("largest profit trade",)),
    ("largest_loss", ("largest loss trade",)),
    ("average_profit", ("average profit trade",)),
    ("average_loss", ("average loss trade",)),
    ("initial_deposit", ("initial deposit",)),
]


def _match_label(label: str, field_name: str) -> bool:
    label_l = label.strip().rstrip(":").lower()
    for prefix in dict(_LABEL_MAP)[field_name]:
        if label_l.startswith(prefix):
            return True
    return False


def parse_html_report(path: str) -> BacktestSummary:
    text = _read_text(path)
    parser = _ReportHTMLParser()
    try:
        parser.feed(text)
    except Exception:
        pass
    summary = BacktestSummary(source_format="html")

    # --- summary from tables: rows of [label, value] or [label, value, x, y]
    for table in parser.tables:
        for row in table:
            if len(row) < 2:
                continue
            for field_name in ("net_profit", "gross_profit", "gross_loss", "profit_factor",
                               "expected_payoff", "max_drawdown", "relative_drawdown",
                               "trades", "winning_trades", "losing_trades", "largest_profit",
                               "largest_loss", "average_profit", "average_loss",
                               "initial_deposit"):
                if summary.__dict__.get(field_name) is not None:
                    continue
                if _match_label(row[0], field_name):
                    val = _parse_number(row[1])
                    if val is not None:
                        summary.__dict__[field_name] = val
                    pct = _parse_percent_in_parens(" ".join(row[1:3]))
                    if pct is not None and field_name in ("max_drawdown", "relative_drawdown"):
                        if field_name == "max_drawdown":
                            summary.max_drawdown_percent = pct
                        summary.relative_drawdown = pct if field_name == "relative_drawdown" else summary.relative_drawdown
    # EA name / symbol / period heuristics from plain text
    pt = parser.plain_text()
    m = re.search(r"Expert Advisor[:\s]+(\S+)", pt, re.I)
    if m:
        summary.ea_name = m.group(1)
    m = re.search(r"Symbol[:\s]+(\S+)", pt, re.I)
    if m:
        summary.symbol = m.group(1)

    # --- deals table (header containing 'deal' + 'time') -> compute richer stats
    deals, notes = [], []
    for table in parser.tables:
        if not table:
            continue
        header = [c.lower() for c in table[0]]
        if any("deal" in h for h in header) and any("time" in h for h in header):
            col_map = _map_columns(table[0])
            if "time" in col_map and ("profit" in col_map or "volume" in col_map):
                for row in table[1:]:
                    def g(c):
                        idx = col_map.get(c)
                        return row[idx] if idx is not None and idx < len(row) else ""
                    if not g("time"):
                        continue
                    deals.append(DealRecord(
                        time=g("time"), deal_id=g("deal"), symbol=g("symbol"),
                        type=g("type").lower(), direction=g("direction").lower(),
                        volume=_parse_number(g("volume")) or 0.0,
                        price=_parse_number(g("price")) or 0.0,
                        order=g("order"),
                        commission=_parse_number(g("commission")) or 0.0,
                        swap=_parse_number(g("swap")) or 0.0,
                        profit=_parse_number(g("profit")) or 0.0,
                        balance=_parse_number(g("balance")),
                        comment=g("comment"),
                    ))
                break
    if deals:
        computed = summary_from_deals(deals, notes)
        # keep explicitly parsed summary values if both exist, prefer computed for curve
        for k, v in computed.__dict__.items():
            if k in ("source_file", "source_format", "notes", "deals"):
                continue
            if v is not None:
                summary.__dict__[k] = v
        summary.deals = deals
    else:
        summary.notes.append("no deals table found - only summary labels parsed")
    return summary


# ---------------------------------------------------------------------------
# TXT parsing
# ---------------------------------------------------------------------------
def parse_txt_report(path: str) -> BacktestSummary:
    text = _read_text(path)
    summary = BacktestSummary(source_format="txt")
    # label: value pairs on one line
    for field_name, _ in _LABEL_MAP:
        if summary.__dict__.get(field_name) is not None:
            continue
        for prefix in dict(_LABEL_MAP)[field_name]:
            m = re.search(re.escape(prefix) + r"\s*[:=]?\s*(-?[\d.,\s]+(?:\([-()\d.,\s%]+\))?)",
                          text, re.I)
            if m:
                val = _parse_number(m.group(1))
                if val is not None:
                    summary.__dict__[field_name] = val
                    pct = _parse_percent_in_parens(m.group(1))
                    if pct is not None and field_name == "max_drawdown":
                        summary.max_drawdown_percent = pct
                break
    if summary.trades is None and summary.net_profit is None:
        summary.notes.append("no recognizable summary fields in text report")
    return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def parse_backtest_file(path: str) -> BacktestSummary:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".htm", ".html"):
        s = parse_html_report(path)
    elif ext == ".csv":
        deals, notes = parse_deals_csv(path)
        s = summary_from_deals(deals, notes)
        if not deals:
            # maybe it's a summary-style csv; try label/value text parse
            txt_summary = parse_txt_report(path)
            for k, v in txt_summary.__dict__.items():
                if v not in (None, [], "") and s.__dict__.get(k) in (None, [], ""):
                    s.__dict__[k] = v
        s.source_format = "csv"
    elif ext in (".txt", ".log"):
        s = parse_txt_report(path)
    else:
        # unknown extension: try HTML then CSV then TXT
        try:
            s = parse_html_report(path)
            s.source_format = "html"
        except Exception:
            try:
                deals, notes = parse_deals_csv(path)
                s = summary_from_deals(deals, notes)
                s.source_format = "csv"
            except Exception:
                s = parse_txt_report(path)
                s.source_format = "txt"
    s.source_file = os.path.basename(path)
    return s
