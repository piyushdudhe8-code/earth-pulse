from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import requests

NASA_MONTHLY_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"

CITIES: dict[str, dict[str, float]] = {
    "Delhi": {"latitude": 28.6139, "longitude": 77.2090},
    "Mumbai": {"latitude": 19.0760, "longitude": 72.8777},
    "Nagpur": {"latitude": 21.1458, "longitude": 79.0882},
    "Pune": {"latitude": 18.5204, "longitude": 73.8567},
    "Bengaluru": {"latitude": 12.9716, "longitude": 77.5946},
    "Chennai": {"latitude": 13.0827, "longitude": 80.2707},
    "Kolkata": {"latitude": 22.5726, "longitude": 88.3639},
    "Hyderabad": {"latitude": 17.3850, "longitude": 78.4867},
    "Jaipur": {"latitude": 26.9124, "longitude": 75.7873},
    "Ahmedabad": {"latitude": 23.0225, "longitude": 72.5714},
    "Lucknow": {"latitude": 26.8467, "longitude": 80.9462},
    "Thane": {"latitude": 19.2183, "longitude": 72.9781},
}

VARIABLES: dict[str, dict[str, Any]] = {
    "Temperature": {
        "parameter": "T2M",
        "unit": "°C",
        "kind": "mean",
        "dataset": "NASA MERRA-2 meteorological archive via POWER",
        "spatial_resolution": "MERRA-2 native grid, approximately 0.5° latitude × 0.625° longitude",
        "description": "Average air temperature 2 metres above the surface.",
        "description_hi": "Zameen se 2 metre upar hawa ka ausat taapman.",
        "display": "Average temperature",
    },
    "Rainfall": {
        "parameter": "PRECTOTCORR",
        "unit": "mm/month (estimated)",
        "kind": "rain",
        "dataset": "NASA MERRA-2 meteorological archive via POWER",
        "spatial_resolution": "MERRA-2 native grid, approximately 0.5° latitude × 0.625° longitude",
        "description": "Corrected precipitation. NASA's monthly mean daily rate is converted to an estimated monthly total.",
        "description_hi": "Corrected precipitation. NASA ke monthly mean daily rate ko mahine ke dinon se guna karke estimated total banaya jata hai.",
        "display": "Estimated monthly rainfall",
    },
    "Relative humidity": {
        "parameter": "RH2M",
        "unit": "%",
        "kind": "mean",
        "dataset": "NASA MERRA-2 meteorological archive via POWER",
        "spatial_resolution": "MERRA-2 native grid, approximately 0.5° latitude × 0.625° longitude",
        "description": "Average relative humidity 2 metres above the surface.",
        "description_hi": "Zameen se 2 metre upar hawa ki relative humidity ka ausat.",
        "display": "Average relative humidity",
    },
    "Wind speed": {
        "parameter": "WS10M",
        "unit": "m/s",
        "kind": "mean",
        "dataset": "NASA MERRA-2 meteorological archive via POWER",
        "spatial_resolution": "MERRA-2 native grid, approximately 0.5° latitude × 0.625° longitude",
        "description": "Average wind speed 10 metres above the surface.",
        "description_hi": "Zameen se 10 metre upar hawa ki ausat raftaar.",
        "display": "Average wind speed",
    },
    "Sunlight": {
        "parameter": "ALLSKY_SFC_SW_DWN",
        "unit": "kWh/m²/day",
        "kind": "mean",
        "dataset": "NASA GEWEX SRB / CERES SYN1deg / CERES FLASHFlux solar archive via POWER",
        "spatial_resolution": "NASA POWER solar source-native grid, approximately 1° latitude × 1° longitude",
        "description": "Mean daily downward shortwave solar energy at the surface under all-sky conditions.",
        "description_hi": "सभी मौसम स्थितियों में सतह तक पहुंचने वाली औसत दैनिक सौर ऊर्जा।",
        "display": "Surface solar radiation",
        "trend_supported": False,
        "product_note": (
            "The solar record combines satellite products across time. Source transitions "
            "can affect long-term trends, so this app does not report a statistical trend "
            "for this parameter."
        ),
    },
}


