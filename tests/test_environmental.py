import numpy as np
import pandas as pd
import pytest
import requests

from earth_pulse.environmental import (
    ENVIRONMENTAL_PARAMETERS,
    fetch_nasa_daily,
    summarize_daily_series,
)
from earth_pulse.explorer import _reverse_geocode, _search_places


def test_location_explorer_exposes_six_explicit_daily_parameters():
    assert set(ENVIRONMENTAL_PARAMETERS) == {
        "Hotness",
        "Rainfall",
        "Air moisture",
        "Soil moisture",
        "Air speed",
        "Sunlight",
    }
    assert ENVIRONMENTAL_PARAMETERS["Rainfall"]["parameter"] == "PRECTOTCORR"
    assert ENVIRONMENTAL_PARAMETERS["Soil moisture"]["unit"] == "m³/m³"
    assert ENVIRONMENTAL_PARAMETERS["Sunlight"]["parameter"] == "ALLSKY_SFC_SW_DWN"
    assert ENVIRONMENTAL_PARAMETERS["Sunlight"]["unit"] == "kWh/m²/day"


def test_daily_fetch_preserves_missing_values_and_api_reported_coordinates(monkeypatch):
    class Response:
        url = "https://power.larc.nasa.gov/example"
        status_code = 200
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "properties": {
                    "parameter": {"T2M": {"20200101": 1.5, "20200103": -999.0}}
                },
                "header": {
                    "fill_value": -999.0,
                    "sources": ["MERRA2"],
                    "api": {"version": "test"},
                    "time_standard": "UTC",
                },
                "parameters": {"T2M": {"units": "C", "longname": "Temperature"}},
                "geometry": {"coordinates": [77.21, 28.61, 220.0]},
            }

    calls = {}

    def fake_get(url, **kwargs):
        calls["url"] = url
        calls["params"] = kwargs["params"]
        return Response()

    monkeypatch.setattr("earth_pulse.environmental.requests.get", fake_get)
    frame = fetch_nasa_daily(28.6139, 77.2090, "Hotness", "2020-01-01", "2020-01-03")

    assert len(frame) == 3
    assert frame["value"].iloc[0] == 1.5
    assert frame["value"].iloc[1:].isna().all()
    assert frame.attrs["latest_valid_date"] == "2020-01-01"
    assert frame.attrs["api_latitude"] == 28.61
    assert frame.attrs["api_longitude"] == 77.21
    assert "grid_latitude" not in frame.attrs
    assert calls["params"]["time-standard"] == "UTC"
    assert calls["params"]["community"] == "AG"
    assert calls["params"]["parameters"] == "T2M"


def test_daily_fetch_recognizes_string_fill_value_metadata(monkeypatch):
    class Response:
        url = "https://power.larc.nasa.gov/example"
        status_code = 200
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "properties": {"parameter": {"T2M": {"20200101": -888.0}}},
                "header": {"fill_value": "-888", "sources": ["MERRA2"]},
            }

    monkeypatch.setattr(
        "earth_pulse.environmental.requests.get",
        lambda *args, **kwargs: Response(),
    )
    frame = fetch_nasa_daily(
        28.6139,
        77.2090,
        "Hotness",
        "2020-01-01",
        "2020-01-01",
    )

    assert frame["value"].isna().all()
    assert frame.attrs["latest_valid_date"] is None


def test_daily_timeout_has_connection_guidance(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("request timed out")

    monkeypatch.setattr("earth_pulse.environmental.requests.get", timeout)
    with pytest.raises(RuntimeError, match="Check your internet connection"):
        fetch_nasa_daily(28.6139, 77.2090, "Hotness", "2020-01-01", "2020-01-02")


def test_soil_moisture_rejects_dates_before_its_product_record(monkeypatch):
    def fail_if_requested(*args, **kwargs):
        pytest.fail("The NASA API must not be called for dates before the product record.")

    monkeypatch.setattr("earth_pulse.environmental.requests.get", fail_if_requested)
    with pytest.raises(ValueError, match="2015-03-31"):
        fetch_nasa_daily(
            28.6139,
            77.2090,
            "Soil moisture",
            "2015-01-01",
            "2015-12-31",
        )


def test_missing_soil_data_is_not_claimed_as_smap_or_filled(monkeypatch):
    class Response:
        url = "https://power.larc.nasa.gov/example"
        status_code = 200
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "properties": {"parameter": {"SFMC": {"20200601": -999.0}}},
                "header": {"fill_value": -999.0, "sources": []},
                "parameters": {"SFMC": {"units": "m3 m-3"}},
            }

    monkeypatch.setattr("earth_pulse.environmental.requests.get", lambda *args, **kwargs: Response())
    frame = fetch_nasa_daily(
        28.6139,
        77.2090,
        "Soil moisture",
        "2020-06-01",
        "2020-06-01",
    )

    assert frame["value"].isna().all()
    assert frame.attrs["latest_valid_date"] is None
    assert "not asserted" in frame.attrs["spatial_resolution"]


def test_daily_summary_keeps_rainfall_totals_and_omits_incomplete_months():
    dates = pd.date_range("2020-01-01", "2020-02-29", freq="D")
    values = np.ones(len(dates))
    values[25:37] = np.nan
    frame = pd.DataFrame({"value": values}, index=dates)

    summary = summarize_daily_series(frame, "Rainfall")

    assert summary["monthly"].loc[pd.Timestamp("2020-01-01"), "value"] == 31
    assert pd.isna(summary["monthly"].loc[pd.Timestamp("2020-02-01"), "value"])
    assert summary["valid_days"] == 48


def test_daily_trend_series_excludes_partial_calendar_years():
    dates = pd.date_range("2010-01-01", "2018-11-30", freq="D")
    frame = pd.DataFrame({"value": np.ones(len(dates))}, index=dates)

    summary = summarize_daily_series(frame, "Hotness")

    assert len(summary["annual"]) == 8
    assert summary["annual"].index[-1] == 2017


def test_place_search_and_reverse_geocoding_return_real_address_data(monkeypatch):
    class Response:
        status_code = 200
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            if self.url.endswith("/search"):
                return [
                    {
                        "display_name": "Nashik, Maharashtra, India",
                        "lat": "19.9975",
                        "lon": "73.7898",
                        "address": {
                            "city": "Nashik",
                            "state": "Maharashtra",
                            "country": "India",
                        },
                    }
                ]
            return {
                "display_name": "Nashik, Maharashtra, India",
                "address": {
                    "city": "Nashik",
                    "state": "Maharashtra",
                    "country": "India",
                },
            }

    def fake_get(url, **kwargs):
        response = Response()
        response.url = url
        return response

    monkeypatch.setattr("earth_pulse.explorer.requests.get", fake_get)

    places = _search_places("earth-pulse-test-place")
    reverse = _reverse_geocode(19.9975, 73.7898)

    assert places[0]["latitude"] == 19.9975
    assert places[0]["address"]["state"] == "Maharashtra"
    assert reverse["display_name"] == "Nashik, Maharashtra, India"
