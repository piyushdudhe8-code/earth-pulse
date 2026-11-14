from __future__ import annotations

from datetime import datetime, timezone


def make_report(result: dict, city: str, latitude: float, longitude: float, verdict: str, adjusted_p: float | None = None) -> str:
    p_line = f"Mann–Kendall p-value: {result['p_value']:.5f}"
    if adjusted_p is not None:
        p_line += f"\nBenjamini–Hochberg adjusted p-value (comparison): {adjusted_p:.5f}"
    if result["kind"] == "rain":
        rate = f"{result['slope_per_decade']:+.2f} {result['trend_unit']} per decade"
        ci = f"[{result['ci_low_per_decade']:+.2f}, {result['ci_high_per_decade']:+.2f}]"
    else:
        rate = f"{result['slope_per_decade']:+.4f} {result['trend_unit']} per decade"
        ci = f"[{result['ci_low_per_decade']:+.4f}, {result['ci_high_per_decade']:+.4f}]"
    return f"""EARTH PULSE — Investigation Report
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

QUESTION
What changed in {city}?

LOCATION
{city} | Latitude: {latitude:.4f} | Longitude: {longitude:.4f}

VARIABLE
{result['variable']} ({result['parameter']})
Period: {result['start']} to {result['end']}
Data source: {result['source']}
NASA POWER API version: {result['api_version']}
Underlying source(s): {result['data_sources']}
Request URL: {result['request_url']}

FINDING
{verdict}
Estimated rate: {rate}
95% confidence interval: {ci}
{p_line}
Kendall tau: {result['tau']:.4f}
Lag-1 autocorrelation diagnostic (detrended annual values): {result['lag1_autocorrelation']:.4f}
Data completeness: {result['completeness']:.1f}% ({result['valid_months']}/{result['expected_months']} months)

METHOD
{result['method']}
Monthly observations were converted to annual aggregates to reduce the effect of the repeating seasonal cycle. Hamed–Rao modified Mann–Kendall was used for the trend significance test. Sen's slope and its 95% confidence interval estimate the rate of change.

IMPORTANT LIMITATIONS
• A statistically significant trend does not establish its cause (correlation is not causation).
• NASA POWER is gridded analysis-ready data, not a street-level weather station measurement.
• Rainfall is estimated from the monthly mean daily precipitation rate multiplied by the number of calendar days in each month. Annual rainfall is the sum of these monthly estimates (mm/year).
• Incomplete months/years can affect the result; check completeness before interpreting it.
• Statistical significance is not the same as practical importance.
• DEMO DATA, when shown, is synthetic and must never be cited as a NASA observation.

NASA POWER documentation: https://power.larc.nasa.gov/docs/services/api/temporal/monthly/
"""
