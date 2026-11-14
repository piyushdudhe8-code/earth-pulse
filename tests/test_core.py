import numpy as np
import pandas as pd
import pytest
import requests

from earth_pulse.analysis import benjamini_hochberg, analyze_series
from earth_pulse.data import fetch_nasa_monthly, make_demo_series


def test_demo_series_has_monthly_frequency():
    data = make_demo_series("Delhi", "Temperature", 2004, 2025)
    assert len(data) == 22 * 12
    assert data.index.is_monotonic_increasing


def test_trend_result_has_expected_fields():
    data = make_demo_series("Delhi", "Temperature", 2004, 2025)
    result = analyze_series(data, "Temperature")
    assert result["years_count"] == 22
    assert 0 <= result["p_value"] <= 1
    assert result["ci_low_per_decade"] <= result["ci_high_per_decade"]


def test_bh_adjustment_is_monotonic_in_rank_order():
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03])
    assert len(adjusted) == 3
    assert all(0 <= value <= 1 for value in adjusted)
    assert adjusted[0] <= adjusted[2] <= adjusted[1]


def test_rainfall_trend_unit_is_annual_total():
    data = make_demo_series("Mumbai", "Rainfall", 2004, 2025)
    result = analyze_series(data, "Rainfall")
    assert result["unit"] == "mm/month (estimated)"
    assert result["trend_unit"] == "mm/year"


def test_nasa_timeout_has_a_connection_guidance_message(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("request timed out")

    monkeypatch.setattr("earth_pulse.data.requests.get", timeout)
    with pytest.raises(RuntimeError, match="Check your internet connection"):
        fetch_nasa_monthly(28.6139, 77.2090, "Temperature", 2022, 2023)


def test_nasa_response_missing_parameter_is_reported(monkeypatch):
    class Response:
        url = "https://power.larc.nasa.gov/"

        def raise_for_status(self):
            pass

        def json(self):
            return {"properties": {"parameter": {}}}

    monkeypatch.setattr("earth_pulse.data.requests.get", lambda *args, **kwargs: Response())
    with pytest.raises(RuntimeError, match="did not contain monthly values for T2M"):
        fetch_nasa_monthly(28.6139, 77.2090, "Temperature", 2022, 2023)
