"""
Exam period date utilities.

Computes the list of schedulable dates from the user's configuration:
  - Start date / end date
  - Excluded weekdays (0=Mon … 6=Sun; e.g. Friday=4, Saturday=5)
  - Ad-hoc excluded dates (holidays)

No date is hardcoded — everything is configurable (FR-2).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable


def available_dates(
    start: date,
    end: date,
    excluded_weekdays: Iterable[int] = (4, 5),   # default: Fri + Sat
    excluded_dates: Iterable[date] = (),
) -> list[date]:
    """
    Return an ordered list of schedulable exam dates in [start, end].

    Parameters
    ----------
    start              : first day of the exam period (inclusive)
    end                : last day of the exam period (inclusive)
    excluded_weekdays  : weekday numbers to skip every week
                         (0=Monday … 6=Sunday; default Friday=4, Saturday=5)
    excluded_dates     : additional ad-hoc dates to exclude (public holidays)

    Returns an empty list if start > end or all days are excluded.
    """
    if start > end:
        return []

    excluded_weekday_set = set(excluded_weekdays)
    excluded_date_set = set(excluded_dates)

    dates: list[date] = []
    current = start
    while current <= end:
        if current.weekday() not in excluded_weekday_set and current not in excluded_date_set:
            dates.append(current)
        current += timedelta(days=1)

    return dates
