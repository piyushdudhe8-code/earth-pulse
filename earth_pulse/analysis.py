from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata, theilslopes

from .data import VARIABLES, prepare_monthly_series


def _annual_series(monthly: pd.DataFrame, variable: str) -> pd.Series:
    clean = prepare_monthly_series(monthly, variable)
    clean = clean.dropna(subset=["display_value"])
    if VARIABLES[variable]["kind"] == "rain":
        annual = clean.groupby("year")["display_value"].sum(min_count=12)
    else:
        # Calendar-day weighting avoids treating February and a 31-day month equally.
        weighted = clean["display_value"] * clean["days"]
        annual_num = weighted.groupby(clean["year"]).sum(min_count=12)
        annual_den = clean["days"].groupby(clean["year"]).sum(min_count=12)
        annual = annual_num / annual_den
    annual.index = annual.index.astype(int)
    return annual.dropna().sort_index()


def _lag1_autocorrelation(values: np.ndarray) -> float:
    if len(values) < 4:
        return float("nan")
    x = np.asarray(values, dtype=float)
    slope, intercept, *_ = theilslopes(x, np.arange(len(x)))
    residual = x - (intercept + slope * np.arange(len(x)))
    if np.std(residual[:-1]) == 0 or np.std(residual[1:]) == 0:
        return 0.0
    return float(np.corrcoef(residual[:-1], residual[1:])[0, 1])


