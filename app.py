from __future__ import annotations

import calendar
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from earth_pulse.analysis import analyze_series, benjamini_hochberg, build_verdict
from earth_pulse.data import (
    CITIES,
    VARIABLES,
    fetch_nasa_monthly,
    make_demo_series,
    prepare_monthly_series,
)
from earth_pulse.global_explorer import render_global_explorer
from earth_pulse.globe import render_earth_globe
from earth_pulse.interpretation import parameter_interpretation
from earth_pulse.report import make_report
from earth_pulse.seasons import season_months, seasonal_series


# -------------------------------------------------------------------
# PAGE CONFIG + DESIGN
# -------------------------------------------------------------------
st.set_page_config(
    page_title="EARTH PULSE | Earth Systems Trend Detective",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

    :root {
        --ep-ink: #eaf1f0;
        --ep-muted: #9eb1ad;
        --ep-bg: #081715;
        --ep-panel: #102522;
        --ep-line: #23423d;
        --ep-mint: #9be7c4;
        --ep-yellow: #f2c879;
    }

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp {
        background: radial-gradient(circle at 80% -10%, #1b4038 0%, #0a1b18 38%, #07110f 100%);
        color: var(--ep-ink);
    }
    .block-container { max-width: 1200px; padding-top: 1.5rem; padding-bottom: 3rem; }
    .st-key-back_nav {
        position: sticky !important;
        top: 5rem !important;
        z-index: 10001 !important;
        width: max-content !important;
    }
    .st-key-back_nav .stButton > button {
        min-height: 2.45rem;
        padding: .35rem .9rem;
        border-radius: 999px;
        background: rgba(16, 37, 34, .96);
        color: #eaf1f0;
        border-color: #44675c;
        box-shadow: 0 4px 18px rgba(0, 0, 0, .28);
    }
    [data-testid="stSidebar"] { background: #0b1c19; border-right: 1px solid #1b3731; }
    [data-testid="stSidebar"] * { color: #dceae5; }
    h1, h2, h3 {
        font-family: 'Space Grotesk', sans-serif !important;
        letter-spacing: -.03em;
        color: #f0f7f3;
    }
    .eyebrow {
        color: #9be7c4;
        letter-spacing: .16em;
        text-transform: uppercase;
        font-size: .72rem;
        font-weight: 700;
    }
    .hero {
        border: 1px solid #31544a;
        border-radius: 24px;
        padding: 2.2rem;
        background: linear-gradient(125deg, rgba(22,58,49,.95), rgba(12,31,28,.9) 58%, rgba(12,26,23,.92));
        box-shadow: 0 20px 60px rgba(0,0,0,.18);
    }
    .hero h1 {
        font-size: clamp(2.6rem, 6vw, 4.8rem);
        line-height: 1;
        margin: .55rem 0 .85rem;
    }
    .hero p { color: #bfd0c9; font-size: 1.08rem; max-width: 740px; }
    .panel {
        background: rgba(16,37,34,.82);
        border: 1px solid #24443c;
        padding: 1rem 1.15rem;
        border-radius: 18px;
        height: 100%;
    }
    .metric {
        background: rgba(16,37,34,.78);
        border: 1px solid #24443c;
        border-radius: 16px;
        padding: 1rem 1.1rem;
        min-height: 105px;
    }
    .metric-label {
        color: #9eb1ad;
        font-size: .78rem;
        text-transform: uppercase;
        letter-spacing: .08em;
    }
    .metric-value {
        color: #f1f8f4;
        font-family: 'Space Grotesk';
        font-size: 1.7rem;
        font-weight: 700;
        padding-top: .25rem;
    }
    .muted { color: #a8bcb5; }
    .tag {
        display: inline-block;
        border: 1px solid #44675c;
        border-radius: 999px;
        padding: .25rem .65rem;
        color: #bcebd2;
        font-size: .75rem;
        margin: .2rem .25rem .2rem 0;
    }
    [data-testid="stMetricValue"] { color: #eff8f3; }
    .stButton > button, .stDownloadButton > button {
        border-radius: 12px;
        border: 1px solid #5b9b82;
        background: #a5e8c5;
        color: #092019;
        font-weight: 700;
        min-height: 2.8rem;
        cursor: pointer;
        transition: background-color .15s ease, border-color .15s ease, transform .15s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        border-color: #d5f7e4;
        background: #c0f2d7;
        color: #081b14;
    }
    .stButton > button:active, .stDownloadButton > button:active {
        transform: translateY(1px);
    }
    .stTextInput input, .stNumberInput input,
    .stSelectbox div[data-baseweb="select"] > div {
        background: #102622;
        color: #eef8f2;
    }
    .stTabs [data-baseweb="tab"] { color: #a9bbb4; }
    hr { border-color: #26443d; }
    [data-testid="stAlert"] { border-radius: 14px; }
    footer { visibility: hidden; }

    @media (max-width: 700px) {
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        .hero { padding: 1.35rem; border-radius: 18px; }
        .hero h1 { font-size: 2.8rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------------------------------------------------------
# LANGUAGE + NAVIGATION
# -------------------------------------------------------------------
PAGE_HOME = "Home"
PAGE_INVESTIGATE = "Investigate"
PAGE_COMPARE = "Compare"
PAGE_DEMO = "Demo lab"
PAGE_ABOUT = "How it works"
PAGES = [PAGE_HOME, PAGE_INVESTIGATE, PAGE_COMPARE, PAGE_DEMO, PAGE_ABOUT]

LANG_ENGLISH = "English"
LANG_HINDI = "हिन्दी"
PAGE_TEXT_KEYS = {
    PAGE_HOME: "home",
    PAGE_INVESTIGATE: "investigate",
    PAGE_COMPARE: "compare",
    PAGE_DEMO: "demo",
    PAGE_ABOUT: "about",
}

TEXT = {
    LANG_ENGLISH: {
        "home": "Home",
        "investigate": "Investigate",
        "compare": "Compare",
        "demo": "Demo lab",
        "about": "How it works",
        "start": "Start an investigation",
        "watch": "Explore a demo",
        "what": "What do you want to investigate?",
        "where": "Where should we look?",
        "period": "Analysis period",
        "analyze": "Analyze trends",
        "source": "Data source",
        "technical": "Technical details",
        "report": "Investigation report",
        "download": "Download report (.txt)",
        "limitations": "What this result does not tell us",
        "city": "City",
        "variable": "Earth system variable",
        "start_year": "Analysis start year",
        "globe": "EARTH SYSTEMS · PLANET VIEW",
        "globe_help": "Explore the planet, then choose a signal and location below.",
        "custom": "Enter latitude / longitude manually",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "back": "← Back",
        "monthly_value": "Monthly value",
        "annual_average": "Annual average",
        "annual_rainfall": "Annual rainfall total",
        "trend_line": "Sen's trend line",
        "month": "Month",
        "year": "Year",
        "home_desc": "Explore open Earth data and discover whether a pattern is really changing — in simple words, without writing code.",
        "no_login": "No login required",
        "bilingual": "Hindi + English",
        "open_data": "Open data",
        "card1_title": "Choose a signal",
        "card1_text": "Temperature, relative humidity, rainfall or wind speed. Pick the change you want to understand.",
        "card2_title": "Test the pattern",
        "card2_text": "See the data, the long-term direction and whether the pattern is statistically convincing.",
        "card3_title": "Keep the evidence",
        "card3_text": "Download a report showing the data source, result and limitations.",
        "home_footer": "EARTH PULSE is a student-built open-data prototype, not an official NASA product. Data source: NASA POWER.",
    },
    LANG_HINDI: {
        "home": "होम",
        "investigate": "जांच करें",
        "compare": "तुलना",
        "demo": "डेमो लैब",
        "about": "कैसे काम करता है",
        "start": "नई जांच शुरू करें",
        "watch": "डेमो देखें",
        "what": "आप क्या जांचना चाहते हैं?",
        "where": "किस जगह का डेटा देखें?",
        "period": "जांच की समय अवधि",
        "analyze": "ट्रेंड जांचें",
        "source": "डेटा स्रोत",
        "technical": "तकनीकी जानकारी",
        "report": "जांच रिपोर्ट",
        "download": "रिपोर्ट डाउनलोड करें (.txt)",
        "limitations": "यह परिणाम क्या नहीं बताता",
        "city": "शहर",
        "variable": "पृथ्वी प्रणाली का मान",
        "start_year": "जांच का शुरुआती साल",
        "globe": "पृथ्वी प्रणाली · ग्रह का दृश्य",
        "globe_help": "पृथ्वी को देखें, फिर नीचे कोई मान और जगह चुनें।",
        "custom": "अक्षांश / देशांतर खुद दर्ज करें",
        "latitude": "अक्षांश",
        "longitude": "देशांतर",
        "back": "← वापस",
        "monthly_value": "मासिक मान",
        "annual_average": "सालाना औसत",
        "annual_rainfall": "सालाना वर्षा योग",
        "trend_line": "Sen की ट्रेंड रेखा",
        "month": "महीना",
        "year": "साल",
        "home_desc": "पृथ्वी के खुले डेटा को समझें और जानें कि समय के साथ क्या बदल रहा है — बिना कोडिंग किए, आसान भाषा में।",
        "no_login": "लॉगिन की जरूरत नहीं",
        "bilingual": "हिंदी + English",
        "open_data": "खुला डेटा",
        "card1_title": "एक संकेत चुनें",
        "card1_text": "तापमान, हवा में नमी, बारिश या हवा की गति में से चुनें।",
        "card2_title": "बदलाव का पैटर्न समझें",
        "card2_text": "डेटा देखें और जानें कि लंबे समय में क्या बदलाव आया है।",
        "card3_title": "सबूत सुरक्षित रखें",
        "card3_text": "डेटा स्रोत, नतीजे और सीमाओं वाली रिपोर्ट डाउनलोड करें।",
        "home_footer": "EARTH PULSE विद्यार्थियों द्वारा बनाया गया खुला-डेटा प्रोटोटाइप है। यह NASA का आधिकारिक उत्पाद नहीं है। डेटा स्रोत: NASA POWER।",
    },
}

if "page" not in st.session_state:
    requested_page = st.query_params.get("page", PAGE_HOME)
    st.session_state.page = requested_page if requested_page in PAGES else PAGE_HOME
if "language" not in st.session_state:
    st.session_state.language = LANG_ENGLISH
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "previous_page" not in st.session_state:
    st.session_state.previous_page = None
if "page_history" not in st.session_state:
    st.session_state.page_history = []

with st.sidebar:
    st.markdown("<div class='eyebrow'>🌍 EARTH PULSE</div>", unsafe_allow_html=True)
    st.caption("Earth Systems Trend Detective")
    st.session_state.language = st.radio(
        "Language / भाषा",
        [LANG_ENGLISH, LANG_HINDI],
        horizontal=True,
        index=0 if st.session_state.language == LANG_ENGLISH else 1,
    )
    t = TEXT[st.session_state.language]
    st.divider()

    page_options = PAGES
    page_labels = [t[PAGE_TEXT_KEYS[page]] for page in page_options]
    current_index = page_options.index(st.session_state.page) if st.session_state.page in page_options else 0
    if st.session_state.get("sidebar_navigation") not in page_labels:
        st.session_state.sidebar_navigation = page_labels[current_index]
    selected_label = st.radio(
        "Navigate",
        page_labels,
        key="sidebar_navigation",
        label_visibility="collapsed",
    )
    selected_page = page_options[page_labels.index(selected_label)]
    if selected_page != st.session_state.page:
        st.session_state.page_history.append(st.session_state.page)
        st.session_state.previous_page = st.session_state.page
        st.session_state.page = selected_page
        st.query_params["page"] = selected_page

    st.divider()
    st.markdown(
        "<span class='tag'>NASA POWER</span><span class='tag'>No login</span>",
        unsafe_allow_html=True,
    )
    st.caption(
        "विद्यार्थियों द्वारा बनाया गया प्रोटोटाइप। NASA का आधिकारिक उत्पाद नहीं।"
        if st.session_state.language == LANG_HINDI
        else "A student-built open-data prototype. Not an official NASA product."
    )
    st.markdown(
        "[NASA POWER documentation](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/)"
    )

def navigate_to_page(page: str) -> None:
    if page not in PAGES:
        raise ValueError(f"Unknown page: {page}")
    if page != st.session_state.page:
        st.session_state.page_history.append(st.session_state.page)
        st.session_state.previous_page = st.session_state.page
        st.session_state.page = page
        st.session_state.sidebar_navigation = TEXT[st.session_state.language][PAGE_TEXT_KEYS[page]]
    st.query_params["page"] = page


# -------------------------------------------------------------------
# DATA HELPERS
# -------------------------------------------------------------------
@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_nasa_fetch(latitude: float, longitude: float, variable: str, start_year: int, end_year: int):
    return fetch_nasa_monthly(latitude, longitude, variable, start_year, end_year)


location_picker = components.declare_component(
    "earth_pulse_location_picker",
    path=str(Path(__file__).parent / "earth_pulse" / "location_component"),
)


def get_location(city: str, custom: bool, lat: float, lon: float) -> tuple[float, float]:
    if custom:
        return float(lat), float(lon)
    return CITIES[city]["latitude"], CITIES[city]["longitude"]


def load_and_analyze(
    city: str,
    latitude: float,
    longitude: float,
    variable: str,
    start_year: int,
    end_year: int,
    force_demo: bool = False,
) -> dict:
    if force_demo:
        frame = make_demo_series(city, variable, start_year, end_year)
        source = "DEMO DATA — synthetic, generated for demonstration only"
    else:
        try:
            frame = cached_nasa_fetch(latitude, longitude, variable, start_year, end_year)
            source = frame.attrs.get(
                "source",
                "NASA POWER Monthly and Annual API (periodic monthly data; not instantaneous)",
            )
        except Exception as exc:
            raise RuntimeError(
                f"NASA POWER request failed ({type(exc).__name__}: {exc}). "
                "Open Demo lab to view clearly labelled synthetic data."
            ) from exc

    return analyze_series(frame, variable, source=source)


def render_parameter_interpretation(parameter: str) -> None:
    guidance = parameter_interpretation(parameter)
    if not guidance:
        return
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


def render_monthly_data_quality(
    frame: pd.DataFrame,
    variable: str,
    location: str,
    coordinates: tuple[float, float] | None = None,
    selected_period: str | None = None,
) -> None:
    expected = len(frame.index)
    valid = int(frame["value"].notna().sum())
    missing = expected - valid
    latest = frame.index[frame["value"].notna()].max().strftime("%Y-%m") if valid else "none"
    requested_start = frame.attrs.get("requested_start", "not provided")
    requested_end = frame.attrs.get("requested_end", "not provided")
    if selected_period:
        if " to " in selected_period:
            requested_start, requested_end = selected_period.split(" to ", maxsplit=1)
        else:
            requested_start = requested_end = selected_period
    valid_index = frame.index[frame["value"].notna()]
    observation_period = (
        f"{valid_index.min():%Y-%m} to {valid_index.max():%Y-%m}"
        if valid
        else "no valid observations"
    )
    coordinate_text = (
        f"{coordinates[0]:.4f}, {coordinates[1]:.4f}"
        if coordinates is not None
        else "coordinates not provided"
    )
    retrieved_at = frame.attrs.get("retrieved_at", "not provided")
    if retrieved_at != "not provided":
        retrieved_at = datetime.fromisoformat(retrieved_at).astimezone().strftime(
            "%Y-%m-%d %H:%M %Z"
        )
    st.markdown("**Data source and observation quality**")
    st.write(f"Selected location: {location} · {coordinate_text}")
    st.write(
        f"Parameter: {variable} ({frame.attrs.get('parameter', VARIABLES[variable]['parameter'])}) · "
        f"Display unit: {VARIABLES[variable]['unit']} · "
        f"NASA API unit: {frame.attrs.get('api_unit', 'not provided')}"
    )
    st.write(
        f"Source: {frame.attrs.get('source', 'NASA POWER Monthly and Annual API')} · "
        f"Dataset: {frame.attrs.get('dataset', 'not provided')} · "
        f"API sources: {frame.attrs.get('data_sources', 'not provided')} · "
        f"API version: {frame.attrs.get('api_version', 'unknown')}"
    )
    st.write(
        f"Requested period: {requested_start} to {requested_end} · "
        f"Observation period: {observation_period} · "
        f"Latest valid observation: {latest}"
    )
    st.write(
        f"Total valid observations received: {valid} · Missing observations: {missing} · "
        f"Coverage: {valid / expected * 100 if expected else 0:.1f}% ({valid}/{expected} months)"
    )
    st.write(
        f"Spatial resolution: {frame.attrs.get('spatial_resolution', 'not provided')} · "
        f"Retrieved: {retrieved_at}"
    )


# -------------------------------------------------------------------
# RESULTS
# -------------------------------------------------------------------
def render_result(
    result: dict,
    city: str,
    latitude: float,
    longitude: float,
    language: str = LANG_ENGLISH,
    adjusted_p: float | None = None,
):
    is_demo = "DEMO DATA" in result["source"]
    verdict_result = result if adjusted_p is None else {
        **result,
        "significant": adjusted_p < 0.05,
    }
    verdict = build_verdict(verdict_result, language)
    if is_demo:
        if language == LANG_HINDI:
            verdict = (
                "केवल इस synthetic demonstration series में: "
                f"{verdict} यह किसी शहर के वास्तविक पर्यावरणीय अवलोकन का निष्कर्ष नहीं है।"
            )
        else:
            verdict = (
                "In this synthetic demonstration series only: "
                f"{verdict} This is not a finding about the named city's actual environment."
            )

    st.markdown(
        "<div class='eyebrow'>जांच का परिणाम</div>"
        if language == LANG_HINDI
        else "<div class='eyebrow'>INVESTIGATION RESULT</div>",
        unsafe_allow_html=True,
    )
    st.subheader(f"{city} · {result['variable']}")

    if is_demo:
        st.warning(
            "Synthetic demonstration data — not actual environmental observations."
            if language != LANG_HINDI
            else "Synthetic demonstration data — not actual environmental observations. "
            "ये NASA के वास्तविक पर्यावरणीय अवलोकन नहीं हैं।"
        )
    else:
        st.success(
            "NASA POWER का आवधिक मासिक डेटा मिला। यह तात्कालिक सेंसर रीडिंग नहीं, ग्रिड-आधारित डेटा है।"
            if language == LANG_HINDI
            else "NASA POWER periodic monthly data. This is not an instantaneous sensor reading; it is gridded data."
        )

    st.markdown("**Data source and observation quality**")
    st.write(f"Selected location: {city} · {latitude:.4f}, {longitude:.4f}")
    if is_demo:
        st.write(
            f"Parameter: {result['variable']} ({result['parameter']}) · "
            f"Synthetic unit: {result['display_unit']} · "
            f"Source / dataset: {result['source']} · "
            f"Generated sample values: {result['valid_months']} · "
            "Spatial resolution: not applicable (synthetic data)."
        )
    else:
        st.write(
            f"Parameter: {result['variable']} ({result['parameter']} · "
            f"{result['api_long_name']}) · "
            f"Display unit: {result['display_unit']} · NASA API unit: {result['api_unit']}"
        )
        retrieved_at = result.get("retrieved_at", "not provided")
        if retrieved_at != "not provided":
            retrieved_at = datetime.fromisoformat(retrieved_at).astimezone().strftime(
                "%Y-%m-%d %H:%M %Z"
            )
        st.write(
            f"Source: {result['source']} · Dataset: {result['dataset']} · "
            f"API: {result['api_title']} · API sources: {result['data_sources']} · "
            f"API version: {result['api_version']}"
        )
        st.write(
            f"Requested period: {result['requested_start']} to {result['requested_end']} · "
            f"Observation period: {result['start']} to {result['end']} · "
            f"Latest available observation: {result['latest_valid_date']}"
        )
        st.write(
            f"Total valid observations received: {result['valid_months']} · "
            f"Missing observations: {result['missing_months']} · "
            f"Coverage: {result['completeness']:.1f}% "
            f"({result['valid_months']}/{result['expected_months']} months)"
        )
        st.write(
            f"Spatial resolution: {result['spatial_resolution']} · "
            f"Retrieved: {retrieved_at}"
        )
    st.write(f"Analysis method: {result['method']}")

    if result["completeness"] < 90:
        st.warning(
            "90% से कम डेटा उपलब्ध है। नतीजे को सावधानी से समझें।"
            if language == LANG_HINDI
            else "Data completeness is below 90%. Treat the trend result cautiously."
        )

    decision_significant = result["significant"] if adjusted_p is None else adjusted_p < 0.05
    title = (
        "महत्वपूर्ण बदलाव का संकेत मिला"
        if decision_significant and language == LANG_HINDI
        else "महत्वपूर्ण बदलाव का संकेत नहीं मिला"
        if language == LANG_HINDI
        else "SIGNIFICANT TREND DETECTED"
        if decision_significant
        else "NO SIGNIFICANT TREND DETECTED"
    )
    sub = (
        "जांच में लंबे समय के एकतरफा बदलाव का सांख्यिकीय प्रमाण मिला।"
        if decision_significant and language == LANG_HINDI
        else "इस जांच में पर्याप्त सांख्यिकीय प्रमाण नहीं मिला।"
        if language == LANG_HINDI
        else "The test found evidence of a monotonic trend at the 5% level."
        if decision_significant
        else "The test did not find enough evidence of a monotonic trend at the 5% level."
    )
    if is_demo:
        title = (
            "SYNTHETIC STATISTICS EXAMPLE"
            if language != LANG_HINDI
            else "SYNTHETIC STATISTICS EXAMPLE · डेमो विश्लेषण"
        )
        sub = (
            "The statistical test applies only to generated sample values, not to actual observations for this city."
            if language != LANG_HINDI
            else "सांख्यिकीय जांच केवल बनाए गए नमूना मानों पर लागू है, इस शहर के वास्तविक अवलोकनों पर नहीं।"
        )
    color = "#153c30" if decision_significant else "#3b3020"
    border = "#4c9b78" if decision_significant else "#9a7840"

    st.markdown(
        f"""
        <div style='background:{color};border:1px solid {border};border-radius:18px;padding:1.2rem 1.35rem;margin:.6rem 0 1rem'>
            <div class='eyebrow'>{title}</div>
            <div style='font-size:1rem;color:#eef6ef;margin-top:.45rem'>{verdict}</div>
            <div class='muted' style='margin-top:.45rem'>{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    rate_fmt = (
        f"{result['slope_per_decade']:+.2f}"
        if result["kind"] == "rain"
        else f"{result['slope_per_decade']:+.3f}"
    )
    c1.markdown(
        f"<div class='metric'><div class='metric-label'>Rate / decade</div><div class='metric-value'>{rate_fmt}</div><div class='muted'>{result['trend_unit']}</div></div>",
        unsafe_allow_html=True,
    )

    p_value = result["p_value"] if adjusted_p is None else adjusted_p
    c2.markdown(
        f"<div class='metric'><div class='metric-label'>p-value</div><div class='metric-value'>{p_value:.4f}</div><div class='muted'>Threshold: 0.05</div></div>",
        unsafe_allow_html=True,
    )
    c3.markdown(
        f"<div class='metric'><div class='metric-label'>Data completeness</div><div class='metric-value'>{result['completeness']:.1f}%</div><div class='muted'>{result['valid_months']} / {result['expected_months']} months</div></div>",
        unsafe_allow_html=True,
    )
    acf = result["lag1_autocorrelation"]
    acf_text = "n/a" if pd.isna(acf) else f"{acf:+.2f}"
    c4.markdown(
        f"<div class='metric'><div class='metric-label'>Lag-1 autocorrelation</div><div class='metric-value'>{acf_text}</div><div class='muted'>Detrended annual values</div></div>",
        unsafe_allow_html=True,
    )

    if language == LANG_HINDI:
        tab_names = ["मासिक डेटा", "लंबे समय का ट्रेंड", t["report"]]
    else:
        tab_names = ["Monthly observations", "Long-term trend", t["report"]]

    tab_raw, tab_trend, tab_report = st.tabs(tab_names)

    with tab_raw:
        monthly = result["monthly"].dropna(subset=["display_value"])
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=monthly.index,
                y=monthly["display_value"],
                mode="lines+markers",
                name=t["monthly_value"],
                line=dict(color="#80d9b5", width=1.7),
                marker=dict(size=3),
                fill="tozeroy",
                fillcolor="rgba(128,217,181,.08)",
                hovertemplate=f"%{{x|%b %Y}}<br>%{{y:.2f}} {result['unit']}<extra></extra>",
            )
        )
        fig.update_layout(
            template="plotly_dark",
            height=390,
            margin=dict(l=10, r=10, t=24, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(7,17,15,.25)",
            yaxis_title=result["unit"],
            xaxis_title=t["month"],
            dragmode="pan",
            hovermode="x unified",
            xaxis_rangeslider_visible=True,
        )
        st.plotly_chart(
            fig,
            width="stretch",
            config={"scrollZoom": True, "displaylogo": False, "responsive": True},
        )
        st.caption(
            "मासिक डेटा में मौसम का दोहराव बना रहता है। बारिश के मान NASA की मासिक औसत दैनिक दर से अनुमानित हैं।"
            if language == LANG_HINDI
            else "Monthly observations retain the seasonal cycle. Rainfall values are estimated monthly totals."
        )

    with tab_trend:
        annual = result["annual"]
        years = annual.index.to_numpy(dtype=float)
        line = result["slope_per_year"] * years + (
            annual.iloc[0] - result["slope_per_year"] * years[0]
        )
        annual_name = t["annual_rainfall"] if result["kind"] == "rain" else t["annual_average"]
        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=annual.index,
                y=annual.values,
                mode="lines+markers",
                name=annual_name,
                line=dict(color="#80d9b5", width=2.3),
                marker=dict(size=7),
                hovertemplate=f"%{{x:.0f}}<br>%{{y:.2f}} {result['trend_unit']}<extra></extra>",
            )
        )
        fig2.add_trace(
            go.Scatter(
                x=annual.index,
                y=line,
                mode="lines",
                name=t["trend_line"],
                line=dict(color="#f2c879", width=3, dash="dash"),
                hovertemplate=f"%{{x:.0f}}<br>%{{y:.2f}} {result['trend_unit']}<extra></extra>",
            )
        )
        fig2.update_layout(
            template="plotly_dark",
            height=390,
            margin=dict(l=10, r=10, t=24, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(7,17,15,.25)",
            yaxis_title=result["trend_unit"],
            xaxis_title=t["year"],
            dragmode="pan",
            hovermode="x unified",
        )
        st.plotly_chart(
            fig2,
            width="stretch",
            config={"scrollZoom": True, "displaylogo": False, "responsive": True},
        )
        st.caption(
            "सालाना औसत में हर महीने के दिनों का भार शामिल है; वर्षा के लिए सालाना कुल दिखाया गया है।"
            if language == LANG_HINDI
            else "Annual means are day-weighted; rainfall is shown as an annual total."
        )

    with tab_report:
        report = make_report(result, city, latitude, longitude, verdict, adjusted_p=adjusted_p)
        st.code(report, language="text")
        st.download_button(
            t["download"],
            data=report.encode("utf-8"),
            file_name=f"earth-pulse-{city.lower().replace(' ', '-')}-{result['variable'].lower().replace(' ', '-')}.txt",
            mime="text/plain",
            width="stretch",
        )

    render_parameter_interpretation(result["parameter"])

    with st.expander(t["technical"]):
        st.write(f"**Method:** {result['method']}")
        st.write(
            f"**Mann–Kendall tau:** {result['tau']:.4f} | "
            f"**z-score:** {result['z_score']:.3f} | "
            f"**p-value:** {result['p_value']:.5f}"
        )
        st.write(
            f"**Sen's slope:** {result['slope_per_decade']:+.5f} "
            f"{result['trend_unit']} per decade"
        )
        st.write(
            f"**95% CI:** [{result['ci_low_per_decade']:+.5f}, "
            f"{result['ci_high_per_decade']:+.5f}] {result['trend_unit']} per decade"
        )
        st.write(f"**Lag-1 autocorrelation:** {acf_text}")
        st.write(
            f"**POWER parameter:** `{result['parameter']}` | "
            f"**API version:** `{result['api_version']}`"
        )
        st.write(
            f"**Dataset:** {result['dataset']} | **API units:** {result['api_unit']} | "
            f"**Spatial resolution:** {result['spatial_resolution']}"
        )
        st.write(f"**Period:** {result['start']} to {result['end']}")
        st.markdown(
            "[NASA POWER Monthly API](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/)"
        )

    with st.expander(t["limitations"]):
        limitations = [
            "A trend does not prove why the variable changed. Correlation is not causation.",
            "Statistical significance is not the same as real-world importance.",
            "NASA POWER is gridded data, not a local weather-station reading.",
            "Annual aggregation can hide short-lived extremes.",
            "Missing months lower data completeness.",
            "A non-significant result is not proof of zero change.",
        ]
        if language == LANG_HINDI:
            limitations = [
                "ट्रेंड यह साबित नहीं करता कि बदलाव क्यों हुआ।",
                "सांख्यिकीय महत्व और वास्तविक दुनिया का प्रभाव अलग बातें हैं।",
                "NASA POWER ग्रिड-आधारित डेटा है, स्थानीय मौसम स्टेशन की रीडिंग नहीं।",
                "सालाना औसत कुछ समय के छोटे बदलाव छिपा सकता है।",
                "गायब महीनों से डेटा की पूर्णता कम होती है।",
                "महत्वपूर्ण संकेत न मिलना, बदलाव बिल्कुल न होने का प्रमाण नहीं है।",
            ]
        for item in limitations:
            st.markdown(f"- {item}")


# -------------------------------------------------------------------
# PAGES
# -------------------------------------------------------------------
def render_home():
    is_hi = st.session_state.language == LANG_HINDI

    eyebrow = (
        "NASA OPEN DATA · पृथ्वी प्रणाली · सार्वजनिक विज्ञान"
        if is_hi
        else "NASA OPEN DATA · EARTH SYSTEMS · PUBLIC SCIENCE"
    )
    description = t["home_desc"]
    tags = [t["no_login"], t["bilingual"], t["open_data"]]
    tag_html = "".join(f"<span class='tag'>{tag}</span>" for tag in tags)

    st.markdown(
        f"""
        <div class='hero'>
            <div class='eyebrow'>{eyebrow}</div>
            <h1>EARTH<br>PULSE<span style='color:#9be7c4'>.</span></h1>
            <p>{description}</p>
            {tag_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    start_col, demo_col = st.columns(2)
    with start_col:
        st.button(
            f"🔎  {t['start']}",
            key="home_start_investigation",
            width="stretch",
            type="primary",
            on_click=navigate_to_page,
            args=(PAGE_INVESTIGATE,),
        )
    with demo_col:
        st.button(
            f"🧭  {t['watch']}",
            key="home_explore_demo",
            width="stretch",
            type="secondary",
            on_click=navigate_to_page,
            args=(PAGE_DEMO,),
        )

    st.write("")
    cards = [
        ("01 · ASK" if not is_hi else "01 · चुनें", t["card1_title"], t["card1_text"]),
        ("02 · INVESTIGATE" if not is_hi else "02 · जांचें", t["card2_title"], t["card2_text"]),
        ("03 · SHARE" if not is_hi else "03 · साझा करें", t["card3_title"], t["card3_text"]),
    ]
    columns = st.columns(3)
    for column, card in zip(columns, cards):
        label, title, description_text = card
        with column:
            st.markdown(
                f"""
                <div class='panel'>
                    <div class='eyebrow'>{label}</div>
                    <h3>{title}</h3>
                    <p class='muted'>{description_text}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()
    st.caption(t["home_footer"])


def render_monthly_snapshot(
    frame: pd.DataFrame,
    variable: str,
    location: str,
    period: str,
    language: str,
    coordinates: tuple[float, float] | None = None,
    include_data_quality: bool = True,
    analysis_note: str | None = None,
):
    is_hi = language == LANG_HINDI
    if analysis_note:
        st.info(analysis_note)
    elif not VARIABLES[variable].get("trend_supported", True):
        st.info(VARIABLES[variable]["product_note"])
    if include_data_quality:
        render_monthly_data_quality(
            frame,
            variable,
            location,
            coordinates,
            selected_period=period.replace("–", " to "),
        )
    prepared = frame.copy()
    if "display_value" not in prepared:
        prepared = prepare_monthly_series(frame, variable)
    monthly = prepared.dropna(subset=["display_value"])
    if monthly.empty:
        st.warning("इस समय अवधि के लिए मान्य मासिक अवलोकन उपलब्ध नहीं हैं।" if is_hi else "No valid monthly observations are available for this period.")
        return

    st.subheader(location)
    st.caption(
        f"{'अवधि' if is_hi else 'Period'}: {period} · "
        f"{'डेटा स्रोत' if is_hi else 'Data source'}: "
        f"{frame.attrs.get('source', 'NASA POWER Monthly API')}"
    )
    latest = monthly.iloc[-1]
    latest_label = monthly.index[-1].strftime("%b %Y")
    metric_label = "नवीनतम मासिक मान" if is_hi else "Latest monthly value"
    st.metric(metric_label, f"{latest['display_value']:.2f} {VARIABLES[variable]['unit']}")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=monthly.index,
            y=monthly["display_value"],
            mode="lines+markers",
            name=VARIABLES[variable]["display"],
            line=dict(color="#80d9b5", width=2),
            marker=dict(size=5),
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=360,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(7,17,15,.25)",
        yaxis_title=VARIABLES[variable]["unit"],
        xaxis_title="महीना" if is_hi else "Month",
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "responsive": True})
    st.caption(
        f"{'नवीनतम अवलोकन' if is_hi else 'Latest observation'}: {latest_label} · "
        f"{'मासिक डेटा; तात्कालिक सेंसर रीडिंग नहीं।' if is_hi else 'Monthly data; not an instantaneous sensor reading.'}"
    )
    render_parameter_interpretation(VARIABLES[variable]["parameter"])


def render_latest_observation(
    frame: pd.DataFrame,
    variable: str,
    location: str,
    language: str,
    coordinates: tuple[float, float] | None = None,
):
    is_hi = language == LANG_HINDI
    prepared = prepare_monthly_series(frame, variable).dropna(subset=["display_value"])
    if prepared.empty:
        st.warning("इस स्थान के लिए कोई मान्य अवलोकन उपलब्ध नहीं है।" if is_hi else "No valid observation is currently available for this location.")
        return

    latest = prepared.iloc[-1]
    observation_date = prepared.index[-1].strftime("%B %Y")
    st.subheader(location)
    render_monthly_data_quality(frame, variable, location, coordinates)
    st.metric(
        "नवीनतम उपलब्ध मासिक मान" if is_hi else "Latest available monthly value",
        f"{latest['display_value']:.2f} {VARIABLES[variable]['unit']}",
        help=observation_date,
    )
    retrieved_at = frame.attrs.get("retrieved_at", "not provided")
    if retrieved_at != "not provided":
        retrieved_at = datetime.fromisoformat(retrieved_at).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    st.write(f"**{'अवलोकन अवधि' if is_hi else 'Observation month'}:** {observation_date}")
    st.write(
        f"**{'डेटा उपलब्धता जांच' if is_hi else 'Availability checked / retrieved'}:** "
        f"{retrieved_at}"
    )
    st.write(
        f"**{'डेटा स्रोत' if is_hi else 'Data source'}:** "
        f"{frame.attrs.get('source', 'NASA POWER Monthly API')} · "
        f"{frame.attrs.get('data_sources', 'NASA POWER')}"
    )
    st.info(
        "NASA POWER का डेटा आवधिक मासिक ग्रिड डेटा है, तात्कालिक लाइव सेंसर माप नहीं। अवलोकन अवधि सबसे हाल का उपलब्ध महीना है।"
        if is_hi
        else "NASA POWER provides periodically updated, gridded monthly data—not instantaneous live sensor measurements. The observation period is the latest month currently available."
    )
    recent = frame.loc[frame.index >= (prepared.index[-1] - pd.DateOffset(months=23))]
    render_monthly_snapshot(
        recent,
        variable,
        location,
        f"{recent.index.min():%b %Y}–{recent.index.max():%b %Y}",
        language,
        coordinates=coordinates,
        include_data_quality=False,
    )


def render_seasonal_result(
    seasonal: pd.DataFrame,
    variable: str,
    location: str,
    years: tuple[int, int],
    language: str,
    source: str,
    monthly_frame: pd.DataFrame | None = None,
    coordinates: tuple[float, float] | None = None,
):
    is_hi = language == LANG_HINDI
    is_demo = "DEMO DATA" in source
    if seasonal.empty:
        st.warning("चुनी गई अवधि में कोई पूर्ण मौसम उपलब्ध नहीं है।" if is_hi else "No complete seasons are available in the selected period.")
        return

    unit = "mm/season (estimated)" if VARIABLES[variable]["kind"] == "rain" else VARIABLES[variable]["unit"]
    st.subheader(location)
    st.caption(
        f"{'मौसम-वर्ष' if is_hi else 'Season years'}: {years[0]}–{years[1]} · "
        f"{'डेटा स्रोत' if is_hi else 'Data source'}: {source}"
    )
    if is_demo:
        st.warning(
            "Synthetic demonstration data — not actual environmental observations."
        )
    elif monthly_frame is not None:
        render_monthly_data_quality(
            monthly_frame,
            variable,
            location,
            coordinates,
            selected_period=f"{years[0]}-01 to {years[1]}-12",
        )
    summary = (
        seasonal.groupby("season", sort=False)["value"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={
            "season": "मौसम" if is_hi else "Season",
            "mean": "औसत" if is_hi else "Mean",
            "count": "पूर्ण वर्ष" if is_hi else "Complete years",
        })
    )
    summary["Mean" if not is_hi else "औसत"] = summary["Mean" if not is_hi else "औसत"].round(2)
    st.dataframe(summary, hide_index=True, width="stretch")

    fig = go.Figure()
    for season in seasonal["season"].drop_duplicates():
        subset = seasonal[seasonal["season"] == season]
        fig.add_trace(
            go.Scatter(
                x=subset["year"],
                y=subset["value"],
                mode="lines+markers",
                name=season,
                hovertemplate=f"%{{x}}<br>%{{y:.2f}} {unit}<extra>{season}</extra>",
            )
        )
    fig.update_layout(
        template="plotly_dark",
        height=380,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(7,17,15,.25)",
        yaxis_title=unit,
        xaxis_title="वर्ष" if is_hi else "Year",
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "responsive": True})
    if monthly_frame is not None:
        monthly = prepare_monthly_series(monthly_frame, variable)
        climatology = monthly.groupby("month")["display_value"].mean().reindex(range(1, 13))
        month_labels = [calendar.month_abbr[month] for month in range(1, 13)]
        monthly_fig = go.Figure(
            go.Bar(
                x=month_labels,
                y=climatology.to_numpy(),
                marker_color="#80d9b5",
                name="Monthly climatology",
                hovertemplate=f"%{{x}}<br>%{{y:.2f}} {unit}<extra></extra>",
            )
        )
        monthly_fig.update_layout(
            template="plotly_dark",
            height=300,
            margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(7,17,15,.25)",
            yaxis_title=unit,
            xaxis_title="Month",
        )
        st.markdown("**Monthly climatology across the selected period**")
        st.plotly_chart(
            monthly_fig,
            width="stretch",
            config={"displaylogo": False, "responsive": True},
        )
    st.caption(
        "तुलना में केवल पूरे मौसम शामिल हैं; वर्षा अनुमानित मासिक योगों का मौसमी कुल है।"
        if is_hi
        else "Only complete seasons are compared. Rainfall is the seasonal total of estimated monthly accumulations. "
        "The monthly climatology summarizes the average calendar-month value across the same archive."
    )
    render_parameter_interpretation(VARIABLES[variable]["parameter"])


def render_investigate():
    is_hi = st.session_state.language == LANG_HINDI

    st.title("Explore the Living Planet" if not is_hi else "जीवंत पृथ्वी को जानें")
    st.caption(
        "Explore Earth, choose an environmental signal, and investigate a location."
        if not is_hi
        else "पृथ्वी को देखें, पर्यावरणीय संकेत चुनें और किसी स्थान की जांच करें।"
    )

    st.markdown(
        "<div class='eyebrow'>STEP 1 · CHOOSE EXPLORATION MODE</div>"
        if not is_hi
        else "<div class='eyebrow'>चरण 1 · जांच का तरीका चुनें</div>",
        unsafe_allow_html=True,
    )
    st.subheader("Choose Your Exploration Mode" if not is_hi else "अपनी जांच का तरीका चुनें")
    modes = [
        ("seasonal", "🌦️", "Seasonal Mode", "Compare environmental seasons.", "मौसमों की पर्यावरणीय तुलना करें।"),
        ("realtime", "◷", "Real-Time Mode", "See the latest available monthly data.", "नवीनतम उपलब्ध मासिक डेटा देखें।"),
        ("historical", "↗", "Historical Mode", "Explore long-term trends.", "लंबे समय के ट्रेंड देखें।"),
        ("location", "⌖", "Location Mode", "Investigate any point on Earth.", "पृथ्वी पर किसी भी स्थान की जांच करें।"),
    ]
    st.session_state.setdefault("exploration_mode", "historical")
    if st.session_state.exploration_mode == "explorer":
        st.session_state.exploration_mode = "location"
    localized_mode_titles = {
        "seasonal": "मौसमी तरीका",
        "realtime": "नवीनतम तरीका",
        "historical": "ऐतिहासिक तरीका",
        "location": "स्थान तरीका",
    }
    for offset in range(0, len(modes), 2):
        mode_columns = st.columns(2)
        for column, (mode, icon, title, description, description_hi) in zip(
            mode_columns, modes[offset:offset + 2]
        ):
            with column:
                selected = st.session_state.exploration_mode == mode
                st.markdown(
                    f"<div class='panel' style='min-height:110px;border-color:{'#9be7c4' if selected else '#24443c'}'>"
                    f"<div class='eyebrow'>{icon} {'SELECTED' if selected and not is_hi else 'चयनित' if selected else ''}</div>"
                    f"<strong>{title if not is_hi else localized_mode_titles[mode]}</strong>"
                    f"<p class='muted'>{description if not is_hi else description_hi}</p></div>",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Choose" if not is_hi else "चुनें",
                    key=f"mode_{mode}",
                    type="primary" if selected else "secondary",
                    width="stretch",
                ):
                    if st.session_state.exploration_mode != mode:
                        st.session_state.exploration_mode = mode
                        st.session_state.last_result = None
                        st.session_state.pop("investigation_output", None)
                        st.rerun()

    mode = st.session_state.exploration_mode
    if mode == "location":
        render_global_explorer(
            location_picker=location_picker,
            language=st.session_state.language,
        )
        return

    st.markdown(
        "<div class='eyebrow'>STEP 2 · CHOOSE AN ENVIRONMENTAL SIGNAL</div>"
        if not is_hi
        else "<div class='eyebrow'>चरण 2 · पर्यावरणीय संकेत चुनें</div>",
        unsafe_allow_html=True,
    )
    variable_names = list(VARIABLES)
    if not variable_names:
        st.error("No variables are configured in earth_pulse.data.VARIABLES.")
        return
    variable_labels = {
        "Temperature": "Average Air Temperature",
        "Rainfall": "Precipitation",
        "Relative humidity": "Relative Humidity",
        "Wind speed": "Wind Speed",
    }
    variable_labels_hi = {
        "Temperature": "औसत वायु तापमान",
        "Rainfall": "वर्षा",
        "Relative humidity": "सापेक्ष आर्द्रता",
        "Wind speed": "हवा की गति",
    }
    variable = st.selectbox(
        "पर्यावरणीय संकेत" if is_hi else "Environmental signal",
        variable_names,
        format_func=lambda name: (variable_labels_hi if is_hi else variable_labels).get(name, name),
        key="investigation_variable",
    )
    desc_key = "description_hi" if is_hi else "description"
    description = VARIABLES[variable].get(desc_key) or VARIABLES[variable].get("description")
    if description:
        st.caption(description)

    st.markdown(
        "<div class='eyebrow'>STEP 3 · CHOOSE A LOCATION</div>"
        if not is_hi
        else "<div class='eyebrow'>चरण 3 · स्थान चुनें</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Location is requested only after you click the button. You can always use a city or enter coordinates."
        if not is_hi
        else "स्थान केवल बटन दबाने पर मांगा जाएगा। आप शहर चुन सकते हैं या निर्देशांक दर्ज कर सकते हैं।"
    )
    location_response = location_picker(
        buttonLabel="📍 Use My Current Location" if not is_hi else "📍 मेरा वर्तमान स्थान उपयोग करें",
        helpText="Your browser will ask permission." if not is_hi else "आपका ब्राउज़र अनुमति मांगेगा।",
        pendingText="Requesting location permission…" if not is_hi else "स्थान की अनुमति मांगी जा रही है…",
        successText="Location detected." if not is_hi else "स्थान मिल गया।",
        confirmLabel="Confirm this location" if not is_hi else "इस स्थान की पुष्टि करें",
        confirmedText="Location confirmed for this investigation." if not is_hi else "इस जांच के लिए स्थान की पुष्टि हुई।",
        deniedText="Location permission was denied. Enter coordinates manually." if not is_hi else "स्थान की अनुमति नहीं मिली। निर्देशांक खुद दर्ज करें।",
        unavailableText="Location is unavailable. Enter coordinates manually." if not is_hi else "स्थान उपलब्ध नहीं है। निर्देशांक खुद दर्ज करें।",
        key="browser_location_picker",
        default=None,
    )
    if isinstance(location_response, dict):
        request_id = location_response.get("requestId")
        if request_id and request_id != st.session_state.get("seen_location_request_id"):
            st.session_state.seen_location_request_id = request_id
            if location_response.get("status") == "granted":
                st.session_state.current_coordinates = (
                    float(location_response["latitude"]),
                    float(location_response["longitude"]),
                )
                st.session_state.current_location_details = {
                    "accuracy": float(location_response.get("accuracy", float("nan"))),
                    "timestamp": int(location_response.get("timestamp", 0)),
                }
                st.session_state.location_method = "Current location"
                st.session_state.location_message = None
            elif location_response.get("status") == "pending":
                st.session_state.current_coordinates = None
                st.session_state.current_location_details = None
                st.session_state.location_message = None
            else:
                st.session_state.current_coordinates = None
                st.session_state.current_location_details = None
                st.session_state.location_message = location_response.get("status")

    location_methods = ["Saved city", "Current location", "Manual coordinates"]
    method_labels = {
        "Saved city": "Choose a city" if not is_hi else "शहर चुनें",
        "Current location": "Current location" if not is_hi else "वर्तमान स्थान",
        "Manual coordinates": "Enter coordinates manually" if not is_hi else "निर्देशांक खुद दर्ज करें",
    }
    st.session_state.setdefault("location_method", "Saved city")
    location_method = st.selectbox(
        "Location method" if not is_hi else "स्थान का तरीका",
        location_methods,
        format_func=lambda value: method_labels[value],
        key="location_method",
    )
    location_name = ""
    selected_coordinates = None
    if location_method == "Saved city":
        city = st.selectbox(
            "City" if not is_hi else "शहर",
            list(CITIES),
            index=list(CITIES).index("Delhi"),
            key="investigation_city",
        )
        selected_coordinates = (CITIES[city]["latitude"], CITIES[city]["longitude"])
        location_name = city
    elif location_method == "Current location":
        selected_coordinates = st.session_state.get("current_coordinates")
        if selected_coordinates:
            location_name = "Current location" if not is_hi else "वर्तमान स्थान"
        else:
            st.warning(
                "Use the location button first, or choose manual coordinates."
                if not is_hi
                else "पहले स्थान बटन दबाएं या निर्देशांक खुद दर्ज करें।"
            )
    else:
        loc1, loc2 = st.columns(2)
        default_coords = CITIES["Delhi"]
        latitude = loc1.number_input(
            "Latitude (−90 to +90)" if not is_hi else "अक्षांश (−90 से +90)",
            min_value=-90.0,
            max_value=90.0,
            value=float(default_coords["latitude"]),
            format="%.4f",
            key="manual_latitude",
        )
        longitude = loc2.number_input(
            "Longitude (−180 to +180)" if not is_hi else "देशांतर (−180 से +180)",
            min_value=-180.0,
            max_value=180.0,
            value=float(default_coords["longitude"]),
            format="%.4f",
            key="manual_longitude",
        )
        selected_coordinates = (latitude, longitude)
        location_name = f"Custom point ({latitude:.4f}, {longitude:.4f})"

    if selected_coordinates:
        st.info(
            f"{'चुना गया स्थान' if is_hi else 'Selected location'}: {location_name} · "
            f"{selected_coordinates[0]:.4f}, {selected_coordinates[1]:.4f}"
        )

    st.markdown(
        "<div class='eyebrow'>STEP 4 · SELECT THE PERIOD</div>"
        if not is_hi
        else "<div class='eyebrow'>चरण 4 · समय अवधि चुनें</div>",
        unsafe_allow_html=True,
    )
    current_year = datetime.now().year
    archive_end = current_year - 1
    selected_seasons: list[str] = []
    start_year, end_year = archive_end, archive_end
    single_year = False

    if mode == "seasonal":
        available_seasons = season_months(*(selected_coordinates or (28.6139, 77.2090)))
        seasonal_coordinates = selected_coordinates or (28.6139, 77.2090)
        calendar_key = f"{round(seasonal_coordinates[0])}_{round(seasonal_coordinates[1])}"
        month_options = list(range(1, 13))
        with st.expander("Customize seasonal month definitions"):
            custom_definitions = {}
            for season_name, default_months in available_seasons.items():
                chosen_months = st.multiselect(
                    f"{season_name} months",
                    month_options,
                    default=list(default_months),
                    format_func=lambda month: calendar.month_name[month],
                    key=f"season_definition_{calendar_key}_{season_name}",
                )
                if chosen_months:
                    custom_definitions[season_name] = tuple(chosen_months)
        available_seasons = season_months(
            *seasonal_coordinates,
            custom_definitions=custom_definitions,
        )
        previous_seasons = st.session_state.get("selected_seasons")
        default_season = (
            "Monsoon"
            if "Monsoon" in available_seasons
            else "Winter"
            if "Winter" in available_seasons
            else next(iter(available_seasons))
        )
        if previous_seasons is not None:
            retained_seasons = [season for season in previous_seasons if season in available_seasons]
            st.session_state.selected_seasons = retained_seasons or [default_season]
        season_labels = {
            "Spring": "वसंत",
            "Summer": "ग्रीष्म",
            "Monsoon": "मानसून",
            "Autumn": "शरद",
            "Winter": "शीत",
        }
        selected_seasons = st.multiselect(
            "Compare seasons" if not is_hi else "मौसमों की तुलना करें",
            list(available_seasons),
            default=[default_season],
            format_func=lambda value: season_labels.get(value, value) if is_hi else value,
            key="selected_seasons",
        )
        start_year, end_year = st.slider(
            "Season year range" if not is_hi else "मौसम-वर्ष की अवधि",
            min_value=1981,
            max_value=archive_end,
            value=(max(2004, archive_end - 21), archive_end),
            key="season_year_range",
        )
        st.caption(
            "Uses hemisphere-based meteorological months; Monsoon is offered only for South Asia (June–September). Other tropical climates may use different local wet/dry seasons."
            if not is_hi
            else "गोलार्ध के मौसम-वाले महीनों का उपयोग होता है; मानसून केवल दक्षिण एशिया के लिए (जून–सितंबर) दिखाया गया है। अन्य उष्णकटिबंधीय क्षेत्रों में स्थानीय वर्षा-ऋतु अलग हो सकती है।"
        )
    elif mode == "historical":
        period_options = ["Date range", "Single year"]
        period_label = {"Date range": "Year range", "Single year": "Single year"}
        period_kind = st.radio(
            "Historical period" if not is_hi else "ऐतिहासिक अवधि",
            period_options,
            format_func=lambda value: (
                ("वर्ष अवधि" if value == "Date range" else "एक वर्ष")
                if is_hi
                else period_label[value]
            ),
            horizontal=True,
            key=f"{mode}_period_kind",
        )
        if period_kind == "Single year":
            single_year = True
            start_year = end_year = st.selectbox(
                "Year" if not is_hi else "वर्ष",
                list(range(1981, archive_end + 1)),
                index=archive_end - 1981,
                key=f"{mode}_single_year",
            )
        else:
            start_year, end_year = st.slider(
                "Year range" if not is_hi else "वर्ष अवधि",
                min_value=1981,
                max_value=archive_end,
                value=(max(2004, archive_end - 21), archive_end),
                key=f"{mode}_year_range",
            )
        st.caption(
            f"{'NASA POWER मासिक संग्रह' if is_hi else 'NASA POWER monthly archive'}: 1981–{archive_end}. "
            f"{'लंबे ट्रेंड विश्लेषण के लिए कम से कम 8 पूरे वर्ष जरूरी हैं।' if is_hi else 'At least 8 complete years are needed for trend analysis.'}"
        )
    else:
        st.info(
            "Showing the newest observation currently available from NASA POWER."
            if not is_hi
            else "NASA POWER से अभी उपलब्ध नवीनतम अवलोकन दिखाया जाएगा।"
        )

    st.markdown(
        "<div class='eyebrow'>STEP 5 · INVESTIGATE</div>"
        if not is_hi
        else "<div class='eyebrow'>चरण 5 · जांच करें</div>",
        unsafe_allow_html=True,
    )
    submitted = st.button(
        "🔎  Investigate" if not is_hi else "🔎  जांच करें",
        type="primary",
        width="stretch",
        key="investigate_submit",
    )
    if submitted:
        st.session_state.last_result = None
        st.session_state.pop("investigation_output", None)
        if selected_coordinates is None:
            st.error(
                "Select a city, obtain your location, or enter valid coordinates."
                if not is_hi
                else "शहर चुनें, वर्तमान स्थान लें या सही निर्देशांक दर्ज करें।"
            )
        elif mode == "seasonal" and not selected_seasons:
            st.error("Select at least one season." if not is_hi else "कम से कम एक मौसम चुनें।")
        else:
            latitude, longitude = selected_coordinates
            if not location_name:
                location_name = f"Custom point ({latitude:.4f}, {longitude:.4f})"
            try:
                with st.spinner(
                    "NASA POWER डेटा लिया जा रहा है…" if is_hi else "Fetching data from NASA POWER…"
                ):
                    if mode == "realtime":
                        frame = cached_nasa_fetch(
                            latitude, longitude, variable, 1981, current_year
                        )
                        st.session_state.investigation_output = {
                            "kind": "latest",
                            "frame": frame,
                            "variable": variable,
                            "location": location_name,
                            "coordinates": selected_coordinates,
                            "language": st.session_state.language,
                        }
                    elif mode == "seasonal":
                        fetch_start = max(1981, start_year - 1)
                        frame = cached_nasa_fetch(
                            latitude, longitude, variable, fetch_start, end_year
                        )
                        seasonal = seasonal_series(
                            frame,
                            variable,
                            selected_seasons,
                            start_year,
                            end_year,
                            latitude,
                            longitude,
                            custom_definitions=custom_definitions,
                        )
                        if seasonal.empty:
                            raise ValueError("NASA POWER returned no complete seasonal observations for this selection.")
                        st.session_state.investigation_output = {
                            "kind": "seasonal",
                            "seasonal": seasonal,
                            "frame": frame,
                            "variable": variable,
                            "location": location_name,
                            "coordinates": selected_coordinates,
                            "years": (start_year, end_year),
                            "source": frame.attrs.get("source", "NASA POWER Monthly API"),
                            "language": st.session_state.language,
                        }
                    else:
                        if (
                            not single_year
                            and end_year - start_year + 1 >= 8
                            and VARIABLES[variable].get("trend_supported", True)
                        ):
                            result = load_and_analyze(
                                location_name,
                                latitude,
                                longitude,
                                variable,
                                start_year,
                                end_year,
                            )
                            st.session_state.last_result = {
                                "result": result,
                                "city": location_name,
                                "latitude": latitude,
                                "longitude": longitude,
                                "language": st.session_state.language,
                            }
                        else:
                            frame = cached_nasa_fetch(
                                latitude, longitude, variable, start_year, end_year
                            )
                            analysis_note = None
                            if VARIABLES[variable].get("trend_supported", True):
                                analysis_note = (
                                    "Trend analysis cannot be completed reliably from a single year."
                                    if single_year
                                    else "Trend analysis cannot be completed reliably with fewer than eight requested years."
                                )
                            st.session_state.investigation_output = {
                                "kind": "snapshot",
                                "frame": frame,
                                "variable": variable,
                                "location": location_name,
                                "coordinates": selected_coordinates,
                                "period": f"{start_year}" if single_year else f"{start_year}–{end_year}",
                                "language": st.session_state.language,
                                "analysis_note": analysis_note,
                            }
            except Exception as exc:
                st.error(str(exc))
                st.info(
                    "आप Demo lab में केवल उदाहरण के लिए बनाया गया डेटा देख सकते हैं।"
                    if is_hi
                    else "Demo lab is available for clearly labelled synthetic examples."
                )

    output = st.session_state.get("investigation_output")
    if output:
        st.divider()
        st.caption("Showing results from the last submitted investigation." if not is_hi else "पिछली जमा की गई जांच के परिणाम।")
        if output["kind"] == "latest":
            render_latest_observation(
                output["frame"],
                output["variable"],
                output["location"],
                output["language"],
                coordinates=output.get("coordinates"),
            )
        elif output["kind"] == "seasonal":
            render_seasonal_result(
                output["seasonal"],
                output["variable"],
                output["location"],
                output["years"],
                output["language"],
                output["source"],
                monthly_frame=output.get("frame"),
                coordinates=output.get("coordinates"),
            )
        else:
            render_monthly_snapshot(
                output["frame"],
                output["variable"],
                output["location"],
                output["period"],
                output["language"],
                coordinates=output.get("coordinates"),
                analysis_note=output.get("analysis_note"),
            )
    if st.session_state.last_result:
        saved = st.session_state.last_result
        st.divider()
        render_result(
            saved["result"],
            saved["city"],
            saved["latitude"],
            saved["longitude"],
            saved["language"],
        )

    st.divider()
    st.subheader("Explore the 3D Earth" if not is_hi else "3D पृथ्वी देखें")
    st.caption(t["globe_help"])
    render_earth_globe(height=440)


def render_demo():
    is_hi = st.session_state.language == LANG_HINDI
    st.markdown(
        "<div class='eyebrow'>निर्देशित उदाहरण</div>"
        if is_hi
        else "<div class='eyebrow'>GUIDED INVESTIGATIONS</div>",
        unsafe_allow_html=True,
    )
    st.title(t["demo"])
    st.warning(
        "Synthetic demonstration data — not actual environmental observations."
        if not is_hi
        else "Synthetic demonstration data — not actual environmental observations. "
        "ये NASA के वास्तविक पर्यावरणीय अवलोकन नहीं हैं।"
    )
    st.button(
        "Run a real investigation" if not is_hi else "वास्तविक जांच करें",
        key="demo_run_real_investigation",
        on_click=navigate_to_page,
        args=(PAGE_INVESTIGATE,),
        type="primary",
    )

    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown(
            "<div class='panel'><div class='eyebrow'>DEMO 01 · TEMPERATURE</div><h3>Delhi temperature</h3><p class='muted'>Generated monthly values demonstrate seasonality and a sample trend test; they are not Delhi observations.</p></div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "दिल्ली तापमान डेमो चलाएं" if is_hi else "Run Delhi temperature demo",
            width="stretch",
        ):
            frame = make_demo_series("Delhi", "Temperature", 2004, 2025)
            result = analyze_series(frame, "Temperature", source=frame.attrs["source"])
            st.session_state.demo_result = (
                result,
                "Delhi",
                CITIES["Delhi"]["latitude"],
                CITIES["Delhi"]["longitude"],
            )

    with d2:
        st.markdown(
            "<div class='panel'><div class='eyebrow'>DEMO 02 · RAINFALL</div><h3>Mumbai rainfall</h3><p class='muted'>Generated monthly values demonstrate seasonality and annual aggregation; they are not Mumbai observations.</p></div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "मुंबई बारिश डेमो चलाएं" if is_hi else "Run Mumbai rainfall demo",
            width="stretch",
        ):
            frame = make_demo_series("Mumbai", "Rainfall", 2004, 2025)
            result = analyze_series(frame, "Rainfall", source=frame.attrs["source"])
            st.session_state.demo_result = (
                result,
                "Mumbai",
                CITIES["Mumbai"]["latitude"],
                CITIES["Mumbai"]["longitude"],
            )

    with d3:
        st.markdown(
            "<div class='panel'><div class='eyebrow'>DEMO 03 · INDIA SEASONS</div><h3>Nagpur seasonal climate</h3><p class='muted'>Synthetic temperatures compare winter, pre-monsoon, monsoon, and post-monsoon; they are not measured Nagpur climate.</p></div>",
            unsafe_allow_html=True,
        )
        if st.button(
            "नागपुर मौसमी डेमो चलाएं" if is_hi else "Run Nagpur seasonal demo",
            width="stretch",
            key="nagpur_seasonal_demo",
        ):
            frame = make_demo_series("Nagpur", "Temperature", 2004, 2025)
            seasons = ["Winter", "Pre-monsoon", "Monsoon", "Post-monsoon"]
            seasonal = seasonal_series(
                frame,
                "Temperature",
                seasons,
                2005,
                2025,
                CITIES["Nagpur"]["latitude"],
                CITIES["Nagpur"]["longitude"],
            )
            st.session_state.demo_seasonal_result = {
                "seasonal": seasonal,
                "frame": frame,
                "years": (2005, 2025),
                "source": frame.attrs["source"],
            }

    st.divider()
    st.subheader("Future possibilities" if not is_hi else "भविष्य में जोड़े जा सकने वाले फीचर")
    future_features = [
        ("Live satellite layers", "उपग्रह से मिलने वाली लाइव परतें"),
        ("City-to-city climate comparison", "शहरों के बीच जलवायु की तुलना"),
        ("Extreme event alerts", "अत्यधिक मौसम की चेतावनी"),
        ("Interactive historical timeline", "पुराने डेटा की इंटरैक्टिव समयरेखा"),
        ("AI-assisted plain-language explanations", "AI की मदद से आसान भाषा में व्याख्या"),
    ]
    for english, hindi in future_features:
        st.markdown(f"- {hindi if is_hi else english}")

    if "demo_seasonal_result" in st.session_state:
        seasonal_demo = st.session_state.demo_seasonal_result
        st.warning(
            "Synthetic demonstration data — not actual environmental observations."
            if not is_hi
            else "Synthetic demonstration data — not actual environmental observations. "
            "ये NASA के वास्तविक पर्यावरणीय अवलोकन नहीं हैं।"
        )
        render_seasonal_result(
            seasonal_demo["seasonal"],
            "Temperature",
            "Nagpur, Maharashtra",
            seasonal_demo["years"],
            st.session_state.language,
            seasonal_demo["source"],
            monthly_frame=seasonal_demo["frame"],
        )

    if "demo_result" in st.session_state:
        result, city, latitude, longitude = st.session_state.demo_result
        render_result(result, city, latitude, longitude, language=st.session_state.language)


def render_compare():
    is_hi = st.session_state.language == LANG_HINDI
    st.markdown(
        "<div class='eyebrow'>दो जगह · एक संकेत</div>"
        if is_hi
        else "<div class='eyebrow'>SAME SIGNAL · DIFFERENT PLACES</div>",
        unsafe_allow_html=True,
    )
    st.title("दो जगहों की तुलना करें" if is_hi else "Compare two locations")
    st.write(
        "एक ही मान और समय अवधि के लिए दो शहरों के ट्रेंड की तुलना करें।"
        if is_hi
        else "Compare the same variable and period across two cities."
    )

    with st.form("compare_form"):
        comparable_variables = [
            name for name, metadata in VARIABLES.items()
            if metadata.get("trend_supported", True)
        ]
        variable = st.selectbox(
            "पर्यावरणीय मान" if is_hi else "Earth system variable",
            comparable_variables,
            key="compare_variable",
        )
        city_a, city_b = st.columns(2)
        cities = list(CITIES.keys())
        a = city_a.selectbox("जगह A" if is_hi else "Location A", cities, index=cities.index("Delhi"))
        b = city_b.selectbox("जगह B" if is_hi else "Location B", cities, index=cities.index("Mumbai"))
        current_end = datetime.now().year - 1
        start_year = st.slider(
            "शुरुआती साल" if is_hi else "Start year",
            min_value=1981,
            max_value=current_end - 7,
            value=max(2004, current_end - 21),
            key="compare_start",
        )
        submitted = st.form_submit_button(
            "ट्रेंड की तुलना करें" if is_hi else "Compare trends",
            width="stretch",
        )

    if submitted:
        st.session_state.pop("compare_results", None)
        if a == b:
            st.error("कृपया दो अलग-अलग जगह चुनें।" if is_hi else "Choose two different locations.")
        else:
            results = []
            with st.spinner("दोनों जगहों का डेटा जांचा जा रहा है..." if is_hi else "Fetching both location series..."):
                for city in [a, b]:
                    coords = CITIES[city]
                    try:
                        res = load_and_analyze(
                            city,
                            coords["latitude"],
                            coords["longitude"],
                            variable,
                            start_year,
                            current_end,
                        )
                    except Exception as exc:
                        st.error(f"{city}: {exc}")
                        results = []
                        break
                    results.append((res, city, coords["latitude"], coords["longitude"]))

            if len(results) == 2:
                p_adj = benjamini_hochberg(
                    [results[0][0]["p_value"], results[1][0]["p_value"]]
                )
                st.session_state.compare_results = (results, p_adj)

    if "compare_results" in st.session_state:
        results, adjusted = st.session_state.compare_results
        col_a, col_b = st.columns(2)
        for col, item, q_value in zip([col_a, col_b], results, adjusted):
            with col:
                render_result(
                    *item,
                    language=st.session_state.language,
                    adjusted_p=q_value,
                )


def render_about():
    is_hi = st.session_state.language == LANG_HINDI
    st.markdown(
        "<div class='eyebrow'>पर्दे के पीछे</div>"
        if is_hi
        else "<div class='eyebrow'>BEHIND THE PULSE</div>",
        unsafe_allow_html=True,
    )
    st.title("EARTH PULSE कैसे काम करता है" if is_hi else "How EARTH PULSE works")

    steps = (
        [
            ("1 · डेटा लें", "चुनी हुई जगह और मान के लिए NASA POWER से मासिक डेटा मांगा जाता है।"),
            ("2 · डेटा जांचें", "खाली या अमान्य मान हटाए जाते हैं और डेटा की पूर्णता निकाली जाती है।"),
            ("3 · मौसम का दोहराव कम करें", "मासिक मानों को सालाना मानों में बदला जाता है ताकि मौसम का नियमित चक्र लंबे ट्रेंड पर हावी न हो।"),
            ("4 · ट्रेंड जांचें", "Mann–Kendall जांच और Sen's slope से बदलाव की दिशा और दर का अनुमान लगाया जाता है।"),
            ("5 · नतीजा समझाएं", "नतीजे के साथ अनिश्चितता, डेटा की पूर्णता और सीमाएं दिखाई जाती हैं।"),
        ]
        if is_hi
        else [
            ("1 · Fetch", "NASA POWER monthly data is requested for the selected coordinates and variable."),
            ("2 · Check", "Missing or invalid values are excluded and data completeness is calculated."),
            ("3 · Reduce seasonality", "Monthly values are aggregated into annual values to reduce the repeating seasonal cycle."),
            ("4 · Test", "The modified Mann–Kendall test and Sen's slope estimate trend evidence and rate."),
            ("5 · Explain", "The result is shown with uncertainty, data completeness and limitations."),
        ]
    )

    for heading, description in steps:
        st.markdown(
            f"<div class='panel'><h3>{heading}</h3><p class='muted'>{description}</p></div>",
            unsafe_allow_html=True,
        )
        st.write("")

    st.warning(
        "यह MVP सालाना aggregation का उपयोग करता है। ट्रेंड जांच कारण साबित नहीं करती।"
        if is_hi
        else "Important: this MVP uses annual aggregation. A trend test does not prove causation."
    )
    st.markdown(
        "**Data source:** [NASA POWER Monthly API](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/)"
    )


def navigate_back() -> None:
    history = st.session_state.page_history
    previous = history.pop() if history else st.session_state.previous_page
    if previous not in PAGES or previous == st.session_state.page:
        previous = PAGE_HOME
    st.session_state.page = previous
    st.session_state.previous_page = history[-1] if history else None
    st.session_state.sidebar_navigation = TEXT[st.session_state.language][PAGE_TEXT_KEYS[previous]]
    st.query_params["page"] = previous


def render_back_button():
    st.button(
        t["back"],
        key="back_nav",
        type="secondary",
        on_click=navigate_back,
    )


# -------------------------------------------------------------------
# MAIN ROUTER
# -------------------------------------------------------------------
if st.session_state.page != PAGE_HOME:
    render_back_button()

if st.session_state.page == PAGE_HOME:
    render_home()
elif st.session_state.page == PAGE_INVESTIGATE:
    render_investigate()
elif st.session_state.page == PAGE_COMPARE:
    render_compare()
elif st.session_state.page == PAGE_DEMO:
    render_demo()
else:
    render_about()