"""Data processing functions for NZ WITS price analytics."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from .const import SCHEDULE_INTERIM, SCHEDULE_PRSL, SCHEDULE_PRSS, SCHEDULE_RTD
from .coordinator import WitsDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def get_price_statistics(
    coordinator: WitsDataUpdateCoordinator, schedule_type: str
) -> dict[str, Any]:
    """Calculate comprehensive price statistics for a schedule."""
    if not coordinator.data or schedule_type not in coordinator.data:
        return {}

    schedule_data = coordinator.data[schedule_type]
    if not schedule_data or not isinstance(schedule_data, list):
        return {}

    # Extract valid prices
    prices = []
    for item in schedule_data:
        price = item.get("price")
        if price is not None:
            try:
                prices.append(float(price))
            except (ValueError, TypeError):
                continue

    if not prices:
        return {}

    # Convert to kWh prices
    prices_kwh = [price / 1000 for price in prices]

    # Calculate statistics
    min_price = min(prices_kwh)
    max_price = max(prices_kwh)
    avg_price = sum(prices_kwh) / len(prices_kwh)

    # Find time periods for min/max prices
    min_period = None
    max_period = None

    for item in schedule_data:
        if item.get("price") is not None:
            price_kwh = item["price"] / 1000
            if abs(price_kwh - min_price) < 0.00001:  # Float comparison
                min_period = {
                    "period": item.get("tradingPeriod"),
                    "datetime": item.get("tradingDateTime"),
                }
            if abs(price_kwh - max_price) < 0.00001:
                max_period = {
                    "period": item.get("tradingPeriod"),
                    "datetime": item.get("tradingDateTime"),
                }

    return {
        "current_price": prices_kwh[0] if prices_kwh else None,
        "average_price": round(avg_price, 5),
        "min_price": round(min_price, 5),
        "max_price": round(max_price, 5),
        "price_range": round(max_price - min_price, 5),
        "data_points": len(prices_kwh),
        "min_price_period": min_period,
        "max_price_period": max_period,
        "price_volatility": round(_calculate_volatility(prices_kwh), 5)
        if len(prices_kwh) > 1
        else 0,
    }


def get_forecast_summary(
    coordinator: WitsDataUpdateCoordinator, schedule_type: str
) -> dict[str, Any]:
    """Get comprehensive forecast summary for PRSS/PRSL schedules."""
    if schedule_type not in [SCHEDULE_PRSS, SCHEDULE_PRSL]:
        return {}

    if not coordinator.data or schedule_type not in coordinator.data:
        return {}

    schedule_data = coordinator.data[schedule_type]
    if not schedule_data or not isinstance(schedule_data, list):
        return {}

    # Extract forecast prices in kWh
    forecast_data = []
    for item in schedule_data:
        price = item.get("price")
        if price is not None:
            try:
                forecast_data.append(
                    {
                        "price_kwh": float(price) / 1000,
                        "period": item.get("tradingPeriod"),
                        "datetime": item.get("tradingDateTime"),
                    }
                )
            except (ValueError, TypeError):
                continue

    if not forecast_data:
        return {}

    forecast_prices = [item["price_kwh"] for item in forecast_data]

    # Time-based averages
    next_hour = forecast_prices[0] if forecast_prices else None
    next_3h = (
        sum(forecast_prices[:6]) / min(6, len(forecast_prices))
        if forecast_prices
        else None
    )  # 6 periods = 3 hours
    next_6h = (
        sum(forecast_prices[:12]) / min(12, len(forecast_prices))
        if forecast_prices
        else None
    )  # 12 periods = 6 hours

    # Peak and off-peak analysis
    peak_times = _get_peak_periods()
    peak_prices = []
    off_peak_prices = []

    for item in forecast_data:
        period = item.get("period")
        if period and period in peak_times:
            peak_prices.append(item["price_kwh"])
        else:
            off_peak_prices.append(item["price_kwh"])

    # Trend analysis
    trend = (
        _calculate_price_trend(forecast_prices)
        if len(forecast_prices) > 2
        else "stable"
    )

    summary = {
        "forecast_hours": len(forecast_data),
        "next_hour_price": round(next_hour, 5) if next_hour else None,
        "avg_next_3h": round(next_3h, 5) if next_3h else None,
        "avg_next_6h": round(next_6h, 5) if next_6h else None,
        "min_forecast": round(min(forecast_prices), 5) if forecast_prices else None,
        "max_forecast": round(max(forecast_prices), 5) if forecast_prices else None,
        "avg_forecast": round(sum(forecast_prices) / len(forecast_prices), 5)
        if forecast_prices
        else None,
        "price_trend": trend,
    }

    # Add peak/off-peak analysis if we have data
    if peak_prices:
        summary["avg_peak_price"] = round(sum(peak_prices) / len(peak_prices), 5)
    if off_peak_prices:
        summary["avg_off_peak_price"] = round(
            sum(off_peak_prices) / len(off_peak_prices), 5
        )

    return summary


def get_price_comparison(coordinator: WitsDataUpdateCoordinator) -> dict[str, Any]:
    """Compare prices across different schedule types."""
    if not coordinator.data:
        return {}

    current_prices = {}

    # Get current price from each schedule
    for schedule_type in (SCHEDULE_RTD, SCHEDULE_INTERIM, SCHEDULE_PRSS, SCHEDULE_PRSL):
        if schedule_type in coordinator.data:
            schedule_data = coordinator.data[schedule_type]
            if (
                schedule_data
                and isinstance(schedule_data, list)
                and schedule_data[0].get("price")
            ):
                try:
                    current_prices[schedule_type] = (
                        float(schedule_data[0]["price"]) / 1000
                    )
                except (ValueError, TypeError):
                    continue

    if not current_prices:
        return {}

    # Calculate comparisons
    price_values = list(current_prices.values())

    comparison = {
        "schedules_available": list(current_prices.keys()),
        "price_spread": round(max(price_values) - min(price_values), 5)
        if len(price_values) > 1
        else 0,
        "schedule_prices": {k: round(v, 5) for k, v in current_prices.items()},
    }

    # Add relative comparisons
    if SCHEDULE_RTD in current_prices:
        rtd_price = current_prices[SCHEDULE_RTD]
        for schedule, price in current_prices.items():
            if schedule != SCHEDULE_RTD:
                diff = price - rtd_price
                comparison[f"{schedule.lower()}_vs_rtd"] = {
                    "difference": round(diff, 5),
                    "percentage": round((diff / rtd_price) * 100, 2)
                    if rtd_price != 0
                    else 0,
                }

    return comparison


def get_trading_period_info(coordinator: WitsDataUpdateCoordinator) -> dict[str, Any]:
    """Get information about current trading period and timing."""
    now = dt_util.utcnow()

    # Calculate current trading period (30-minute periods starting at midnight NZT)
    # Convert to NZ time
    nz_time = dt_util.as_local(now)
    start_of_day = nz_time.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = nz_time - start_of_day
    current_period = (
        int(elapsed.total_seconds() / 1800) + 1
    )  # 1800 seconds = 30 minutes

    # Calculate next period timing
    next_period_start = start_of_day + timedelta(minutes=current_period * 30)
    time_to_next = next_period_start - nz_time

    # Get data freshness
    data_age = None
    if coordinator.data:
        for schedule_data in coordinator.data.values():
            if isinstance(schedule_data, list) and schedule_data:
                last_update = coordinator.data.get("last_api_success_utc")
                if last_update:
                    data_age = (now - last_update).total_seconds()
                break

    return {
        "current_trading_period": min(current_period, 50),  # Max 50 periods per day
        "next_period_in_minutes": max(0, int(time_to_next.total_seconds() / 60)),
        "current_nz_time": nz_time.isoformat(),
        "data_age_seconds": data_age,
        "is_peak_period": current_period in _get_peak_periods(),
    }


def _calculate_volatility(prices: list[float]) -> float:
    """Calculate price volatility (standard deviation)."""
    if len(prices) < 2:
        return 0.0

    mean = sum(prices) / len(prices)
    variance = sum((price - mean) ** 2 for price in prices) / (len(prices) - 1)
    return variance**0.5


def _calculate_price_trend(prices: list[float]) -> str:
    """Calculate price trend direction."""
    if len(prices) < 3:
        return "stable"

    # Simple trend calculation using first, middle, and last values
    start = prices[0]
    middle = prices[len(prices) // 2]
    end = prices[-1]

    # Calculate trend strength
    total_change = end - start
    mid_change = middle - start

    if abs(total_change) < 0.01:  # Very small change
        return "stable"
    if total_change > 0:
        return "increasing" if mid_change > 0 else "volatile_up"
    return "decreasing" if mid_change < 0 else "volatile_down"


def _get_peak_periods() -> set[int]:
    """Get trading periods that are considered peak times (7am-11pm weekdays)."""
    # Peak periods: 7:00 AM to 11:00 PM (periods 15-46)
    # This is a simplified peak time definition
    return set(range(15, 47))  # Periods 15-46 (7:00 AM - 11:00 PM)


def get_price_alerts(
    coordinator: WitsDataUpdateCoordinator,
    threshold_high: float = 0.30,
    threshold_low: float = 0.05,
) -> dict[str, Any]:
    """Generate price alerts based on thresholds."""
    alerts: dict[str, list[dict[str, Any]]] = {
        "high_price_alerts": [],
        "low_price_alerts": [],
        "forecast_alerts": [],
    }

    if not coordinator.data:
        return alerts

    # Check current prices
    for schedule_type, schedule_data in coordinator.data.items():
        if not isinstance(schedule_data, list) or not schedule_data:
            continue

        current_price = schedule_data[0].get("price")
        if current_price is None:
            continue

        try:
            price_kwh = float(current_price) / 1000
        except (ValueError, TypeError):
            continue

        if price_kwh >= threshold_high:
            alerts["high_price_alerts"].append(
                {
                    "schedule": schedule_type,
                    "price": round(price_kwh, 5),
                    "period": schedule_data[0].get("tradingPeriod"),
                    "datetime": schedule_data[0].get("tradingDateTime"),
                }
            )
        elif price_kwh <= threshold_low:
            alerts["low_price_alerts"].append(
                {
                    "schedule": schedule_type,
                    "price": round(price_kwh, 5),
                    "period": schedule_data[0].get("tradingPeriod"),
                    "datetime": schedule_data[0].get("tradingDateTime"),
                }
            )

    # Check forecast for upcoming high/low prices
    for schedule_type in (SCHEDULE_PRSS, SCHEDULE_PRSL):
        if schedule_type not in coordinator.data:
            continue

        schedule_data = coordinator.data[schedule_type]
        if not isinstance(schedule_data, list):
            continue

        for item in schedule_data[1:7]:  # Check next 6 periods (3 hours)
            price = item.get("price")
            if price is None:
                continue

            try:
                price_kwh = float(price) / 1000
            except (ValueError, TypeError):
                continue

            if price_kwh >= threshold_high:
                alerts["forecast_alerts"].append(
                    {
                        "type": "high_price_upcoming",
                        "schedule": schedule_type,
                        "price": round(price_kwh, 5),
                        "period": item.get("tradingPeriod"),
                        "datetime": item.get("tradingDateTime"),
                    }
                )
            elif price_kwh <= threshold_low:
                alerts["forecast_alerts"].append(
                    {
                        "type": "low_price_upcoming",
                        "schedule": schedule_type,
                        "price": round(price_kwh, 5),
                        "period": item.get("tradingPeriod"),
                        "datetime": item.get("tradingDateTime"),
                    }
                )

    return alerts
