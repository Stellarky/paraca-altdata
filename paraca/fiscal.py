"""Fiscal-period helpers. Paraca's fiscal year ends 30 September (Park24: 31 October).

Fiscal years are labelled by the calendar year in which they END: FY2026 =
1 Oct 2025 – 30 Sep 2026. Q1 = Oct–Dec, Q2 = Jan–Mar, Q3 = Apr–Jun, Q4 = Jul–Sep.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class FiscalQuarter:
    fy: int
    q: int
    start: date
    end: date

    @property
    def label(self) -> str:
        return f"FY{self.fy} Q{self.q}"


def fiscal_quarter(d: date, fy_end_month: int = 9) -> FiscalQuarter:
    """Return the fiscal quarter containing date d for a FY ending in fy_end_month."""
    first_month = fy_end_month % 12 + 1                 # Sep-end -> October
    offset = (d.month - first_month) % 12               # months since FY start
    fy = d.year + (1 if d.month > fy_end_month else 0)
    if fy_end_month == 12:
        fy = d.year
    q = offset // 3 + 1
    return quarter_bounds(fy, q, fy_end_month)


def quarter_bounds(fy: int, q: int, fy_end_month: int = 9) -> FiscalQuarter:
    if q not in (1, 2, 3, 4):
        raise ValueError("quarter must be 1-4")
    first_month = fy_end_month % 12 + 1
    start_year = fy - 1 if fy_end_month != 12 else fy
    m0 = first_month + 3 * (q - 1)
    y0 = start_year + (m0 - 1) // 12
    m0 = (m0 - 1) % 12 + 1
    m1 = m0 + 2
    y1 = y0 + (m1 - 1) // 12
    m1 = (m1 - 1) % 12 + 1
    return FiscalQuarter(fy, q, date(y0, m0, 1), date(y1, m1, calendar.monthrange(y1, m1)[1]))
