#!/usr/bin/env python3
"""Audit drift between data/hotel/*.md knowledge files and the live PostgreSQL DB.

This is the deterministic complement to the LLM-as-judge backtest pipeline.
It catches the high-impact "rag_drift" defect (where RAG returns a value
that's stale vs the booking system's actual number) before any model is
involved, and exits non-zero so CI can gate merges on it.

Currently checks:
  • room_types.base_price           vs prices quoted in data/hotel/room_types.md
                                       and data/hotel/room_guide.md
  • hotel_services.price            vs prices quoted in
                                       data/hotel/dining_services.md,
                                       data/hotel/spa_wellness.md,
                                       data/hotel/facilities_amenities.md

Usage:
    python scripts/audit_data_db_drift.py                 # human-readable
    python scripts/audit_data_db_drift.py --json          # JSON output
    python scripts/audit_data_db_drift.py --strict        # exit 1 on any drift

Exit codes:
    0   no drift detected
    1   drift detected (--strict mode) or DB unreachable
    2   internal error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "data" / "hotel"

# Files that mention room prices
ROOM_PRICE_FILES = ["room_types.md", "room_guide.md"]
# Files that mention service prices
SERVICE_PRICE_FILES = ["dining_services.md", "spa_wellness.md", "facilities_amenities.md"]

ROOM_TYPE_ALIASES = {
    "Standard Room": ["Standard Room", "Standard ", "Standard\t", "ห้องสแตนดาร์ด"],
    "Deluxe Room": ["Deluxe Room", "Deluxe ", "Deluxe\t", "ห้องดีลักซ์"],
    "Suite": ["Suite", "ห้องสวีท"],
    "Penthouse": ["Penthouse Suite", "Penthouse", "ห้องเพนท์เฮาส์ สวีท", "ห้องเพนท์เฮาส์"],
}


def _iter_aliases_specific_first():
    """Yield (canonical, alias) sorted by alias-length desc.

    This guarantees 'Penthouse Suite' is checked before 'Suite' so a
    Penthouse section header is not mis-classified as a Suite.
    """
    pairs = [
        (canonical, alias)
        for canonical, aliases in ROOM_TYPE_ALIASES.items()
        for alias in aliases
    ]
    return sorted(pairs, key=lambda p: -len(p[1]))

PRICE_PATTERN = re.compile(
    r"(?P<value>\d{1,3}(?:,\d{3})+|\d{3,6})\s*(?:THB|บาท|泰铢)\b",
    re.IGNORECASE,
)


@dataclass
class DriftRow:
    item: str           # e.g. "Deluxe Room" or "Thai Massage"
    db_price: float
    md_price: float
    md_file: str
    md_line: int
    md_excerpt: str
    delta_pct: float


@dataclass
class AuditReport:
    rooms_drift: List[DriftRow] = field(default_factory=list)
    services_drift: List[DriftRow] = field(default_factory=list)
    rooms_checked: int = 0
    services_checked: int = 0
    db_room_count: int = 0
    db_service_count: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def total_drift(self) -> int:
        return len(self.rooms_drift) + len(self.services_drift)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_drift"] = self.total_drift
        return d


def parse_int_price(text: str) -> Optional[float]:
    try:
        return float(text.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def load_db_prices() -> tuple[Dict[str, float], Dict[str, float], List[str]]:
    """Returns (room_prices, service_prices, errors).

    room_prices: {name: base_price}
    service_prices: {name_lower: price}
    """
    errors: List[str] = []
    room_prices: Dict[str, float] = {}
    service_prices: Dict[str, float] = {}

    try:
        import psycopg2  # type: ignore
    except ImportError:
        errors.append("psycopg2 not installed — install with: pip install psycopg2-binary")
        return room_prices, service_prices, errors

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://hotel_app:hotel_app_pass_CHANGE_ME@localhost:5432/hotel",
    )

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name, base_price FROM room_types ORDER BY base_price")
                for name, price in cur.fetchall():
                    room_prices[name] = float(price)

                # hotel_services may or may not exist depending on schema version
                cur.execute("""
                    SELECT to_regclass('public.hotel_services')
                """)
                if cur.fetchone()[0] is not None:
                    cur.execute("SELECT name, price FROM hotel_services WHERE price IS NOT NULL")
                    for name, price in cur.fetchall():
                        service_prices[name.lower()] = float(price)
    except Exception as exc:
        errors.append(f"DB connection failed: {exc}")

    return room_prices, service_prices, errors


def find_room_drift(
    md_file: Path,
    db_prices: Dict[str, float],
) -> tuple[List[DriftRow], int]:
    """Return (drift_rows, num_section_prices_checked) for one md file."""
    drift: List[DriftRow] = []
    checked = 0
    if not md_file.exists():
        return drift, 0
    lines = md_file.read_text(encoding="utf-8").splitlines()

    current_room: Optional[str] = None
    # Track (item, file, line) keys we've already flagged so the same
    # line isn't reported twice when EN and TH prices both match.
    seen_keys: set = set()
    alias_pairs = _iter_aliases_specific_first()

    def emit(item: str, md_price: float, line_no: int, excerpt: str) -> None:
        db_price = db_prices.get(item)
        if db_price is None or abs(md_price - db_price) < 0.01:
            return
        key = (item, md_file.name, line_no)
        if key in seen_keys:
            return
        seen_keys.add(key)
        delta_pct = (md_price - db_price) / db_price * 100.0
        drift.append(DriftRow(
            item=item,
            db_price=db_price,
            md_price=md_price,
            md_file=md_file.relative_to(ROOT).as_posix(),
            md_line=line_no,
            md_excerpt=excerpt[:140],
            delta_pct=round(delta_pct, 1),
        ))

    for i, line in enumerate(lines, start=1):
        # Detect H2 section header marking a room type
        if line.startswith("## "):
            header_lower = line.lower()
            current_room = None
            for canonical, alias in alias_pairs:
                if alias.lower() in header_lower:
                    current_room = canonical
                    break
            continue

        # Detect comparison table rows: "| Standard | 28 sqm | 2,500 THB | ..."
        if line.startswith("|") and "THB" in line:
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= 3:
                first_cell_lower = cells[1].lower()
                row_room = None
                for canonical, alias in alias_pairs:
                    first_word = alias.split()[0].lower() if alias.split() else ""
                    if first_word and first_word in first_cell_lower:
                        row_room = canonical
                        break
                if row_room:
                    for m in PRICE_PATTERN.finditer(line):
                        md_price = parse_int_price(m.group("value"))
                        if md_price is None:
                            continue
                        checked += 1
                        emit(row_room, md_price, i, line.strip())
            continue

        if current_room is None:
            continue

        for m in PRICE_PATTERN.finditer(line):
            md_price = parse_int_price(m.group("value"))
            if md_price is None:
                continue
            checked += 1
            emit(current_room, md_price, i, line.strip())

    return drift, checked


def find_service_drift(
    md_file: Path,
    db_prices: Dict[str, float],
) -> tuple[List[DriftRow], int]:
    """Heuristic service-price drift detection.

    Markdown service-price phrasing is much more varied than room prices
    ("Thai massage 60 min — 1,500 THB", "อาหารเช้าบุฟเฟต์ 800 บาท"). We
    therefore only flag prices that EXIST in md but have NO matching value
    in the DB service table (loose match: within ±1 THB). False positives
    are acceptable here since the audit is advisory for non-room items.
    """
    drift: List[DriftRow] = []
    checked = 0
    if not md_file.exists() or not db_prices:
        return drift, 0

    db_prices_set = {round(v, 2) for v in db_prices.values()}
    lines = md_file.read_text(encoding="utf-8").splitlines()

    for i, line in enumerate(lines, start=1):
        for m in PRICE_PATTERN.finditer(line):
            md_price = parse_int_price(m.group("value"))
            if md_price is None:
                continue
            # Skip obvious non-service mentions ("100 Mbps WiFi" with stray THB nearby)
            if md_price < 50 or md_price > 100_000:
                continue
            checked += 1
            rounded = round(md_price, 2)
            if rounded in db_prices_set:
                continue
            drift.append(DriftRow(
                item="(unknown service — value not in DB)",
                db_price=0.0,
                md_price=md_price,
                md_file=md_file.relative_to(ROOT).as_posix(),
                md_line=i,
                md_excerpt=line.strip()[:140],
                delta_pct=0.0,
            ))

    return drift, checked


def run_audit() -> AuditReport:
    report = AuditReport()
    room_prices, service_prices, errors = load_db_prices()
    report.errors.extend(errors)
    report.db_room_count = len(room_prices)
    report.db_service_count = len(service_prices)

    for fname in ROOM_PRICE_FILES:
        drift, checked = find_room_drift(KB_DIR / fname, room_prices)
        report.rooms_drift.extend(drift)
        report.rooms_checked += checked

    if service_prices:
        for fname in SERVICE_PRICE_FILES:
            drift, checked = find_service_drift(KB_DIR / fname, service_prices)
            report.services_drift.extend(drift)
            report.services_checked += checked

    return report


def print_human(report: AuditReport) -> None:
    print(f"\n=== DB -> RAG drift audit ===")
    print(f"DB room types loaded: {report.db_room_count}")
    print(f"DB hotel_services loaded: {report.db_service_count}")
    print(f"MD room-price mentions checked: {report.rooms_checked}")
    print(f"MD service-price mentions checked: {report.services_checked}")
    print()

    if report.errors:
        print("ERRORS:")
        for e in report.errors:
            print(f"  - {e}")
        print()

    if not report.total_drift:
        print("Result: NO DRIFT DETECTED")
        return

    if report.rooms_drift:
        print(f"ROOM PRICE DRIFT ({len(report.rooms_drift)} mismatches):")
        print(f"  {'Item':<18}{'DB':>10}{'MD':>10}{'Delta':>10}  Source")
        print(f"  {'-'*18}{'-'*10}{'-'*10}{'-'*10}  {'-'*60}")
        for d in report.rooms_drift:
            print(
                f"  {d.item:<18}{d.db_price:>10,.0f}{d.md_price:>10,.0f}"
                f"{d.delta_pct:>9.1f}%  {d.md_file}:{d.md_line}"
            )
        print()

    if report.services_drift:
        print(f"SERVICE PRICE DRIFT ({len(report.services_drift)} suspect values):")
        print(f"  Note: heuristic match; review each individually")
        for d in report.services_drift:
            print(f"  - {d.md_file}:{d.md_line}  → {d.md_price:,.0f} THB")
            print(f"      {d.md_excerpt[:100]}")
        print()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--json", action="store_true", help="emit JSON instead of human-readable text")
    p.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if any drift detected (CI-friendly)",
    )
    args = p.parse_args()

    try:
        report = run_audit()
    except Exception as exc:
        print(f"Internal error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print_human(report)

    if report.errors and not report.db_room_count:
        return 1  # DB unreachable — couldn't audit
    if args.strict and report.total_drift > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