def _valid_number(value: Any, fill_value: float = -999.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    if not np.isfinite(number) or number <= -900 or number == fill_value:
        return np.nan
    return number


def fetch_nasa_monthly(
    latitude: float,
    longitude: float,
    variable: str,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Fetch one monthly point series from the official NASA POWER API."""
    if variable not in VARIABLES:
        raise ValueError(f"Unsupported variable: {variable}")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Latitude/longitude are outside valid ranges.")
    if start_year > end_year:
        raise ValueError("Start year must be before end year.")

    parameter = VARIABLES[variable]["parameter"]
    params = {
        "parameters": parameter,
        "community": "RE",
        "longitude": f"{longitude:.4f}",
        "latitude": f"{latitude:.4f}",
        "start": str(start_year),
        "end": str(end_year),
        "format": "JSON",
    }
    headers = {"User-Agent": "EarthPulse/1.0 (student research prototype)"}
    try:
        response = requests.get(NASA_MONTHLY_URL, params=params, headers=headers, timeout=45)
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
        detail = response.text.strip()
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

    header = payload.get("header")
    header = header if isinstance(header, dict) else {}
    try:
        fill_value = float(header.get("fill_value", -999.0))
    except (TypeError, ValueError):
        fill_value = -999.0
    properties = payload.get("properties")
    parameters = properties.get("parameter") if isinstance(properties, dict) else None
    values = parameters.get(parameter) if isinstance(parameters, dict) else None
    if not isinstance(values, dict):
        message = payload.get("messages")
        detail = f" NASA POWER message: {message}" if message else ""
        raise RuntimeError(
            f"NASA POWER response did not contain monthly values for {parameter}.{detail}"
        )

    records: list[dict[str, Any]] = []
    for key, raw_value in values.items():
        if len(str(key)) != 6 or not str(key).isdigit():
            continue
        year, month = int(str(key)[:4]), int(str(key)[4:6])
        if month < 1 or month > 12 or year < start_year or year > end_year:
            continue
        records.append(
            {
                "date": pd.Timestamp(year=year, month=month, day=1),
                "value": _valid_number(raw_value, fill_value),
            }
        )

    if not records:
        raise RuntimeError("NASA POWER returned no monthly values for this request.")
    frame = pd.DataFrame(records).sort_values("date").drop_duplicates("date").set_index("date")
    expected = pd.date_range(f"{start_year}-01-01", f"{end_year}-12-01", freq="MS")
    frame = frame.reindex(expected)
    frame.index.name = "date"
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    if not frame["value"].notna().any():
        raise RuntimeError(
            f"NASA POWER returned no valid monthly observations for {parameter} "
            f"from {start_year} to {end_year}."
        )
    frame.attrs["source"] = "NASA POWER Monthly and Annual API (periodic monthly data; not instantaneous)"
    frame.attrs["parameter"] = parameter
    frame.attrs["request_url"] = response.url
    api = header.get("api")
    api = api if isinstance(api, dict) else {}
    sources = header.get("sources")
    sources = sources if isinstance(sources, list) else []
    parameter_details = payload.get("parameters")
    parameter_details = (
        parameter_details.get(parameter)
        if isinstance(parameter_details, dict)
        else None
    )
    parameter_details = parameter_details if isinstance(parameter_details, dict) else {}
    geometry = payload.get("geometry")
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    valid_count = int(frame["value"].notna().sum())
    frame.attrs.update(
        {
            "api_title": header.get("title", "NASA POWER Monthly and Annual API"),
            "api_version": api.get("version", "unknown"),
            "dataset": VARIABLES[variable]["dataset"],
            "data_sources": ", ".join(str(source) for source in sources) or "NASA POWER; source not identified",
            "api_unit": parameter_details.get("units", "not provided"),
            "api_long_name": parameter_details.get("longname", variable),
            "api_parameter_metadata": parameter_details.copy(),
            "display_unit": VARIABLES[variable]["unit"],
            "spatial_resolution": VARIABLES[variable]["spatial_resolution"],
            "api_longitude": coordinates[0] if isinstance(coordinates, list) and len(coordinates) >= 2 else None,
            "api_latitude": coordinates[1] if isinstance(coordinates, list) and len(coordinates) >= 2 else None,
            "api_elevation_m": coordinates[2] if isinstance(coordinates, list) and len(coordinates) >= 3 else None,
            "requested_start": f"{start_year}-01",
            "requested_end": f"{end_year}-12",
            "expected_observations": len(expected),
            "valid_observations": valid_count,
            "missing_observations": len(expected) - valid_count,
            "latest_valid_date": frame.index[frame["value"].notna()].max().strftime("%Y-%m"),
            "observed_start": frame.index[frame["value"].notna()].min().strftime("%Y-%m"),
            "observed_end": frame.index[frame["value"].notna()].max().strftime("%Y-%m"),
            "fill_value": fill_value,
            "response_header": header.copy(),
        }
    )
    frame.attrs["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    return frame


def prepare_monthly_series(frame: pd.DataFrame, variable: str) -> pd.DataFrame:
    """Normalize POWER monthly fields into display units and calculate completeness."""
    result = frame[["value"]].copy().sort_index()
    result["days"] = [monthrange(d.year, d.month)[1] for d in result.index]
    result["year"] = result.index.year
    result["month"] = result.index.month
    if VARIABLES[variable]["kind"] == "rain":
        # POWER monthly PRECTOTCORR is a monthly mean daily precipitation rate (mm/day).
        # Multiplication by the number of calendar days estimates monthly accumulation.
        result["display_value"] = result["value"] * result["days"]
    else:
        result["display_value"] = result["value"]
    return result


def make_demo_series(city: str, variable: str, start_year: int = 2004, end_year: int = 2025) -> pd.DataFrame:
    """Generate reproducible synthetic demo data. Never represent this as NASA data."""
    rng = np.random.default_rng(2026 + sum(ord(c) for c in city + variable))
    dates = pd.date_range(f"{start_year}-01-01", f"{end_year}-12-01", freq="MS")
    month = dates.month.to_numpy()
    year_index = dates.year.to_numpy() - start_year

    if variable == "Temperature":
        # Deliberate synthetic warming signal with a strong annual cycle.
        seasonal = 8.0 * np.cos(2 * np.pi * (month - 5) / 12)
        values = 25.0 + seasonal + 0.035 * year_index + rng.normal(0, 1.15, len(dates))
    elif variable == "Rainfall":
        # Synthetic monthly mean daily rate (mm/day); monsoon peak is Jun-Sep.
        seasonal_profile = np.array([0.7, 0.6, 0.8, 1.2, 3.0, 12.0, 18.0, 15.0, 8.0, 2.5, 1.0, 0.7])
        values = seasonal_profile[month - 1] * (1 - 0.004 * year_index)
        values = values * rng.lognormal(mean=0, sigma=0.16, size=len(dates))
    elif variable == "Relative humidity":
        seasonal = 18 * np.sin(2 * np.pi * (month - 6) / 12)
        values = 58 + seasonal + 0.04 * year_index + rng.normal(0, 3.0, len(dates))
    else:  # Wind speed
        seasonal = 0.6 * np.sin(2 * np.pi * (month - 6) / 12)
        values = 3.2 + seasonal + 0.006 * year_index + rng.normal(0, 0.22, len(dates))

    values = np.maximum(values, 0) if variable == "Rainfall" else values
    frame = pd.DataFrame({"value": values}, index=dates)
    frame.index.name = "date"
    frame.attrs["source"] = "DEMO DATA — synthetic, generated for demonstration only"
    frame.attrs["parameter"] = VARIABLES[variable]["parameter"]
    frame.attrs["api_version"] = "synthetic demo"
    frame.attrs["data_sources"] = "synthetic; not NASA data"
    frame.attrs["dataset"] = "Synthetic demonstration generator; not an observation dataset"
    frame.attrs["api_unit"] = "synthetic values"
    frame.attrs["display_unit"] = VARIABLES[variable]["unit"]
    frame.attrs["spatial_resolution"] = "Not applicable to synthetic demonstration data"
    frame.attrs["request_url"] = "N/A — synthetic demo data"
    return frame
