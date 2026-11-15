from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import requests


NASA_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

ENVIRONMENTAL_PARAMETERS: dict[str, dict[str, Any]] = {
    "Hotness": {
        "short_name": "HOTNESS",
        "scientific_name": "Average air temperature",
        "parameter": "T2M",
        "unit": "°C",
        "aggregation": "mean",
        "start_date": "1981-01-01",
        "resolution": "MERRA-2 / GEOS-IT native grid: 0.5° latitude × 0.625° longitude",
        "description": "How hot is the air about 2 metres above the surface?",
    },
    "Rainfall": {
        "short_name": "RAINFALL",
        "scientific_name": "Corrected precipitation",
        "parameter": "PRECTOTCORR",
        "unit": "mm/month (estimated)",
        "aggregation": "sum",
        "start_date": "1981-01-01",
        "resolution": "MERRA-2 / GEOS-IT native grid: 0.5° latitude × 0.625° longitude",
        "description": "How much corrected precipitation reached the area?",
        "product_note": (
            "NASA POWER PRECTOTCORR is used as a daily precipitation rate and summed "
            "to monthly totals. If fewer than all days are valid but at least 80% are "
            "present, the mean valid-day rate is scaled to the calendar month; poorer "
            "months are omitted. NASA IMERG is a separate ~0.1° product and is not "
            "silently substituted or combined with this series."
        ),
    },
    "Air moisture": {
        "short_name": "AIR MOISTURE",
        "scientific_name": "Relative humidity",
        "parameter": "RH2M",
        "unit": "%",
        "aggregation": "mean",
        "start_date": "1981-01-01",
        "resolution": "MERRA-2 / GEOS-IT native grid: 0.5° latitude × 0.625° longitude",
        "description": "How much moisture is in the air? This is relative humidity, not dryness.",
    },
    "Soil moisture": {
        "short_name": "SOIL MOISTURE",
        "scientific_name": "Surface soil moisture",
        "parameter": "SFMC",
        "unit": "m³/m³",
        "aggregation": "mean",
        "start_date": "2015-03-31",
        "resolution": (
            "SMAP L4 native resolution is about 9 km (~0.09°); shown as the source "
            "resolution only when NASA response metadata identifies SMAP."
        ),
        "description": "How much water is in the upper soil layer? Missing SFMC data is not filled from another product.",
        "product_note": (
            "The NASA SMAP L4 record begins in 2015. POWER is treated as SMAP only when "
            "the response identifies that source; it may return no valid SFMC values "
            "for a location. No pre-2015 or alternate-product values are fabricated."
        ),
    },
    "Air speed": {
        "short_name": "AIR SPEED",
        "scientific_name": "Wind speed at 10 metres",
        "parameter": "WS10M",
        "unit": "m/s",
        "aggregation": "mean",
        "start_date": "1981-01-01",
        "resolution": "MERRA-2 / GEOS-IT native grid: 0.5° latitude × 0.625° longitude",
        "description": "How fast is the air moving at 10 metres above the surface?",
    },
    "Sunlight": {
        "short_name": "SUNLIGHT",
        "scientific_name": "Downward surface shortwave radiation",
        "parameter": "ALLSKY_SFC_SW_DWN",
        "unit": "kWh/m²/day",
        "aggregation": "mean",
        "start_date": "1984-01-01",
        "resolution": "NASA POWER solar source-native grid: 1° latitude × 1° longitude",
        "description": "How much solar energy reaches the surface each day?",
        "product_note": (
            "The solar record concatenates different satellite products. Source "
            "transitions can create discontinuities, so this explorer does not report "
            "a long-term statistical trend for sunlight."
        ),
    },
}


