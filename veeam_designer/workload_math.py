"""Shared workload math helpers for consistent sizing calculations."""

from __future__ import annotations


def projected_total_data_tb(
    total_data_tb: float,
    annual_growth_percent: float,
    years_to_plan_for: int,
) -> float:
    """Return protected data after compounding the configured annual growth rate."""

    years = max(0, years_to_plan_for)
    annual_rate = max(-1.0, annual_growth_percent / 100.0)
    growth_factor = (1.0 + annual_rate) ** years
    return total_data_tb * growth_factor


def daily_change_tb(total_data_tb: float, daily_change_percent: float) -> float:
    """Return the daily changed data in terabytes."""

    return total_data_tb * daily_change_percent / 100.0


def projected_daily_change_tb(
    total_data_tb: float,
    daily_change_percent: float,
    annual_growth_percent: float,
    years_to_plan_for: int,
) -> float:
    """Return daily changed data after the projected growth horizon is applied."""

    projected_total = projected_total_data_tb(
        total_data_tb=total_data_tb,
        annual_growth_percent=annual_growth_percent,
        years_to_plan_for=years_to_plan_for,
    )
    return daily_change_tb(projected_total, daily_change_percent)


def tb_to_mb(total_tb: float) -> float:
    """Convert tebibytes to mebibytes using binary storage units."""

    return total_tb * 1024.0 * 1024.0
