from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.mark.parametrize(
    "page",
    ["Investigate", "Compare", "Demo lab", "How it works"],
)
@pytest.mark.parametrize("language", ["English", "हिन्दी"])
def test_inner_pages_render_a_working_back_button(page, language):
    app = AppTest.from_file(APP_PATH)
    app.session_state["page"] = page
    app.session_state["language"] = language
    app.run(timeout=30)

    assert not app.exception
    label = "Back" if language == "English" else "वापस"
    back_buttons = [button for button in app.button if label in button.label]
    assert len(back_buttons) == 1
    back_button = back_buttons[0]
    back_button.click()
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["page"] == "Home"


@pytest.mark.parametrize(
    "mode",
    ["seasonal", "realtime", "historical", "location"],
)
def test_exploration_modes_are_selectable(mode):
    app = AppTest.from_file(APP_PATH)
    app.session_state["page"] = "Investigate"
    app.run(timeout=30)

    next(button for button in app.button if button.key == f"mode_{mode}").click()
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["exploration_mode"] == mode
    mode_titles = {
        "seasonal": "Seasonal Mode",
        "realtime": "Real-Time Mode",
        "historical": "Historical Mode",
        "location": "Location Mode",
    }
    assert any(
        "SELECTED" in element.value and mode_titles[mode] in element.value
        for element in app.markdown
    )
    if mode == "seasonal":
        assert any(widget.label == "Compare seasons" for widget in app.multiselect)
    elif mode == "realtime":
        assert not any(widget.label == "Historical period" for widget in app.radio)
        assert not app.multiselect
    elif mode == "historical":
        assert any(widget.label == "Historical period" for widget in app.radio)
        assert not app.multiselect
    elif mode == "location":
        assert any(widget.label == "Environmental parameter" for widget in app.radio)


def test_back_returns_to_the_previous_inner_page():
    app = AppTest.from_file(APP_PATH)
    app.session_state["page"] = "Investigate"
    app.run(timeout=30)

    next(radio for radio in app.radio if radio.label == "Navigate").set_value("Compare")
    app.run(timeout=30)
    assert app.session_state["page"] == "Compare"

    next(button for button in app.button if button.key == "back_nav").click()
    app.run(timeout=30)
    assert app.session_state["page"] == "Investigate"


def test_homepage_start_button_opens_investigate_page():
    app = AppTest.from_file(APP_PATH)
    app.run(timeout=30)

    app.session_state["global_explorer_globe_point"] = {
        "latitude": 21.1458,
        "longitude": 79.0882,
        "name": "Nagpur",
    }
    next(button for button in app.button if button.key == "home_start_investigation").click()
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["page"] == "Investigate"
    assert app.session_state["global_explorer_globe_point"]["name"] == "Nagpur"
    assert app.query_params["page"] == "Investigate"


def test_homepage_demo_button_routes_to_demo_without_clearing_session_data():
    app = AppTest.from_file(APP_PATH)
    app.run(timeout=30)

    app.session_state["global_explorer_globe_point"] = {
        "latitude": 21.1458,
        "longitude": 79.0882,
        "name": "Nagpur",
    }
    next(button for button in app.button if button.key == "home_explore_demo").click()
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["page"] == "Demo lab"
    assert app.session_state["global_explorer_globe_point"]["name"] == "Nagpur"
    assert app.query_params["page"] == "Demo lab"
    assert any(button.key == "nagpur_seasonal_demo" for button in app.button)


def test_page_query_parameter_restores_navigation_after_refresh():
    app = AppTest.from_file(APP_PATH)
    app.query_params["page"] = "Demo lab"
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["page"] == "Demo lab"


def test_location_parameter_switch_keeps_globe_selection():
    app = AppTest.from_file(APP_PATH)
    app.session_state["page"] = "Investigate"
    app.session_state["exploration_mode"] = "location"
    app.session_state["global_explorer_method"] = "Globe selection"
    app.session_state["global_explorer_globe_point"] = {
        "latitude": 21.1458,
        "longitude": 79.0882,
        "name": "Nagpur",
    }
    app.run(timeout=30)

    assert not app.exception
    next(widget for widget in app.radio if widget.label == "Environmental parameter").set_value(
        "Air moisture"
    )
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["global_explorer_parameter"] == "Air moisture"
    assert app.session_state["global_explorer_method"] == "Globe selection"
    assert app.session_state["global_explorer_globe_point"]["name"] == "Nagpur"


def test_demo_page_runs_the_labelled_nagpur_seasonal_example():
    app = AppTest.from_file(APP_PATH)
    app.session_state["page"] = "Demo lab"
    app.run(timeout=30)

    next(button for button in app.button if button.key == "nagpur_seasonal_demo").click()
    app.run(timeout=30)

    assert not app.exception
    result = app.session_state["demo_seasonal_result"]
    assert result["source"].startswith("DEMO DATA")
    assert set(result["seasonal"]["season"]) == {
        "Winter",
        "Pre-monsoon",
        "Monsoon",
        "Post-monsoon",
    }


def test_demo_lab_discloses_synthetic_data_and_links_to_a_real_investigation():
    app = AppTest.from_file(APP_PATH)
    app.session_state["page"] = "Demo lab"
    app.run(timeout=30)

    assert any(
        "Synthetic demonstration data — not actual environmental observations."
        in warning.value
        for warning in app.warning
    )
    next(
        button
        for button in app.button
        if button.key == "demo_run_real_investigation"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["page"] == "Investigate"
    assert app.query_params["page"] == "Investigate"


def test_synthetic_demo_result_is_not_headlined_as_a_real_city_trend():
    app = AppTest.from_file(APP_PATH)
    app.session_state["page"] = "Demo lab"
    app.run(timeout=30)

    next(
        button
        for button in app.button
        if button.label == "Run Delhi temperature demo"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert any(
        "Synthetic demonstration data — not actual environmental observations."
        in warning.value
        for warning in app.warning
    )
    assert any(
        "SYNTHETIC STATISTICS EXAMPLE" in element.value
        for element in app.markdown
    )
    assert not any(
        "SIGNIFICANT TREND DETECTED" in element.value
        for element in app.markdown
    )


def test_globe_location_name_is_escaped_before_html_rendering():
    app = AppTest.from_file(APP_PATH)
    app.session_state["page"] = "Investigate"
    app.session_state["exploration_mode"] = "location"
    app.session_state["global_explorer_method"] = "Globe selection"
    app.session_state["global_explorer_globe_point"] = {
        "latitude": 21.1458,
        "longitude": 79.0882,
        "name": "<img src=x onerror=alert(1)>",
    }

    app.run(timeout=30)

    assert not app.exception
    panel = next(
        element.value
        for element in app.markdown
        if "Selected location" in element.value
    )
    assert "&lt;img src=x onerror=alert(1)&gt;" in panel
    assert "<img src=x" not in panel