def fetch_nasa_daily(
    latitude: float,
    longitude: float,
    variable: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch one NASA POWER daily point series without filling missing observations."""
    if variable not in ENVIRONMENTAL_PARAMETERS:
        raise ValueError(f"Unsupported environmental parameter: {variable}")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Latitude/longitude are outside valid ranges.")
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("Dates must use the YYYY-MM-DD format.") from exc
    if start > end:
        raise ValueError("Start date must be before end date.")

    metadata = ENVIRONMENTAL_PARAMETERS[variable]
    minimum_date = date.fromisoformat(metadata["start_date"])
    if start < minimum_date:
        raise ValueError(
            f"{variable} data starts no earlier than {minimum_date.isoformat()}."
        )

    parameter = metadata["parameter"]
    params = {
        "parameters": parameter,
        "community": "AG",
        "longitude": f"{longitude:.4f}",
        "latitude": f"{latitude:.4f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }
    headers = {"User-Agent": "EarthPulse/1.0 (student research prototype)"}
    try:
        response = requests.get(
            NASA_DAILY_URL, params=params, headers=headers, timeout=45
        )
    except requests.Timeout as exc:
        raise RuntimeError(
            "NASA POWER request timed out. Check your internet connection and try again."
        ) from exc
    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Could not connect to NASA POWER. Check your internet connection and try again."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"NASA POWER request failed: {exc}") from exc

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = getattr(response, "text", "").strip()
        if len(detail) > 300:
            detail = f"{detail[:297]}..."
        message = f"NASA POWER returned HTTP {response.status_code}."
        if detail:
            message = f"{message} {detail}"
        raise RuntimeError(message) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("NASA POWER returned a response that was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("NASA POWER returned an unexpected JSON response.")

    properties = payload.get("properties") if isinstance(payload, dict) else None
    parameter_values = properties.get("parameter") if isinstance(properties, dict) else None
    values = parameter_values.get(parameter) if isinstance(parameter_values, dict) else None
    if not isinstance(values, dict):
        messages = payload.get("messages") if isinstance(payload, dict) else None
        detail = f" NASA POWER message: {messages}" if messages else ""
        raise RuntimeError(
            f"NASA POWER response did not contain daily values for {parameter}.{detail}"
        )

    header = payload.get("header")
    header = header if isinstance(header, dict) else {}
    try:
        fill_value = float(header.get("fill_value", -999.0))
    except (TypeError, ValueError):
        fill_value = -999.0
    records: list[dict[str, Any]] = []
    for key, raw_value in values.items():
        try:
            observation_date = datetime.strptime(str(key), "%Y%m%d").date()
            number = float(raw_value)
        except (TypeError, ValueError):
            continue
        if observation_date < start or observation_date > end:
            continue
        valid = np.isfinite(number) and number > -900 and number != fill_value
        records.append(
            {
                "date": pd.Timestamp(observation_date),
                "value": number if valid else np.nan,
            }
        )

    if not records:
        raise RuntimeError("NASA POWER returned no daily observations for this request.")

    frame = (
        pd.DataFrame(records)
        .sort_values("date")
        .drop_duplicates("date")
        .set_index("date")
        .reindex(pd.date_range(start, end, freq="D"))
    )
    frame.index.name = "date"
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")

    parameter_details = payload.get("parameters")
    parameter_details = (
        parameter_details.get(parameter)
        if isinstance(parameter_details, dict)
        else None
    )
    parameter_details = parameter_details if isinstance(parameter_details, dict) else {}
    geometry = payload.get("geometry")
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    sources = header.get("sources")
    sources = sources if isinstance(sources, list) else []
    source_text = ", ".join(str(source) for source in sources) or "NASA POWER; source not identified"
    resolution = metadata["resolution"]
    if variable == "Soil moisture":
        if any("SMAP" in str(source).upper() for source in sources):
            resolution = "SMAP L4 native resolution: about 9 km (~0.09°)"
        else:
            resolution = (
                "NASA POWER did not identify SMAP in this response; native resolution "
                "is not asserted for these values."
            )

    frame.attrs.update(
        {
            "source": "NASA POWER Daily API",
            "parameter": parameter,
            "api_version": (header.get("api") or {}).get("version", "unknown"),
            "data_sources": source_text,
            "unit": parameter_details.get("units", metadata["unit"]),
            "long_name": parameter_details.get("longname", metadata["scientific_name"]),
            "request_url": getattr(response, "url", ""),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "time_standard": header.get("time_standard", "UTC"),
            "api_longitude": coordinates[0] if isinstance(coordinates, list) and len(coordinates) >= 2 else None,
            "api_latitude": coordinates[1] if isinstance(coordinates, list) and len(coordinates) >= 2 else None,
            "api_elevation_m": coordinates[2] if isinstance(coordinates, list) and len(coordinates) >= 3 else None,
            "spatial_resolution": resolution,
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
            "latest_valid_date": (
                frame.index[frame["value"].notna()].max().date().isoformat()
                if frame["value"].notna().any()
                else None
            ),
        }
    )
    return frame


def summarize_daily_series(frame: pd.DataFrame, variable: str) -> dict[str, Any]:
    """Create monthly and annual summaries while preserving missing-data counts."""
    if variable not in ENVIRONMENTAL_PARAMETERS:
        raise ValueError(f"Unsupported environmental parameter: {variable}")
    metadata = ENVIRONMENTAL_PARAMETERS[variable]
    daily = frame[["value"]].copy().sort_index()
    daily["valid"] = daily["value"].notna()
    daily["month"] = daily.index.to_period("M")
    daily["year"] = daily.index.year
    daily["days_in_month"] = daily.index.days_in_month

    grouped = daily.groupby("month")
    monthly = pd.DataFrame(
        {
            "valid_days": grouped["valid"].sum().astype(int),
            "days_in_month": grouped["days_in_month"].first().astype(int),
        }
    )
    aggregation = metadata["aggregation"]
    monthly["value"] = (
        grouped["value"].sum(min_count=1)
        if aggregation == "sum"
        else grouped["value"].mean()
    )
    monthly["completeness"] = monthly["valid_days"] / monthly["days_in_month"] * 100
    if aggregation == "sum":
        monthly["value"] = (
            monthly["value"] / monthly["valid_days"] * monthly["days_in_month"]
        )
    monthly.loc[monthly["completeness"] < 80, "value"] = np.nan
    monthly.index = monthly.index.to_timestamp()
    monthly.index.name = "date"
    monthly["year"] = monthly.index.year

    clean = monthly.dropna(subset=["value"])
    rain = aggregation == "sum"
    annual_groups = clean.groupby("year")
    if rain:
        annual = annual_groups["value"].sum(min_count=12)
    else:
        annual_numerator = (
            clean["value"] * clean["valid_days"]
        ).groupby(clean["year"]).sum(min_count=12)
        annual_denominator = clean["valid_days"].groupby(clean["year"]).sum(min_count=12)
        annual = annual_numerator / annual_denominator
    annual = annual.dropna().sort_index()
    if len(annual) < 8 or not np.all(np.diff(annual.index.to_numpy(dtype=int)) == 1):
        annual = pd.Series(dtype=float, name="value")

    valid_days = int(daily["valid"].sum())
    return {
        "daily": daily,
        "monthly": monthly,
        "annual": annual,
        "valid_days": valid_days,
        "expected_days": len(daily),
        "completeness": valid_days / len(daily) * 100 if len(daily) else 0.0,
    }
