import numpy as np
import pandas as pd
import pytest

from earth_pulse.country_data import aggregate_country_series
from earth_pulse.geography import identify_country


def _country_feature():
    feature = identify_country(21.1458, 79.0882)
    assert feature is not None
    return feature


def test_country_series_aggregates_multiple_valid_locations(monkeypatch):
    seen = []

    def fake_fetch(latitude, longitude, variable, start_date, end_date):
        seen.append((latitude, longitude))
        dates = pd.date_range(start_date, end_date, freq="D")
        value = float(len(seen))
        return pd.DataFrame({"value": np.full(len(dates), value)}, index=dates)

    monkeypatch.setattr("earth_pulse.country_data._cached_point_series", fake_fetch)
    result = aggregate_country_series(
        _country_feature(),
        anchor=(21.1458, 79.0882),
        variable="Hotness",
        start_date="2020-01-01",
        end_date="2020-01-31",
    )

    assert result["sample_count"] == 5
    assert result["unique_request_count"] == 5
    assert result["successful_request_count"] == 5
    assert result["contributing_locations"] == 5
    assert result["duplicate_request_coordinates"] == 0
    assert len(set(seen)) == 5
    assert result["summary"]["monthly"].iloc[0]["value"] == 3.0
    assert result["summary"]["monthly"].iloc[0]["valid_locations"] == 5
    assert "not guaranteed to represent distinct cells" in result["aggregation_method"]


def test_country_series_refuses_single_point_country_fallback(monkeypatch):
    def fake_fetch(latitude, longitude, variable, start_date, end_date):
        dates = pd.date_range(start_date, end_date, freq="D")
        values = np.full(len(dates), np.nan)
        if latitude == 21.1458:
            values[:] = 25.0
        return pd.DataFrame({"value": values}, index=dates)

    monkeypatch.setattr("earth_pulse.country_data._cached_point_series", fake_fetch)
    with pytest.raises(RuntimeError, match="requires at least two valid sample locations"):
        aggregate_country_series(
            _country_feature(),
            anchor=(21.1458, 79.0882),
            variable="Hotness",
            start_date="2020-01-01",
            end_date="2020-01-31",
        )


def test_country_series_deduplicates_identical_rounded_request_coordinates(monkeypatch):
    seen = []

    def fake_fetch(latitude, longitude, variable, start_date, end_date):
        seen.append((latitude, longitude))
        dates = pd.date_range(start_date, end_date, freq="D")
        return pd.DataFrame({"value": np.full(len(dates), 25.0)}, index=dates)

    monkeypatch.setattr("earth_pulse.country_data._cached_point_series", fake_fetch)
    monkeypatch.setattr(
        "earth_pulse.country_data.sample_country_points",
        lambda *args, **kwargs: [
            (21.14581, 79.08821),
            (21.14584, 79.08824),
            (22.0, 80.0),
        ],
    )

    result = aggregate_country_series(
        _country_feature(),
        anchor=(21.1458, 79.0882),
        variable="Hotness",
        start_date="2020-01-01",
        end_date="2020-01-31",
    )

    assert len(seen) == 2
    assert seen[0] == (21.1458, 79.0882)
    assert result["sample_count"] == 3
    assert result["unique_request_count"] == 2
    assert result["successful_request_count"] == 2
    assert result["duplicate_request_coordinates"] == 1