def hamed_rao_mann_kendall(values: np.ndarray, alpha: float = 0.05) -> dict:
    """Hamed–Rao modified Mann–Kendall test with a rank-ACF variance correction.

    Implements the Hamed & Rao variance-correction formulation: remove a Sen trend,
    rank the detrended series, retain significant rank-autocorrelation lags, and
    inflate the null variance before computing a two-sided normal-approximation p.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 8:
        raise ValueError(
            "Analysis cannot be completed reliably: at least 8 annual values are "
            "required for the trend test."
        )

    # Mann–Kendall S statistic.
    s = 0
    for i in range(n - 1):
        s += int(np.sign(x[i + 1:] - x[i]).sum())

    # Tie-corrected variance of S.
    _, counts = np.unique(x, return_counts=True)
    tie_term = sum(int(t * (t - 1) * (2 * t + 5)) for t in counts if t > 1)
    var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    if var_s <= 0:
        return {"tau": 0.0, "z": 0.0, "p": 1.0, "s": int(s), "var_s": 0.0}

    # Detrend before calculating serial correlation so the trend itself is not mistaken for persistence.
    slope, intercept, *_ = theilslopes(x, np.arange(1, n + 1))
    detrended = x - (np.arange(1, n + 1) * slope)
    ranks = rankdata(detrended).astype(float)
    ranks -= ranks.mean()
    denominator = float(np.dot(ranks, ranks))
    acf = np.zeros(n, dtype=float)
    if denominator > 0:
        for lag in range(1, n):
            acf[lag] = float(np.dot(ranks[:-lag], ranks[lag:]) / denominator)

    # Follow the Hamed–Rao significance filter for autocorrelation lags.
    bound = float(norm.ppf(1 - alpha / 2) / np.sqrt(n))
    correction_sum = 0.0
    for lag in range(1, n):
        if abs(acf[lag]) > bound:
            correction_sum += (n - lag) * (n - lag - 1) * (n - lag - 2) * acf[lag]
    n_ns = 1 + (2.0 / (n * (n - 1) * (n - 2))) * abs(correction_sum)
    adjusted_var_s = var_s * max(n_ns, 1e-9)

    if s > 0:
        z = (s - 1) / np.sqrt(adjusted_var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(adjusted_var_s)
    else:
        z = 0.0
    p_value = float(2 * (1 - norm.cdf(abs(z))))
    tau = float(s / (0.5 * n * (n - 1)))
    return {"tau": tau, "z": float(z), "p": p_value, "s": int(s), "var_s": float(adjusted_var_s)}


def analyze_series(monthly: pd.DataFrame, variable: str, source: str | None = None) -> dict:
    if variable not in VARIABLES:
        raise ValueError(f"Unsupported variable: {variable}")
    if not VARIABLES[variable].get("trend_supported", True):
        raise ValueError(
            f"A long-term statistical trend is not reported for {variable} because "
            "NASA POWER combines source products across the record. Monthly observations "
            "and seasonal summaries remain available."
        )
    prepared = prepare_monthly_series(monthly, variable)
    expected_count = len(prepared)
    valid_count = int(prepared["display_value"].notna().sum())
    completeness = (valid_count / expected_count * 100) if expected_count else 0.0
    annual = _annual_series(monthly, variable)

    if len(annual) < 8:
        raise ValueError(
            "Analysis cannot be completed reliably: at least 8 complete annual values "
            "are needed for a cautious trend test. Choose a longer period."
        )
    years = annual.index.to_numpy(dtype=float)
    if len(years) > 1 and not np.all(np.diff(years) == 1):
        raise ValueError(
            "Analysis cannot be completed reliably: one or more whole years have too "
            "many missing months for annual aggregation. Choose a different time range "
            "or inspect data completeness."
        )

    values = annual.to_numpy(dtype=float)
    test = hamed_rao_mann_kendall(values, alpha=0.05)
    slope_result = theilslopes(values, years, alpha=0.95)
    slope = float(slope_result.slope)
    low_slope = float(slope_result.low_slope)
    high_slope = float(slope_result.high_slope)
    lag1 = _lag1_autocorrelation(values)

    rate_per_decade = slope * 10
    ci_low = low_slope * 10
    ci_high = high_slope * 10
    p_value = float(test["p"])
    significant = bool(p_value < 0.05)
    direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat"

    return {
        "monthly": prepared,
        "annual": annual,
        "variable": variable,
        "unit": VARIABLES[variable]["unit"],
        "trend_unit": "mm/year" if VARIABLES[variable]["kind"] == "rain" else VARIABLES[variable]["unit"],
        "kind": VARIABLES[variable]["kind"],
        "source": source or monthly.attrs.get("source", "Unknown source"),
        "parameter": monthly.attrs.get("parameter", VARIABLES[variable]["parameter"]),
        "dataset": monthly.attrs.get("dataset", "NASA POWER; dataset not identified"),
        "api_title": monthly.attrs.get("api_title", "not provided"),
        "api_long_name": monthly.attrs.get("api_long_name", "not provided"),
        "api_parameter_metadata": monthly.attrs.get("api_parameter_metadata", {}),
        "api_unit": monthly.attrs.get("api_unit", "not provided"),
        "display_unit": monthly.attrs.get("display_unit", VARIABLES[variable]["unit"]),
        "spatial_resolution": monthly.attrs.get("spatial_resolution", "not provided by response"),
        "api_latitude": monthly.attrs.get("api_latitude"),
        "api_longitude": monthly.attrs.get("api_longitude"),
        "api_elevation_m": monthly.attrs.get("api_elevation_m"),
        "response_header": monthly.attrs.get("response_header", {}),
        "api_version": monthly.attrs.get("api_version", "unknown"),
        "data_sources": monthly.attrs.get("data_sources", "unknown"),
        "request_url": monthly.attrs.get("request_url", "unavailable"),
        "retrieved_at": monthly.attrs.get("retrieved_at", "not provided"),
        "requested_start": monthly.attrs.get("requested_start", "not provided"),
        "requested_end": monthly.attrs.get("requested_end", "not provided"),
        "completeness": completeness,
        "valid_months": valid_count,
        "expected_months": expected_count,
        "missing_months": expected_count - valid_count,
        "latest_valid_date": monthly.attrs.get(
            "latest_valid_date",
            str(prepared.loc[prepared["display_value"].notna()].index.max().date()),
        ),
        "start": str(prepared.loc[prepared["display_value"].notna()].index.min().date()),
        "end": str(prepared.loc[prepared["display_value"].notna()].index.max().date()),
        "years_count": len(annual),
        "tau": float(test["tau"]),
        "p_value": p_value,
        "z_score": float(test["z"]),
        "slope_per_year": slope,
        "slope_per_decade": rate_per_decade,
        "ci_low_per_decade": ci_low,
        "ci_high_per_decade": ci_high,
        "lag1_autocorrelation": lag1,
        "significant": significant,
        "direction": direction,
        "method": "Hamed–Rao modified Mann–Kendall on annual aggregates + Sen's slope",
    }


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """Benjamini–Hochberg false-discovery-rate adjusted p-values."""
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    if n == 0:
        return []
    order = np.argsort(p)
    ranked = p[order]
    adjusted_ranked = ranked * n / np.arange(1, n + 1)
    adjusted_ranked = np.minimum.accumulate(adjusted_ranked[::-1])[::-1]
    adjusted = np.empty(n, dtype=float)
    adjusted[order] = np.clip(adjusted_ranked, 0, 1)
    return adjusted.tolist()


def build_verdict(result: dict, language: str = "English") -> str:
    slope = result["slope_per_decade"]
    low, high = result["ci_low_per_decade"], result["ci_high_per_decade"]
    unit = result["trend_unit"]
    if result["kind"] == "rain":
        change = f"{slope:+.1f} {unit} per decade"
        ci = f"95% CI {low:+.1f} to {high:+.1f}"
    else:
        change = f"{slope:+.3f} {unit} per decade"
        ci = f"95% CI {low:+.3f} to {high:+.3f}"

    if language == "हिन्दी":
        if result["significant"]:
            return f"{result['variable']} में सांख्यिकीय रूप से महत्वपूर्ण बदलाव मिला: हर दशक में लगभग {change}। {ci}। यह trend है, कारण का प्रमाण नहीं।"
        return f"अभी {result['variable']} में 5% स्तर पर सांख्यिकीय रूप से महत्वपूर्ण trend नहीं मिला। अनुमानित बदलाव {change} है ({ci})। इसका अर्थ यह नहीं कि कोई बदलाव बिल्कुल नहीं है।"

    if result["significant"]:
        direction = "rising" if slope > 0 else "falling"
        return f"A statistically significant {direction} trend was detected in {result['variable'].lower()}: about {change}. {ci}. This describes a pattern, not its cause."
    return f"No statistically significant trend was detected in {result['variable'].lower()} at the 5% level. The estimated rate is {change} ({ci}). This does not prove that nothing is changing."
