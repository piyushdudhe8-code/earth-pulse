from __future__ import annotations

import json
from html import escape
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock
from time import monotonic, sleep
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from scipy.stats import theilslopes

from .analysis import hamed_rao_mann_kendall
from .data import CITIES
from .environmental import (
    ENVIRONMENTAL_PARAMETERS,
    fetch_nasa_daily,
    summarize_daily_series,
)
from .globe import render_earth_globe
from .interpretation import parameter_interpretation


NOMINATIM_URL = "https://nominatim.openstreetmap.org"
NOMINATIM_HEADERS = {
    "User-Agent": "EARTH-PULSE/1.0 (https://github.com/piyushdudhe8-code/earth-pulse)"
}
_NOMINATIM_LOCK = Lock()
_LAST_NOMINATIM_REQUEST = 0.0


def _nominatim_get(path: str, params: dict[str, Any]) -> requests.Response:
    global _LAST_NOMINATIM_REQUEST
    with _NOMINATIM_LOCK:
        wait = 1.0 - (monotonic() - _LAST_NOMINATIM_REQUEST)
        if wait > 0:
            sleep(wait)
        try:
            return requests.get(
                f"{NOMINATIM_URL}/{path}",
                params=params,
                headers=NOMINATIM_HEADERS,
                timeout=15,
            )
        finally:
            _LAST_NOMINATIM_REQUEST = monotonic()

