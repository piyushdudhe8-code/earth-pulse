from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from .environmental import ENVIRONMENTAL_PARAMETERS, fetch_nasa_daily, summarize_daily_series
from .geography import country_name, sample_country_points


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def _cached_point_series(
    latitude: float,
    longitude: float,
    variable: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    return fetch_nasa_daily(latitude, longitude, variable, start_date, end_date)


def aggregate_country_series(
    feature: dict[str, Any],
    anchor: tuple[float, float],
    variable: str,
    start_date: str,
    end_date: str,
    max_points: int = 5,
) -> dict[str, Any]:
    """Estimate a country series from several boundary-validated NASA POWER points."""
    if variable not in ENVIRONMENTAL_PARAMETERS:
        raise ValueError(f"Unsupported environmental parameter: {variable}")
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("Start date must be before end date.")

    sample_points = sample_country_points(feature, anchor=anchor, max_points=max_points)
    if len(sample_points) < 2:
        raise ValueError(
            "The bundled country boundary does not contain two suitable sample points; "
            "a country aggregate is not reported."
        )

    frames: list[pd.DataFrame] = []
    requested_coordinates: set[tuple[float, float]] = set()
    duplicate_request_coordinates = 0
    failures: list[str] = []
    for latitude, longitude in sample_points:
        request_coordinate = (round(latitude, 4), round(longitude, 4))
        if request_coordinate in requested_coordinates:
            duplicate_request_coordinates += 1
            continue
        requested_coordinates.add(request_coordinate)
        try:
            frame = _cached_point_series(
                request_coordinate[0],
                request_coordinate[1],
                variable,
                start_date,
                end_date,
            )
        except (RuntimeError, ValueError) as exc:
            failures.append(f"{latitude:.3f}, {longitude:.3f}: {exc}")
            continue
        frames.append(frame)

    if not frames:
        detail = "; ".join(failures[:2]) or "No NASA POWER responses were returned."
        raise RuntimeError(f"No sampled locations could be loaded. {detail}")

    named_frames = [
        frame.rename(columns={"value": str(index)})[[str(index)]]
        for index, frame in enumerate(frames)
    ]
    point_values = pd.concat(named_frames, axis=1).sort_index()
    valid_location_count = point_values.notna().sum(axis=1).astype(int)
    contributing_locations = int(point_values.notna().any(axis=0).sum())
    if contributing_locations == 1:
        raise RuntimeError(
            "Only one sampled location returned valid observations. A country-level "
            "aggregate requires at least two valid sample locations."
        )

    minimum_daily_locations = max(1, math.ceil(contributing_locations / 2))
    daily = pd.DataFrame(
        {
            "value": point_values.mean(axis=1, skipna=True),
            "valid_locations": valid_location_count,
        },
        index=point_values.index,
    )
    daily.loc[daily["valid_locations"] < minimum_daily_locations, "value"] = np.nan
    summary = summarize_daily_series(daily[["value"]], variable)
    daily.attrs["source"] = "NASA POWER Daily API; multi-point country estimate"
    daily.attrs["data_sources"] = "; ".join(sorted({
        str(frame.attrs.get("data_sources", "NASA POWER; source not identified"))
        for frame in frames
    }))
    daily.attrs["parameter"] = ENVIRONMENTAL_PARAMETERS[variable]["parameter"]
    daily.attrs["spatial_resolution"] = ENVIRONMENTAL_PARAMETERS[variable]["resolution"]
    daily.attrs["unit"] = ENVIRONMENTAL_PARAMETERS[variable]["unit"]
    daily.attrs["api_version"] = "; ".join(sorted({
        str(frame.attrs.get("api_version", "unknown")) for frame in frames
    }))
    daily.attrs["requested_start"] = start.isoformat()
    daily.attrs["requested_end"] = end.isoformat()
    daily.attrs["retrieved_at"] = max(
        (str(frame.attrs.get("retrieved_at", "")) for frame in frames),
        default="",
    )
    daily.attrs["request_url"] = "Multiple cached NASA POWER daily point requests"
    daily.attrs["latest_valid_date"] = (
        daily.index[daily["value"].notna()].max().date().isoformat()
        if daily["value"].notna().any()
        else None
    )

    month_location_counts = (
        daily["valid_locations"]
        .where(daily["value"].notna())
        .groupby(daily.index.to_period("M"))
        .mean()
    )
    summary["monthly"]["valid_locations"] = month_location_counts.reindex(
        summary["monthly"].index.to_period("M")
    ).to_numpy()
    summary["monthly"]["valid_locations"] = summary["monthly"]["valid_locations"].fillna(0)

    return {
        "country": country_name(feature),
        "frame": daily,
        "summary": summary,
        "sample_points": sample_points,
        "sample_count": len(sample_points),
        "unique_request_count": len(requested_coordinates),
        "successful_request_count": len(frames),
        "duplicate_request_coordinates": duplicate_request_coordinates,
        "contributing_locations": contributing_locations,
        "minimum_daily_locations": minimum_daily_locations,
        "aggregation_method": (
            "Unweighted arithmetic mean of daily NASA POWER point estimates. "
            f"A date is retained only when at least {minimum_daily_locations} "
            f"of {contributing_locations} contributing sample locations are valid. "
            "Sample request coordinates lie inside the selected boundary, but NASA "
            "POWER point responses do not identify snapped grid-cell centers; the "
            "samples are not guaranteed to represent distinct cells."
        ),
        "failures": failures,
    }