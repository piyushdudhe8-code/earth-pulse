from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any


BOUNDARIES_PATH = Path(__file__).with_name("ne_110m_admin_0_countries.geojson")


@lru_cache(maxsize=1)
def country_features() -> tuple[dict[str, Any], ...]:
    """Load the bundled Natural Earth Admin-0 country polygons."""
    try:
        with BOUNDARIES_PATH.open(encoding="utf-8") as source:
            collection = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load Natural Earth country boundaries: {exc}") from exc

    features = collection.get("features") if isinstance(collection, dict) else None
    if not isinstance(features, list) or not features:
        raise RuntimeError("The Natural Earth boundary file contains no country features.")
    return tuple(
        feature
        for feature in features
        if isinstance(feature, dict)
        and isinstance(feature.get("geometry"), dict)
        and isinstance(feature["geometry"].get("coordinates"), list)
    )


def _point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    if len(ring) < 4:
        return False

    inside = False
    points: list[tuple[float, float]] = []
    for coordinate in ring:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            return False
        # Unwrap each vertex around the test point so rings crossing ±180° work.
        delta = (float(coordinate[0]) - longitude + 180.0) % 360.0 - 180.0
        points.append((longitude + delta, float(coordinate[1])))

    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        if (y1 > latitude) != (y2 > latitude):
            crossing_x = x1 + (latitude - y1) * (x2 - x1) / (y2 - y1)
            if longitude < crossing_x:
                inside = not inside
    return inside


def point_in_feature(
    latitude: float,
    longitude: float,
    feature: dict[str, Any],
) -> bool:
    """Return whether a coordinate lies in a GeoJSON Polygon or MultiPolygon."""
    geometry = feature.get("geometry", {})
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        return False

    polygons = [coordinates] if geometry_type == "Polygon" else coordinates if geometry_type == "MultiPolygon" else []
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            continue
        outer = polygon[0]
        if not isinstance(outer, list) or not _point_in_ring(longitude, latitude, outer):
            continue
        if any(
            isinstance(hole, list) and _point_in_ring(longitude, latitude, hole)
            for hole in polygon[1:]
        ):
            continue
        return True
    return False


def identify_country(latitude: float, longitude: float) -> dict[str, Any] | None:
    """Find the country polygon containing a coordinate; ocean points return None."""
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("Coordinates must be finite numbers.")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Latitude/longitude are outside valid ranges.")

    for feature in country_features():
        bbox = feature.get("bbox")
        if isinstance(bbox, list) and len(bbox) >= 4:
            min_lon, min_lat, max_lon, max_lat = bbox[:4]
            if not (min_lat <= latitude <= max_lat):
                continue
            if min_lon <= max_lon and not (min_lon <= longitude <= max_lon):
                continue
        if point_in_feature(latitude, longitude, feature):
            return feature
    return None


def country_name(feature: dict[str, Any]) -> str:
    properties = feature.get("properties", {})
    return str(properties.get("ADMIN") or properties.get("NAME") or "Unknown country")


def _feature_bounds(feature: dict[str, Any]) -> tuple[float, float, float, float]:
    bbox = feature.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        return (
            float(bbox[0]),
            float(bbox[1]),
            float(bbox[2]),
            float(bbox[3]),
        )

    longitudes: list[float] = []
    latitudes: list[float] = []

    def collect(value: Any) -> None:
        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(
            isinstance(item, (int, float)) for item in value[:2]
        ):
            longitudes.append(float(value[0]))
            latitudes.append(float(value[1]))
        elif isinstance(value, (list, tuple)):
            for child in value:
                collect(child)

    collect(feature.get("geometry", {}).get("coordinates", []))
    if not longitudes:
        raise ValueError("Country geometry has no coordinate bounds.")
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def sample_country_points(
    feature: dict[str, Any],
    anchor: tuple[float, float] | None = None,
    max_points: int = 5,
) -> list[tuple[float, float]]:
    """Choose deterministic, spatially spread points that lie inside a country."""
    if max_points < 1:
        raise ValueError("max_points must be at least one.")
    min_lon, min_lat, max_lon, max_lat = _feature_bounds(feature)
    candidates: list[tuple[float, float]] = []
    grid_size = 30
    for row in range(grid_size):
        latitude = min_lat + (row + 0.5) * (max_lat - min_lat) / grid_size
        for column in range(grid_size):
            longitude = min_lon + (column + 0.5) * (max_lon - min_lon) / grid_size
            if point_in_feature(latitude, longitude, feature):
                candidates.append((latitude, longitude))

    selected: list[tuple[float, float]] = []
    if anchor and point_in_feature(anchor[0], anchor[1], feature):
        selected.append((float(anchor[0]), float(anchor[1])))
    if not candidates:
        return selected

    if not selected:
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        first = min(
            candidates,
            key=lambda point: (point[0] - center_lat) ** 2
            + ((point[1] - center_lon) * math.cos(math.radians(center_lat))) ** 2,
        )
        selected.append(first)

    while len(selected) < max_points and len(selected) < len(candidates):
        next_point = max(
            (point for point in candidates if point not in selected),
            key=lambda point: min(
                (point[0] - chosen[0]) ** 2
                + ((point[1] - chosen[1]) * math.cos(math.radians(point[0]))) ** 2
                for chosen in selected
            ),
        )
        selected.append(next_point)
    return selected