_AUDIENCE_CONTEXT = {
    "Farmer": (
        "Temperature, rainfall, soil moisture, humidity, wind and sunlight can provide "
        "environmental context for farming. This is not a crop-specific or irrigation recommendation."
    ),
    "Agricultural Trader": (
        "Environmental conditions can be relevant to storage and transport planning. "
        "This app does not provide mandi prices, arrivals, forecasts or market advice."
    ),
    "Student": (
        "Each point is a NASA gridded/model or satellite-derived estimate. The graph shows "
        "observations over time, not a local field sensor."
    ),
    "Researcher": (
        "Check the selected product, source transitions, missing observations, units and "
        "grid resolution before using this series in research."
    ),
    "General User": (
        "This is a way to explore environmental patterns around a location; it does not "
        "identify the cause of a change."
    ),
}


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_nasa_daily_fetch(
    latitude: float,
    longitude: float,
    variable: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    return fetch_nasa_daily(latitude, longitude, variable, start_date, end_date)


@st.cache_data(ttl=30 * 24 * 60 * 60, show_spinner=False)
def _search_places(query: str) -> list[dict[str, Any]]:
    try:
        response = _nominatim_get(
            "search",
            {
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": 5,
            },
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"OpenStreetMap place search failed: {exc}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("OpenStreetMap place search returned invalid JSON.") from exc
    if not isinstance(payload, list):
        raise RuntimeError("OpenStreetMap place search returned an unexpected response.")

    results = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            latitude = float(item["lat"])
            longitude = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        results.append(
            {
                "name": item.get("display_name", "Unnamed place"),
                "latitude": latitude,
                "longitude": longitude,
                "address": item.get("address", {}),
            }
        )
    return results


@st.cache_data(ttl=30 * 24 * 60 * 60, show_spinner=False)
def _reverse_geocode(latitude: float, longitude: float) -> dict[str, Any]:
    try:
        response = _nominatim_get(
            "reverse",
            {
                "lat": f"{latitude:.6f}",
                "lon": f"{longitude:.6f}",
                "format": "jsonv2",
                "zoom": 10,
                "addressdetails": 1,
            },
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"OpenStreetMap location lookup failed: {exc}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("OpenStreetMap location lookup returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("OpenStreetMap location lookup returned an unexpected response.")
    address = payload.get("address")
    return {
        "display_name": str(payload.get("display_name") or ""),
        "address": address if isinstance(address, dict) else {},
    }


def _address_summary(address: dict[str, Any]) -> str:
    place = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
        or address.get("state_district")
    )
    fields = [place, address.get("state"), address.get("country")]
    return ", ".join(str(field) for field in fields if field)


@st.cache_data(show_spinner=False)
def _load_pilot_locations() -> dict[str, list[dict[str, Any]]]:
    path = Path(__file__).with_name("pilot_locations.json")
    try:
        with path.open(encoding="utf-8") as source:
            payload = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load the pilot location registry: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Pilot location registry must contain a JSON object.")
    for key in ("farmer_regions", "trade_markets"):
        entries = payload.get(key)
        if not isinstance(entries, list):
            raise RuntimeError(f"Pilot location registry is missing {key}.")
        for entry in entries:
            if not isinstance(entry, dict):
                raise RuntimeError(f"Pilot location registry contains an invalid {key} entry.")
            if not (-90 <= float(entry["latitude"]) <= 90 and -180 <= float(entry["longitude"]) <= 180):
                raise RuntimeError(f"Pilot location has invalid coordinates: {entry.get('name', 'unknown')}.")
    return payload


def _year_range(variable: str, now: date) -> tuple[int, int]:
    first_year = date.fromisoformat(ENVIRONMENTAL_PARAMETERS[variable]["start_date"]).year
    return max(first_year, now.year - 10), now.year


def _trend_summary(summary: dict[str, Any], variable: str) -> dict[str, Any] | None:
    if variable == "Sunlight":
        return None
    annual = summary["annual"]
    if len(annual) < 8:
        return None

    years = annual.index.to_numpy(dtype=float)
    values = annual.to_numpy(dtype=float)
    test = hamed_rao_mann_kendall(values, alpha=0.05)
    slope = theilslopes(values, years, alpha=0.95)
    return {
        "direction": "increasing" if slope.slope > 0 else "decreasing" if slope.slope < 0 else "flat",
        "slope_per_decade": float(slope.slope * 10),
        "ci_low_per_decade": float(slope.low_slope * 10),
        "ci_high_per_decade": float(slope.high_slope * 10),
        "p_value": float(test["p"]),
        "significant": bool(test["p"] < 0.05),
        "year_count": len(annual),
    }


def _render_environmental_result(result: dict[str, Any], purpose: str) -> None:
    variable = result["variable"]
    metadata = ENVIRONMENTAL_PARAMETERS[variable]
    frame = result["frame"]
    summary = result["summary"]
    monthly = summary["monthly"].dropna(subset=["value"])
    latest = frame.attrs.get("latest_valid_date")
    country_aggregate = result.get("country_aggregate")
    unit = metadata["unit"]

    st.subheader(f"{result['location']} · {metadata['short_name']}")
    st.caption(
        f"{metadata['scientific_name']} · {metadata['description']} "
        f"({metadata['parameter']})"
    )
    if latest:
        if country_aggregate:
            st.info(
                f"Estimated country aggregate from {country_aggregate['contributing_locations']} "
                f"valid sample locations. Latest NASA observation returned: {latest}. "
                "This is not a single coordinate's value or an area-weighted national statistic."
            )
        else:
            st.info(
                f"Location selected by the user. Latest NASA observation returned: {latest}. "
                "NASA POWER is periodically updated, not a live sensor."
            )
    else:
        st.warning(
            "NASA POWER returned no valid observations for this parameter and location. "
            "No substitute or synthetic values are shown."
        )
        st.caption(
            f"Requested {metadata['parameter']} from {frame.attrs.get('requested_start')} "
            f"to {frame.attrs.get('requested_end')} · Sources: "
            f"{frame.attrs.get('data_sources')} · Resolution: "
            f"{frame.attrs.get('spatial_resolution')} · "
            f"Missing days: {summary['expected_days']} / {summary['expected_days']}."
        )
        if metadata.get("product_note"):
            st.info(metadata["product_note"])
        if country_aggregate:
            st.caption(
                f"Candidate sample points: {country_aggregate['sample_count']} · "
                f"unique request coordinates: {country_aggregate['unique_request_count']} · "
                f"successful requests: {country_aggregate['successful_request_count']} · "
                f"valid sample locations: {country_aggregate['contributing_locations']} · "
                f"{country_aggregate['aggregation_method']}"
            )
        return

    if monthly.empty:
        st.warning("There are not enough valid days to form a complete month in this period.")
        if metadata.get("product_note"):
            st.info(metadata["product_note"])
        return

    metrics = st.columns(4 if country_aggregate else 3)
    metrics[0].metric("Latest monthly value", f"{monthly.iloc[-1]['value']:.2f} {unit}")
    metrics[1].metric("Daily data completeness", f"{summary['completeness']:.1f}%")
    metrics[2].metric("Valid daily observations", f"{summary['valid_days']} / {summary['expected_days']}")
    if country_aggregate:
        metrics[3].metric(
            "Contributing sample points",
            f"{country_aggregate['contributing_locations']} / {country_aggregate['unique_request_count']}",
        )

    chart_title = (
        "Monthly estimated precipitation total"
        if variable == "Rainfall"
        else f"Monthly {metadata['scientific_name'].lower()}"
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=monthly.index,
            y=monthly["value"],
            mode="lines+markers",
            name=chart_title,
            line=dict(color="#80d9b5", width=2),
            marker=dict(size=4),
            customdata=(
                monthly[["valid_days", "completeness", "valid_locations"]].to_numpy()
                if country_aggregate
                else monthly[["valid_days", "completeness"]].to_numpy()
            ),
            hovertemplate=(
                "%{x|%b %Y}<br>%{y:.2f} "
                f"{unit}<br>Valid days: %{{customdata[0]}}"
                "<br>Month completeness: %{customdata[1]:.1f}%"
                "<br>Mean valid sample locations: %{customdata[2]:.1f}<extra></extra>"
                if country_aggregate
                else
                "%{x|%b %Y}<br>%{y:.2f} "
                f"{unit}<br>Valid days: %{{customdata[0]}}"
                "<br>Month completeness: %{customdata[1]:.1f}%<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=390,
        margin=dict(l=10, r=10, t=24, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(7,17,15,.25)",
        yaxis_title=unit,
        xaxis_title="Month",
        hovermode="x unified",
        xaxis_rangeslider_visible=True,
    )
    st.plotly_chart(
        fig,
        width="stretch",
        config={"scrollZoom": True, "displaylogo": False, "responsive": True},
    )
    st.caption(
        "Monthly values are aggregated from daily observations. Months with under 80% "
        "valid daily data are omitted; gaps are not interpolated."
    )
    if country_aggregate:
        st.caption(
            f"Country estimate method: {country_aggregate['aggregation_method']} "
            f"Sample points: {', '.join(f'{lat:.2f}, {lon:.2f}' for lat, lon in country_aggregate['sample_points'])}."
        )
        if country_aggregate["duplicate_request_coordinates"]:
            st.caption(
                f"{country_aggregate['duplicate_request_coordinates']} duplicate rounded "
                "request coordinate(s) were omitted."
            )
        if country_aggregate["failures"]:
            st.warning(
                f"{len(country_aggregate['failures'])} sampled location request(s) failed; "
                "the aggregate uses only valid returned locations. "
                + " First error: "
                + country_aggregate["failures"][0]
            )
    if metadata.get("product_note"):
        st.info(metadata["product_note"])

    trend = result["trend"]
    if variable == "Sunlight":
        st.warning(
            "No significance or long-term trend is reported for this solar series. "
            "NASA POWER concatenates satellite products; source transitions may affect trends."
        )
    elif trend is None:
        st.info(
            "Trend analysis cannot be completed reliably: it needs at least eight "
            "consecutive years with enough monthly observations. The selected data do "
            "not meet that requirement."
        )
    else:
        trend_unit = "mm/year" if variable == "Rainfall" else unit
        per_decade = trend["slope_per_decade"]
        verdict = (
            f"{trend['direction'].capitalize()} trend: {per_decade:+.3f} {trend_unit} "
            f"per decade (95% Sen's-slope CI "
            f"{trend['ci_low_per_decade']:+.3f} to {trend['ci_high_per_decade']:+.3f}). "
            f"Hamed–Rao modified Mann–Kendall p={trend['p_value']:.4f}; "
            f"{'statistically significant at 5%' if trend['significant'] else 'not statistically significant at 5%'}."
        )
        st.markdown("**Trend findings**")
        st.write(verdict)
        st.caption(
            "Trend tests describe patterns, not causes. Annual aggregation, missing data "
            "and model/grid uncertainty remain important limitations."
        )

    annual = summary["annual"]
    if not annual.empty:
        years = annual.index.to_numpy(dtype=float)
        annual_unit = "mm/year" if variable == "Rainfall" else unit
        annual_figure = go.Figure()
        annual_figure.add_trace(
            go.Scatter(
                x=annual.index,
                y=annual.values,
                mode="lines+markers",
                name="Annual aggregate",
                line=dict(color="#80d9b5", width=2),
            )
        )
        if trend is not None and variable != "Sunlight":
            slope = trend["slope_per_decade"] / 10
            trend_line = annual.iloc[0] + slope * (years - years[0])
            annual_figure.add_trace(
                go.Scatter(
                    x=annual.index,
                    y=trend_line,
                    mode="lines",
                    name="Sen's slope",
                    line=dict(color="#f2c879", width=2, dash="dash"),
                )
            )
        annual_figure.update_layout(
            template="plotly_dark",
            height=330,
            margin=dict(l=10, r=10, t=18, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(7,17,15,.25)",
            yaxis_title=annual_unit,
            xaxis_title="Year",
            hovermode="x unified",
        )
        st.markdown("**Annual historical series**")
        st.plotly_chart(
            annual_figure,
            width="stretch",
            config={"displaylogo": False, "responsive": True},
        )

    values = monthly["value"]
    q1, q3 = values.quantile([0.25, 0.75])
    spread = q3 - q1
    unusual = monthly[(monthly["value"] < q1 - 1.5 * spread) | (monthly["value"] > q3 + 1.5 * spread)]
    if not unusual.empty:
        dates = ", ".join(unusual.index.strftime("%b %Y").tolist()[:5])
        st.write(
            f"Exploratory unusual observations (1.5×IQR screen; not event attribution): "
            f"{len(unusual)} month(s), including {dates}."
        )
    else:
        st.write("No monthly values crossed the exploratory 1.5×IQR screen in this period.")

    context = _AUDIENCE_CONTEXT[purpose]
    st.markdown("**Why this may matter**")
    st.write(context)
    guidance = parameter_interpretation(metadata["parameter"])
    if guidance:
        st.subheader("What does this mean?")
        for label, key in (
            ("Measured", "measured"),
            ("A rising trend", "rising"),
            ("A falling trend", "falling"),
            ("Why it may matter", "matters"),
            ("What it cannot tell us", "cannot_tell"),
            ("Limitations", "limitations"),
        ):
            st.markdown(f"**{label}:** {guidance[key]}")

    api_lat = frame.attrs.get("api_latitude")
    api_lon = frame.attrs.get("api_longitude")
    api_location = (
        f"{api_lat:.3f}, {api_lon:.3f}"
        if isinstance(api_lat, (int, float)) and isinstance(api_lon, (int, float))
        else "not provided by this response"
    )
    st.markdown("**Data information and limitations**")
    st.write(
        f"Location: {result['location']} ({result['latitude']:.4f}, {result['longitude']:.4f}) · "
        f"Source: {frame.attrs.get('source')} · Dataset / product: {frame.attrs.get('data_sources')} · "
        f"Coordinate reported by NASA POWER: {api_location} · "
        f"Native resolution: {frame.attrs.get('spatial_resolution')}."
    )
    if country_aggregate:
        st.caption(
            f"Estimated country/region aggregate · {country_aggregate['sample_count']} "
            f"candidate boundary-validated points; {country_aggregate['unique_request_count']} "
            f"unique rounded request coordinates; {country_aggregate['successful_request_count']} "
            f"successful requests; {country_aggregate['contributing_locations']} "
            "locations with valid observations. "
            "Natural Earth 1:110m boundaries are generalized; the estimate is not "
            "area-weighted and does not represent every local climate. NASA POWER does "
            "not return snapped grid-cell centers, so boundary validation applies to "
            "request coordinates, not necessarily the underlying source cells."
        )
    st.caption(
        f"Observation period requested: {frame.attrs.get('requested_start')} to "
        f"{frame.attrs.get('requested_end')} · Latest valid observation: {latest} · "
        f"Temporal resolution: daily, displayed as monthly aggregates · "
        f"Total valid observations: {summary['valid_days']} · "
        f"Missing observations: {summary['expected_days'] - summary['valid_days']} · "
        f"Data coverage: {summary['completeness']:.1f}% · "
        f"Analysis method: {('no long-term trend reported because source transitions can affect the solar record' if variable == 'Sunlight' else 'annual aggregates; Hamed–Rao modified Mann–Kendall test and Sen’s slope')}. "
        "NASA gridded/model or satellite estimates are not local station or field-sensor measurements."
    )
    st.caption(
        "Meteorological POWER data may be delayed by around two days; solar data may be "
        "delayed by around five to seven days. The actual latest date above comes from "
        "the returned valid observations, not the device-location timestamp."
    )


def _render_feedback() -> None:
    with st.expander("Help us understand your needs"):
        st.caption(
            "Optional. Feedback is kept only in this Streamlit session; it is not "
            "persisted or sent to a feedback service."
        )
        with st.form("location_explorer_feedback"):
            concern = st.selectbox(
                "Which environmental change affects your work most?",
                ["Temperature", "Rainfall", "Soil moisture", "Humidity", "Wind", "Sunlight", "Other"],
            )
            useful = st.text_input("What information would help you most?")
            rainfall = st.selectbox("Is rainfall information useful to your decisions?", ["", "Yes", "No"])
            soil = st.selectbox("Do you want to understand soil moisture changes?", ["", "Yes", "No"])
            temperature = st.selectbox("Is temperature variation important for your area?", ["", "Yes", "No"])
            submitted = st.form_submit_button("Submit feedback")
        if submitted:
            st.session_state["location_explorer_feedback"] = {
                "concern": concern,
                "useful": useful,
                "rainfall": rainfall,
                "soil_moisture": soil,
                "temperature": temperature,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
            st.success("Thank you. Your feedback remains only in this session.")


def render_location_explorer(location_picker: Any, language: str = "English") -> None:
    is_hi = language == "हिन्दी"
    st.markdown(
        "<div class='eyebrow'>LOCATION-AWARE ENVIRONMENTAL INVESTIGATION</div>",
        unsafe_allow_html=True,
    )
    st.subheader(
        "एक समय में एक पर्यावरणीय संकेत की जांच करें"
        if is_hi
        else "Investigate one environmental signal at a time"
    )
    st.caption(
        "Your location is used only after you choose it and confirm an investigation. "
        "NASA POWER observations are delayed and gridded; they are not live farm or street sensors."
    )

    locations = _load_pilot_locations()
    methods = [
        "Saved city",
        "Current device location",
        "Manual coordinates",
        "Search by place",
        "Farmer pilot",
        "Mandi pilot",
    ]
    method_labels_hi = {
        "Saved city": "शहर चुनें",
        "Current device location": "डिवाइस का वर्तमान स्थान",
        "Manual coordinates": "निर्देशांक दर्ज करें",
        "Search by place": "स्थान खोजें",
        "Farmer pilot": "किसान क्षेत्र पायलट",
        "Mandi pilot": "मंडी पायलट",
    }
    method = st.selectbox(
        "जांच का स्थान" if is_hi else "Investigation location",
        methods,
        key="location_explorer_method",
        format_func=lambda value: method_labels_hi[value] if is_hi else value,
    )

    selected_coordinates: tuple[float, float] | None = None
    location_name = ""
    location_source = method
    location_detail: dict[str, Any] = {}

    if method == "Saved city":
        city = st.selectbox("City", list(CITIES), key="location_explorer_city")
        selected_coordinates = (
            CITIES[city]["latitude"],
            CITIES[city]["longitude"],
        )
        location_name = city
    elif method == "Current device location":
        location_response = location_picker(
            buttonLabel="Use My Current Location / Refresh Location",
            helpText="Your browser asks permission only when you press the button.",
            pendingText="Requesting a fresh location reading…",
            successText="Location detected. Review the coordinates before continuing.",
            confirmLabel="Confirm this location",
            confirmedText="Location confirmed for this investigation.",
            deniedText="Location permission was denied. Choose a city, search, or enter coordinates.",
            unavailableText="Location is unavailable. Choose a city, search, or enter coordinates.",
            key="location_explorer_geolocation",
            default=None,
        )
        if isinstance(location_response, dict):
            request_id = location_response.get("requestId")
            if request_id and request_id != st.session_state.get("location_explorer_seen_request"):
                st.session_state.location_explorer_seen_request = request_id
                if location_response.get("status") == "granted":
                    st.session_state.location_explorer_gps = {
                        "latitude": float(location_response["latitude"]),
                        "longitude": float(location_response["longitude"]),
                        "accuracy": float(location_response.get("accuracy", float("nan"))),
                        "timestamp": int(location_response.get("timestamp", 0)),
                    }
                    st.session_state.location_explorer_gps_error = None
                elif location_response.get("status") == "pending":
                    st.session_state.location_explorer_gps = None
                    st.session_state.location_explorer_gps_error = None
                else:
                    st.session_state.location_explorer_gps = None
                    st.session_state.location_explorer_gps_error = location_response.get("status")

        gps = st.session_state.get("location_explorer_gps")
        if gps:
            selected_coordinates = (gps["latitude"], gps["longitude"])
            location_name = "Device location"
            location_detail = gps
            timestamp = gps["timestamp"]
            if timestamp:
                detected_at = datetime.fromtimestamp(timestamp / 1000, timezone.utc).astimezone()
                st.caption(
                    f"Detected {detected_at:%Y-%m-%d %H:%M %Z} · "
                    f"GPS accuracy ±{gps['accuracy']:.0f} m · "
                    f"{gps['latitude']:.5f}, {gps['longitude']:.5f}"
                )
            if np.isfinite(gps["accuracy"]) and gps["accuracy"] > 5000:
                st.warning("GPS accuracy is coarse. You can refresh or choose a more precise location.")
            if st.button("Clear device location", key="location_explorer_clear_gps"):
                st.session_state.location_explorer_gps = None
                st.session_state.location_explorer_result = None
                st.rerun()
        else:
            status = st.session_state.get("location_explorer_gps_error")
            if status:
                st.warning(
                    "Location was not available. You can still investigate by city, place search, "
                    "a pilot region, or manual coordinates."
                )
    elif method == "Manual coordinates":
        left, right = st.columns(2)
        latitude = left.number_input(
            "Latitude (−90 to +90)",
            min_value=-90.0,
            max_value=90.0,
            value=28.6139,
            format="%.4f",
            key="location_explorer_latitude",
        )
        longitude = right.number_input(
            "Longitude (−180 to +180)",
            min_value=-180.0,
            max_value=180.0,
            value=77.2090,
            format="%.4f",
            key="location_explorer_longitude",
        )
        selected_coordinates = (latitude, longitude)
        location_name = f"Manual point ({latitude:.4f}, {longitude:.4f})"
    elif method == "Search by place":
        st.caption(
            "Place search uses OpenStreetMap Nominatim. Your search text is sent only "
            "when you press Search; GPS coordinates are not sent to place search."
        )
        st.caption("Geocoding attribution: OpenStreetMap contributors.")
        with st.form("location_explorer_place_search"):
            place_query = st.text_input("City, district, or postal code", key="location_explorer_query")
            search_submitted = st.form_submit_button("Search places")
        if search_submitted:
            st.session_state.location_explorer_search_results = []
            if place_query.strip():
                try:
                    st.session_state.location_explorer_search_results = _search_places(place_query.strip())
                except RuntimeError as exc:
                    st.error(str(exc))
        search_results = st.session_state.get("location_explorer_search_results", [])
        if search_results:
            selected_index = st.selectbox(
                "Search result",
                range(len(search_results)),
                format_func=lambda index: search_results[index]["name"],
                key="location_explorer_search_choice",
            )
            place = search_results[selected_index]
            selected_coordinates = (place["latitude"], place["longitude"])
            location_name = place["name"]
            location_source = "OpenStreetMap place search"
            location_detail = place.get("address", {})
        elif search_submitted:
            st.info("No matching places were returned. Try a more specific name or enter coordinates.")
    elif method in ("Farmer pilot", "Mandi pilot"):
        group_key = "farmer_regions" if method == "Farmer pilot" else "trade_markets"
        candidates = locations[group_key]
        selected_index = st.selectbox(
            "Explore agricultural regions",
            range(len(candidates)),
            format_func=lambda index: (
                f"{candidates[index]['name']}, {candidates[index]['state']}"
            ),
            key=f"location_explorer_{group_key}",
        )
        pilot = candidates[selected_index]
        selected_coordinates = (float(pilot["latitude"]), float(pilot["longitude"]))
        location_name = f"{pilot['name']}, {pilot['state']}"
        location_source = pilot["category"]
        location_detail = pilot
        st.info("Exploring a selected pilot location — not your current device location.")
        st.caption(pilot["source"])

    if selected_coordinates and method in ("Current device location", "Manual coordinates"):
        coordinate_signature = (
            round(selected_coordinates[0], 5),
            round(selected_coordinates[1], 5),
        )
        resolved_place = st.session_state.get("location_explorer_reverse_place")
        if (
            isinstance(resolved_place, dict)
            and resolved_place.get("coordinates") == coordinate_signature
        ):
            place = resolved_place["place"]
            if place.get("display_name"):
                location_name = place["display_name"]
            location_detail = place.get("address", {})
        elif st.button(
            "Confirm coordinates and look up city / district / state",
            key="location_explorer_reverse_lookup",
        ):
            try:
                place = _reverse_geocode(*selected_coordinates)
                st.session_state.location_explorer_reverse_place = {
                    "coordinates": coordinate_signature,
                    "place": place,
                }
                if place.get("display_name"):
                    location_name = place["display_name"]
                    location_detail = place.get("address", {})
                else:
                    st.info("No readable place name was returned. You can continue using coordinates.")
            except RuntimeError as exc:
                st.warning(f"{exc} You can continue using coordinates.")

    if selected_coordinates:
        st.markdown(
            f"<div class='panel'><strong>Current investigation location</strong><br>"
            f"{escape(location_name)}<br><span class='muted'>"
            f"{location_source} · {selected_coordinates[0]:.4f}, "
            f"{selected_coordinates[1]:.4f}</span></div>",
            unsafe_allow_html=True,
        )
        if location_detail:
            address_text = _address_summary(location_detail)
            if address_text:
                st.caption(f"District/state/country: {address_text}")

    left, right = st.columns([0.9, 1.1])
    now = datetime.now(timezone.utc).date()
    with left:
        icons = dict(
            zip(ENVIRONMENTAL_PARAMETERS, ("🌡️", "🌧️", "💧", "🌱", "💨", "☀️"))
        )
        labels = {
            key: f"{icons[key]} {metadata['short_name']} · {metadata['scientific_name']}"
            for key, metadata in ENVIRONMENTAL_PARAMETERS.items()
        }
        variable = st.radio(
            "केवल एक पर्यावरणीय संकेत चुनें" if is_hi else "Environmental signal — choose one",
            list(ENVIRONMENTAL_PARAMETERS),
            format_func=lambda key: labels[key],
            key="location_explorer_parameter",
        )
        metadata = ENVIRONMENTAL_PARAMETERS[variable]
        st.caption(f"{metadata['description']} · Unit: {metadata['unit']}")
        if variable == "Sunlight":
            st.caption("Solar source history changes; no long-term trend will be asserted.")
        purpose = st.selectbox(
            "Your purpose (optional)",
            ["General User", "Farmer", "Agricultural Trader", "Student", "Researcher"],
            key="location_explorer_purpose",
        )
        first_year, last_year = _year_range(variable, now)
        start_year, end_year = st.slider(
            "Analysis years",
            min_value=first_year,
            max_value=last_year,
            value=(max(first_year, last_year - 10), last_year),
            key=f"location_explorer_years_{variable}",
        )
    with right:
        render_earth_globe(
            height=440,
            latitude=selected_coordinates[0] if selected_coordinates else None,
            longitude=selected_coordinates[1] if selected_coordinates else None,
        )
        st.caption("The gold marker shows the selected point. It is not a data heatmap.")

    start_date = max(
        date(start_year, 1, 1),
        date.fromisoformat(metadata["start_date"]),
    )
    end_date = min(date(end_year, 12, 31), now)
    st.caption(
        "The NASA request is made only after you click the confirmation button. "
        "A GPS fix is not sent to a place-search service unless you separately confirm "
        "the place-name lookup. Coordinates are sent to NASA POWER only after you confirm "
        "the investigation."
    )
    submitted = st.button(
        "Confirm location and load NASA data" if selected_coordinates else "Choose a location to continue",
        type="primary",
        width="stretch",
        key="location_explorer_submit",
        disabled=selected_coordinates is None,
    )

    signature = (
        variable,
        round(selected_coordinates[0], 5) if selected_coordinates else None,
        round(selected_coordinates[1], 5) if selected_coordinates else None,
        start_date.isoformat(),
        end_date.isoformat(),
        location_source,
        location_name,
    )
    if submitted and selected_coordinates:
        st.session_state.location_explorer_result = None
        latitude, longitude = selected_coordinates
        try:
            with st.spinner("Fetching the selected NASA POWER daily series…"):
                frame = cached_nasa_daily_fetch(
                    latitude,
                    longitude,
                    variable,
                    start_date.isoformat(),
                    end_date.isoformat(),
                )
                resolved_name = location_name
                summary = summarize_daily_series(frame, variable)
                st.session_state.location_explorer_result = {
                    "frame": frame,
                    "summary": summary,
                    "trend": _trend_summary(summary, variable),
                    "variable": variable,
                    "location": resolved_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "location_source": location_source,
                }
                st.session_state.location_explorer_signature = signature
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))

    result = st.session_state.get("location_explorer_result")
    if result and st.session_state.get("location_explorer_signature") == signature:
        st.divider()
        _render_environmental_result(result, purpose)
    elif result:
        st.info("Your selection changed. Confirm it to load the matching NASA observations.")

    _render_feedback()
