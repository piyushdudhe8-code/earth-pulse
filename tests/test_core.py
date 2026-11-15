import numpy as np
import pandas as pd
import pytest
import requests

from earth_pulse.analysis import benjamini_hochberg, analyze_series
from earth_pulse.data import VARIABLES, fetch_nasa_monthly, make_demo_series
from earth_pulse.interpretation import PARAMETER_INTERPRETATIONS, parameter_interpretation
from earth_pulse.report import make_report
from earth_pulse.seasons import season_months, seasonal_series


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


@pytest.mark.parametrize("variable", ["Temperature", "Rainfall"])
def test_trend_analysis_excludes_incomplete_calendar_years(variable):
    data = make_demo_series("Nagpur", variable, 2004, 2012)
    data.loc[pd.Timestamp("2004-06-01"), "value"] = np.nan

    result = analyze_series(data, variable)

    assert result["years_count"] == 8
    assert result["annual"].index[0] == 2005
    assert result["annual"].index[-1] == 2012


def test_synthetic_investigation_still_produces_a_source_labelled_report():
    frame = make_demo_series("Nagpur", "Temperature", 2004, 2025)
    result = analyze_series(frame, "Temperature", source=frame.attrs["source"])
    report = make_report(
        result,
        "Nagpur",
        21.1458,
        79.0882,
        "Synthetic demonstration result",
    )

    assert "Nagpur" in report
    assert "DEMO DATA" in report
    assert "IMPORTANT LIMITATIONS" in report
    assert "synthetic demonstration series" in report
    assert "actual conditions in the named city" in report


def test_parameter_interpretations_cover_supported_nasa_variables():
    assert set(PARAMETER_INTERPRETATIONS) == {
        "T2M",
        "PRECTOTCORR",
        "RH2M",
        "WS10M",
        "SFMC",
        "ALLSKY_SFC_SW_DWN",
    }
    for parameter, interpretation in PARAMETER_INTERPRETATIONS.items():
        assert parameter_interpretation(parameter) == interpretation
        assert all(
            interpretation[key]
            for key in ("measured", "rising", "falling", "matters", "cannot_tell", "limitations")
        )


def test_solar_parameter_is_supported_without_a_long_term_trend_claim():
    assert VARIABLES["Sunlight"]["parameter"] == "ALLSKY_SFC_SW_DWN"
    assert VARIABLES["Sunlight"]["unit"] == "kWh/m²/day"
    assert VARIABLES["Sunlight"]["trend_supported"] is False
    with pytest.raises(ValueError, match="A long-term statistical trend is not reported"):
        analyze_series(
            make_demo_series("Delhi", "Temperature", 2004, 2015),
            "Sunlight",
        )


def test_monsoon_season_is_limited_to_south_asia():
    assert season_months(28.6, 77.2)["Monsoon"] == (6, 7, 8, 9)
    assert "Monsoon" not in season_months(40.7, -74.0)


def test_india_uses_the_four_requested_environmental_seasons():
    assert season_months(21.1458, 79.0882) == {
        "Winter": (1, 2),
        "Pre-monsoon": (3, 4, 5),
        "Monsoon": (6, 7, 8, 9),
        "Post-monsoon": (10, 11, 12),
    }


def test_season_months_follow_the_hemisphere():
    assert season_months(-33.9, 151.2)["Summer"] == (12, 1, 2)
    assert season_months(-33.9, 151.2)["Winter"] == (6, 7, 8)


def test_season_definitions_can_be_overridden():
    seasons = season_months(
        40.7,
        -74.0,
        custom_definitions={"Warm season": (5, 6, 7, 8)},
    )

    assert seasons["Warm season"] == (5, 6, 7, 8)


def test_winter_season_uses_december_from_the_previous_calendar_year():
    frame = make_demo_series("Delhi", "Temperature", 2003, 2005)
    result = seasonal_series(frame, "Temperature", ["Winter"], 2004, 2004, 28.6, 77.2)

    assert len(result) == 1
    assert result.iloc[0]["year"] == 2004
    assert result.iloc[0]["season"] == "Winter"


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


def test_monthly_response_preserves_metadata_and_counts_missing_observations(monkeypatch):
    class Response:
        url = "https://power.larc.nasa.gov/example"

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "properties": {
                    "parameter": {
                        "T2M": {
                            "202401": 10.1,
                            "202402": -888.0,
                            "202413": 8.0,
                            "202501": 11.2,
                            "202601": 20.0,
                        }
                    }
                },
                "header": {
                    "title": "NASA monthly test",
                    "fill_value": -888.0,
                    "sources": ["MERRA2"],
                    "api": {"version": "test-version"},
                },
                "parameters": {
                    "T2M": {"units": "C", "longname": "Temperature at 2 Meters"}
                },
                "geometry": {"coordinates": [77.209, 28.614, 206.37]},
            }

    calls = {}

    def fake_get(url, **kwargs):
        calls["url"] = url
        calls["params"] = kwargs["params"]
        return Response()

    monkeypatch.setattr("earth_pulse.data.requests.get", fake_get)
    frame = fetch_nasa_monthly(28.6139, 77.2090, "Temperature", 2024, 2025)

    assert len(frame) == 24
    assert frame.loc[pd.Timestamp("2024-01-01"), "value"] == 10.1
    assert pd.isna(frame.loc[pd.Timestamp("2024-02-01"), "value"])
    assert pd.isna(frame.loc[pd.Timestamp("2024-12-01"), "value"])
    assert pd.isna(frame.loc[pd.Timestamp("2025-02-01"), "value"])
    assert frame.attrs["api_title"] == "NASA monthly test"
    assert frame.attrs["api_version"] == "test-version"
    assert frame.attrs["api_unit"] == "C"
    assert frame.attrs["latest_valid_date"] == "2025-01"
    assert frame.attrs["valid_observations"] == 2
    assert frame.attrs["missing_observations"] == 22
    assert frame.attrs["api_latitude"] == 28.614
    assert calls["url"].endswith("/temporal/monthly/point")
    assert calls["params"]["parameters"] == "T2M"
    assert calls["params"]["start"] == "2024"
    assert calls["params"]["end"] == "2025"


def test_unsupported_monthly_parameter_is_rejected_before_network_call(monkeypatch):
    def unexpected_request(*args, **kwargs):
        pytest.fail("An unsupported parameter must not be sent to NASA POWER.")

    monkeypatch.setattr("earth_pulse.data.requests.get", unexpected_request)
    with pytest.raises(ValueError, match="Unsupported variable"):
        fetch_nasa_monthly(28.6139, 77.2090, "Soil moisture", 2020, 2021)


def test_monthly_all_missing_values_raise_instead_of_falling_back(monkeypatch):
    class Response:
        url = "https://power.larc.nasa.gov/example"

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "properties": {"parameter": {"T2M": {"202401": -999.0}}},
                "header": {"fill_value": -999.0},
            }

    monkeypatch.setattr("earth_pulse.data.requests.get", lambda *args, **kwargs: Response())
    with pytest.raises(RuntimeError, match="no valid monthly observations"):
        fetch_nasa_monthly(28.6139, 77.2090, "Temperature", 2024, 2024)
