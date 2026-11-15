from __future__ import annotations

from datetime import date, datetime, timezone
from html import escape
from typing import Any

import streamlit as st

from .country_data import aggregate_country_series
from .data import CITIES
from .environmental import ENVIRONMENTAL_PARAMETERS, summarize_daily_series
from .explorer import (
    _address_summary,
    _load_pilot_locations,
    _render_feedback,
    _render_environmental_result,
    _reverse_geocode,
    _search_places,
    _trend_summary,
    cached_nasa_daily_fetch,
)
from .geography import country_name, identify_country, sample_country_points
from .globe import render_interactive_earth_globe


_LOCATION_METHODS = [
    "Globe selection",
    "Saved city",
    "Current device location",
    "Manual coordinates",
    "Search by place",
    "Farmer pilot",
    "Mandi pilot",
]


def _coordinates_from_state(
    method: str,
    pilots: dict[str, list[dict[str, Any]]],
) -> tuple[float, float] | None:
    if method == "Globe selection":
        point = st.session_state.get("global_explorer_globe_point")
        if isinstance(point, dict):
            return float(point["latitude"]), float(point["longitude"])
        return None
    if method == "Saved city":
        city = st.session_state.get("global_explorer_city", "Delhi")
        coordinates = CITIES.get(city)
        if coordinates:
            return coordinates["latitude"], coordinates["longitude"]
    elif method == "Current device location":
        gps = st.session_state.get("global_explorer_gps")
        if isinstance(gps, dict):
            return gps["latitude"], gps["longitude"]
    elif method == "Manual coordinates":
        return (
            float(st.session_state.get("global_explorer_latitude", 28.6139)),
            float(st.session_state.get("global_explorer_longitude", 77.2090)),
        )
    elif method == "Search by place":
        results = st.session_state.get("global_explorer_search_results", [])
        if results:
            index = int(st.session_state.get("global_explorer_search_choice", 0))
            if 0 <= index < len(results):
                place = results[index]
                return float(place["latitude"]), float(place["longitude"])
    elif method in ("Farmer pilot", "Mandi pilot"):
        key = "farmer_regions" if method == "Farmer pilot" else "trade_markets"
        candidates = pilots.get(key, [])
        index = int(st.session_state.get(f"global_explorer_{key}", 0))
        if 0 <= index < len(candidates):
            place = candidates[index]
            return float(place["latitude"]), float(place["longitude"])
    return None


def _place_name(
    method: str,
    coordinates: tuple[float, float],
    pilots: dict[str, list[dict[str, Any]]],
) -> str:
    latitude, longitude = coordinates
    if method == "Globe selection":
        point = st.session_state.get("global_explorer_globe_point", {})
        return str(point.get("name") or f"Selected point ({latitude:.4f}, {longitude:.4f})")
    if method == "Saved city":
        return str(st.session_state.get("global_explorer_city", "Delhi"))
    if method == "Current device location":
        return "Device location"
    if method == "Manual coordinates":
        return f"Manual point ({latitude:.4f}, {longitude:.4f})"
    if method == "Search by place":
        results = st.session_state.get("global_explorer_search_results", [])
        index = int(st.session_state.get("global_explorer_search_choice", 0))
        if 0 <= index < len(results):
            return str(results[index].get("name", "Selected place"))
    if method in ("Farmer pilot", "Mandi pilot"):
        key = "farmer_regions" if method == "Farmer pilot" else "trade_markets"
        candidates = pilots.get(key, [])
        index = int(st.session_state.get(f"global_explorer_{key}", 0))
        if 0 <= index < len(candidates):
            place = candidates[index]
            return f"{place['name']}, {place['state']}"
    return f"Point ({latitude:.4f}, {longitude:.4f})"


def _clear_globe_selection() -> None:
    st.session_state.pop("global_explorer_globe_point", None)
    st.session_state.pop("global_explorer_place", None)
    st.session_state.pop("global_explorer_result", None)
    st.session_state["global_explorer_method"] = "Saved city"


def _render_geolocation(location_picker: Any) -> None:
    response = location_picker(
        buttonLabel="Use My Current Location / Refresh",
        helpText="Your browser asks permission only when you request a fresh fix.",
        pendingText="Requesting a fresh location reading…",
        successText="Review the coordinates, then confirm the location.",
        confirmLabel="Confirm this location",
        confirmedText="Location confirmed for this investigation.",
        deniedText="Location permission was denied. Choose another location method.",
        unavailableText="Location is unavailable. Choose another location method.",
        key="global_explorer_geolocation",
        default=None,
    )
    if not isinstance(response, dict):
        return
    request_id = response.get("requestId")
    if not request_id or request_id == st.session_state.get("global_explorer_seen_gps_request"):
        return
    st.session_state.global_explorer_seen_gps_request = request_id
    if response.get("status") == "granted":
        st.session_state.global_explorer_gps = {
            "latitude": float(response["latitude"]),
            "longitude": float(response["longitude"]),
            "accuracy": float(response.get("accuracy", float("nan"))),
            "timestamp": int(response.get("timestamp", 0)),
        }
    elif response.get("status") == "pending":
        st.session_state.global_explorer_gps = None
    else:
        st.session_state.global_explorer_gps = None
        st.session_state.global_explorer_gps_error = str(response.get("status", "unavailable"))


