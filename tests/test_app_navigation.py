from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.mark.parametrize(
    "page",
    ["Investigate", "Compare", "Demo lab", "How it works"],
)
@pytest.mark.parametrize("language", ["English", "हिन्दी"])
def test_inner_pages_render_a_working_back_to_home_button(page, language):
    app = AppTest.from_file(APP_PATH)
    app.session_state["page"] = page
    app.session_state["language"] = language
    app.run(timeout=30)

    assert not app.exception
    label = "Back to Home" if language == "English" else "होम पर वापस जाएं"
    back_button = next(button for button in app.button if label in button.label)
    back_button.click()
    app.run(timeout=30)

    assert not app.exception
    assert app.session_state["page"] == "Home"
