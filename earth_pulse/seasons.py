from __future__ import annotations

import pandas as pd

from .data import VARIABLES, prepare_monthly_series


_NORTHERN_SEASONS = {
    "Spring": (3, 4, 5),
    "Summer": (6, 7, 8),
    "Autumn": (9, 10, 11),
    "Winter": (12, 1, 2),
}
_SOUTHERN_SEASONS = {
    "Spring": (9, 10, 11),
    "Summer": (12, 1, 2),
    "Autumn": (3, 4, 5),
    "Winter": (6, 7, 8),
}
_INDIA_SEASONS = {
    "Winter": (1, 2),
    "Pre-monsoon": (3, 4, 5),
    "Monsoon": (6, 7, 8, 9),
    "Post-monsoon": (10, 11, 12),
}


def season_months(
    latitude: float,
    longitude: float,
    custom_definitions: dict[str, tuple[int, ...]] | None = None,
) -> dict[str, tuple[int, ...]]:
    """Return regional or hemisphere seasons, optionally overriding month groups."""
    in_india = 6 <= latitude <= 38 and 68 <= longitude <= 98
    if in_india:
        seasons = dict(_INDIA_SEASONS)
    else:
        seasons = dict(_NORTHERN_SEASONS if latitude >= 0 else _SOUTHERN_SEASONS)
        if 5 <= latitude <= 35 and 60 <= longitude <= 100:
            seasons["Monsoon"] = (6, 7, 8, 9)

    if custom_definitions:
        for name, months in custom_definitions.items():
            if not name or not months or any(month not in range(1, 13) for month in months):
                raise ValueError(f"Invalid month definition for season {name!r}.")
            seasons[name] = tuple(dict.fromkeys(months))
    return seasons


def seasonal_series(
    frame: pd.DataFrame,
    variable: str,
    selected_seasons: list[str],
    start_year: int,
    end_year: int,
    latitude: float,
    longitude: float,
    custom_definitions: dict[str, tuple[int, ...]] | None = None,
) -> pd.DataFrame:
    """Calculate full-season yearly values; incomplete seasons are excluded."""
    calendar = season_months(latitude, longitude, custom_definitions)
    unknown = set(selected_seasons) - set(calendar)
    if unknown:
        raise ValueError(f"Unsupported season for this location: {', '.join(sorted(unknown))}")

    prepared = prepare_monthly_series(frame, variable).dropna(subset=["display_value"]).copy()
    rows: list[dict[str, object]] = []
    is_rain = VARIABLES[variable]["kind"] == "rain"

    for season in selected_seasons:
        months = calendar[season]
        wraps_year = tuple(sorted(months)) != months
        selected = prepared[prepared["month"].isin(months)].copy()
        selected["season_year"] = selected["year"] + (
            (selected["month"] >= months[0]).astype(int) if wraps_year else 0
        )
        selected = selected[selected["season_year"].between(start_year, end_year)]

        for year, values in selected.groupby("season_year"):
            values = values.sort_values("month")
            if len(values) != len(months) or set(values["month"]) != set(months):
                continue
            measure = (
                float(values["display_value"].sum())
                if is_rain
                else float((values["display_value"] * values["days"]).sum() / values["days"].sum())
            )
            rows.append({"year": int(year), "season": season, "value": measure})

    return pd.DataFrame(rows, columns=["year", "season", "value"]).sort_values(
        ["year", "season"], ignore_index=True
    )