def render_global_explorer(location_picker: Any, language: str = "English") -> None:
    """Render the four-mode app's click-anywhere, location-based investigation."""
    is_hi = language == "हिन्दी"
    try:
        pilots = _load_pilot_locations()
    except RuntimeError as exc:
        st.error(str(exc))
        pilots = {"farmer_regions": [], "trade_markets": []}

    st.markdown(
        "<div class='eyebrow'>INTERACTIVE GLOBAL EARTH EXPLORER</div>",
        unsafe_allow_html=True,
    )
    st.subheader("Click a place on Earth or choose a location" if not is_hi else "पृथ्वी पर क्लिक करें या स्थान चुनें")
    st.caption(
        "Country identity comes from bundled Natural Earth boundary polygons. NASA POWER is periodic gridded data, not a live sensor."
    )

    left, right = st.columns([0.85, 1.15], gap="large")
    method = st.session_state.get("global_explorer_method", "Saved city")
    if method not in _LOCATION_METHODS:
        method = "Saved city"
        st.session_state.global_explorer_method = method
    preview_coordinates = _coordinates_from_state(method, pilots)
    preview_marker = (
        {"latitude": preview_coordinates[0], "longitude": preview_coordinates[1]}
        if preview_coordinates
        else None
    )

    with right:
        globe_value = render_interactive_earth_globe(
            height=680,
            selected_location=preview_marker,
            key="global_explorer_globe",
        )
        st.caption(
            "Selected point marker only; the display is not a NASA data heatmap. "
            "Imagery detail is limited to the tile service's published maximum level."
        )

    if isinstance(globe_value, dict):
        click_id = globe_value.get("clickId")
        if click_id and click_id != st.session_state.get("global_explorer_last_click_id"):
            try:
                latitude = float(globe_value["latitude"])
                longitude = float(globe_value["longitude"])
                feature = identify_country(latitude, longitude)
                st.session_state.global_explorer_last_click_id = click_id
                point = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "name": (
                        f"Open ocean point ({latitude:.4f}, {longitude:.4f})"
                        if feature is None
                        else f"Selected point ({latitude:.4f}, {longitude:.4f})"
                    ),
                    "country": country_name(feature) if feature else None,
                    "click_id": click_id,
                }
                if feature is not None:
                    try:
                        with st.spinner("Looking up the nearest mapped locality…"):
                            place = _reverse_geocode(latitude, longitude)
                        point["place"] = place
                        address = place.get("address", {})
                        locality = _address_summary(address) if isinstance(address, dict) else ""
                        if locality:
                            point["name"] = locality
                    except RuntimeError as exc:
                        st.session_state.global_explorer_geocode_error = str(exc)
                st.session_state.global_explorer_globe_point = point
                st.session_state.global_explorer_method = "Globe selection"
                st.session_state.pop("global_explorer_result", None)
            except (KeyError, TypeError, ValueError) as exc:
                st.error(f"The globe returned invalid coordinates: {exc}")

    active_signature = None
    with left:
        method = st.selectbox(
            "Choose a location",
            _LOCATION_METHODS,
            index=_LOCATION_METHODS.index(method),
            key="global_explorer_method",
            format_func=lambda value: (
                "चयनित पृथ्वी बिंदु" if is_hi and value == "Globe selection" else value
            ),
        )
        coordinates: tuple[float, float] | None = None
        details: dict[str, Any] = {}

        if method == "Saved city":
            city = st.selectbox(
                "City",
                list(CITIES),
                index=list(CITIES).index("Delhi"),
                key="global_explorer_city",
            )
            coordinates = (CITIES[city]["latitude"], CITIES[city]["longitude"])
        elif method == "Current device location":
            _render_geolocation(location_picker)
            gps = st.session_state.get("global_explorer_gps")
            if isinstance(gps, dict):
                coordinates = (gps["latitude"], gps["longitude"])
                details = gps
                if gps.get("timestamp"):
                    detected = datetime.fromtimestamp(
                        gps["timestamp"] / 1000, timezone.utc
                    ).astimezone()
                    st.caption(
                        f"Detected {detected:%Y-%m-%d %H:%M %Z} · "
                        f"accuracy ±{gps['accuracy']:.0f} m"
                    )
                if gps.get("accuracy", 0) > 5000:
                    st.warning("GPS accuracy is coarse; refresh the fix or choose a place manually.")
            elif st.session_state.get("global_explorer_gps_error"):
                st.warning(
                    "Device location is unavailable. Other location methods remain available."
                )
        elif method == "Manual coordinates":
            lat_col, lon_col = st.columns(2)
            latitude = lat_col.number_input(
                "Latitude",
                min_value=-90.0,
                max_value=90.0,
                value=28.6139,
                format="%.5f",
                key="global_explorer_latitude",
            )
            longitude = lon_col.number_input(
                "Longitude",
                min_value=-180.0,
                max_value=180.0,
                value=77.2090,
                format="%.5f",
                key="global_explorer_longitude",
            )
            coordinates = (latitude, longitude)
        elif method == "Search by place":
            st.caption("Geocoding attribution: OpenStreetMap contributors.")
            with st.form("global_explorer_search_form"):
                query = st.text_input("Search for a city, region, or address")
                search = st.form_submit_button("Search places")
            if search:
                st.session_state.global_explorer_search_results = []
                st.session_state.global_explorer_search_error = None
                if query.strip():
                    try:
                        st.session_state.global_explorer_search_results = _search_places(
                            query.strip()
                        )
                    except RuntimeError as exc:
                        st.session_state.global_explorer_search_error = str(exc)
                st.rerun()
            if st.session_state.get("global_explorer_search_error"):
                st.error(st.session_state.global_explorer_search_error)
            search_results = st.session_state.get("global_explorer_search_results", [])
            if search_results:
                selected_index = st.selectbox(
                    "Search result",
                    range(len(search_results)),
                    format_func=lambda index: search_results[index]["name"],
                    key="global_explorer_search_choice",
                )
                place = search_results[selected_index]
                coordinates = (place["latitude"], place["longitude"])
                details = place.get("address", {})
        elif method in ("Farmer pilot", "Mandi pilot"):
            registry_key = "farmer_regions" if method == "Farmer pilot" else "trade_markets"
            candidates = pilots.get(registry_key, [])
            if candidates:
                selected_index = st.selectbox(
                    "Pilot location",
                    range(len(candidates)),
                    format_func=lambda index: (
                        f"{candidates[index]['name']}, {candidates[index]['state']}"
                    ),
                    key=f"global_explorer_{registry_key}",
                )
                candidate = candidates[selected_index]
                coordinates = (candidate["latitude"], candidate["longitude"])
                details = candidate
                st.caption(candidate["source"])
                st.info("Pilot entries are test candidates, not rankings or verified current listings.")
            else:
                st.warning("No pilot locations are currently configured.")
        elif method == "Globe selection":
            selected = st.session_state.get("global_explorer_globe_point")
            if isinstance(selected, dict):
                coordinates = (selected["latitude"], selected["longitude"])
                details = selected.get("place", {}).get("address", {})

        if coordinates:
            latitude, longitude = coordinates
            feature = identify_country(latitude, longitude)
            if feature is None:
                place_label = (
                    st.session_state.get("global_explorer_globe_point", {}).get("name")
                    if method == "Globe selection"
                    else None
                )
                location = place_label or f"Open ocean / no country boundary ({latitude:.4f}, {longitude:.4f})"
            else:
                name = country_name(feature)
                location = (
                    st.session_state.get("global_explorer_globe_point", {}).get("name")
                    if method == "Globe selection"
                    else None
                ) or _place_name(method, coordinates, pilots)
                properties = feature.get("properties", {})
                st.markdown(
                    f"**Country:** {name} · **Continent:** "
                    f"{properties.get('CONTINENT', 'not available')} · "
                    f"**Region:** {properties.get('SUBREGION', 'not available')}"
                )
            st.markdown(
                f"<div class='panel'><strong>Selected location</strong><br>{escape(location)}"
                f"<br><span class='muted'>{latitude:.5f}, {longitude:.5f}</span></div>",
                unsafe_allow_html=True,
            )
            if details:
                address = details.get("address", details) if isinstance(details, dict) else {}
                summary = _address_summary(address) if isinstance(address, dict) else ""
                if summary:
                    st.caption(f"Nearest mapped locality: {summary} · OpenStreetMap contributors")

            st.button(
                "Clear selection",
                key="global_explorer_clear",
                on_click=_clear_globe_selection,
            )

            if feature:
                potential_samples = sample_country_points(
                    feature,
                    anchor=(latitude, longitude),
                    max_points=5,
                )
                can_aggregate_country = len(potential_samples) >= 2
                aggregate_country = st.checkbox(
                    "Estimate country aggregate from multiple points",
                    value=can_aggregate_country,
                    key=f"global_explorer_country_aggregate_{feature.get('properties', {}).get('ADM0_A3', country_name(feature))}",
                    disabled=not can_aggregate_country,
                    help=(
                        "A country estimate uses several boundary-validated NASA POWER points. "
                        "It is not a single coordinate or an area-weighted national statistic."
                    ),
                )
                if not can_aggregate_country:
                    st.info(
                        "This generalized country boundary contains fewer than two suitable "
                        "sample points. Use the selected NASA point; no country aggregate will be claimed."
                    )
            else:
                aggregate_country = False

            icons = dict(
                zip(ENVIRONMENTAL_PARAMETERS, ("🌡️", "🌧️", "💧", "🌱", "💨", "☀️"))
            )
            labels = {
                key: f"{icons[key]} {item['scientific_name']} · {item['unit']}"
                for key, item in ENVIRONMENTAL_PARAMETERS.items()
            }
            variable = st.radio(
                "Environmental parameter",
                list(ENVIRONMENTAL_PARAMETERS),
                format_func=lambda key: labels[key],
                key="global_explorer_parameter",
            )
            metadata = ENVIRONMENTAL_PARAMETERS[variable]
            st.caption(f"{metadata['description']} · NASA POWER `{metadata['parameter']}`")
            if metadata.get("product_note"):
                st.caption(metadata["product_note"])
            purpose = st.selectbox(
                "Audience context (optional)",
                ["General User", "Farmer", "Agricultural Trader", "Student", "Researcher"],
                key="global_explorer_purpose",
            )
            start_limit = date.fromisoformat(metadata["start_date"]).year
            end_limit = date.today().year
            start_year, end_year = st.slider(
                "Historical period",
                min_value=start_limit,
                max_value=end_limit,
                value=(max(start_limit, end_limit - 10), end_limit),
                key=f"global_explorer_years_{variable}",
            )
            start_date = max(
                date(start_year, 1, 1),
                date.fromisoformat(metadata["start_date"]),
            )
            end_date = min(date(end_year, 12, 31), date.today())
            st.caption(
                "NASA observations are requested only after you confirm. "
                "Changing the parameter keeps the selected location and globe camera."
            )
            submitted = st.button(
                "Load historical NASA data",
                type="primary",
                width="stretch",
                key="global_explorer_load",
            )
            signature = (
                variable,
                round(latitude, 5),
                round(longitude, 5),
                start_date.isoformat(),
                end_date.isoformat(),
                bool(aggregate_country),
                country_name(feature) if feature else None,
            )
            active_signature = signature
            if submitted:
                st.session_state.global_explorer_result = None
                try:
                    with st.spinner(
                        "Sampling NASA POWER points and aggregating the selected region…"
                        if aggregate_country
                        else "Loading the selected NASA POWER point…"
                    ):
                        if aggregate_country and feature is not None:
                            country_result = aggregate_country_series(
                                feature,
                                (latitude, longitude),
                                variable,
                                start_date.isoformat(),
                                end_date.isoformat(),
                            )
                            frame = country_result["frame"]
                            result = {
                                "frame": frame,
                                "summary": country_result["summary"],
                                "trend": _trend_summary(country_result["summary"], variable),
                                "variable": variable,
                                "location": country_result["country"],
                                "latitude": latitude,
                                "longitude": longitude,
                                "country_aggregate": country_result,
                            }
                        else:
                            frame = cached_nasa_daily_fetch(
                                latitude,
                                longitude,
                                variable,
                                start_date.isoformat(),
                                end_date.isoformat(),
                            )
                            summary = summarize_daily_series(frame, variable)
                            result = {
                                "frame": frame,
                                "summary": summary,
                                "trend": _trend_summary(summary, variable),
                                "variable": variable,
                                "location": location,
                                "latitude": latitude,
                                "longitude": longitude,
                            }
                    st.session_state.global_explorer_result = result
                    st.session_state.global_explorer_signature = signature
                except (RuntimeError, ValueError) as exc:
                    st.error(str(exc))
        else:
            st.info("Select a point or another location method to begin.")

        if st.session_state.get("global_explorer_geocode_error"):
            st.caption(
                "Nearest-locality lookup was unavailable. Country and coordinates still come "
                "from local boundaries and the globe click."
            )
            st.session_state.pop("global_explorer_geocode_error", None)

    result = st.session_state.get("global_explorer_result")
    if active_signature and result:
        if st.session_state.get("global_explorer_signature") == active_signature:
            st.divider()
            _render_environmental_result(
                result,
                st.session_state.get("global_explorer_purpose", "General User"),
            )
        else:
            st.info("Your parameter, period, or location changed. Load data to refresh the chart.")
    _render_feedback()