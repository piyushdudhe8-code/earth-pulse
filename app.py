from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from earth_pulse.analysis import analyze_series, benjamini_hochberg, build_verdict
from earth_pulse.data import CITIES, VARIABLES, fetch_nasa_monthly, make_demo_series
from earth_pulse.globe import render_earth_globe
from earth_pulse.report import make_report


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
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        border-color: #d5f7e4;
        background: #c0f2d7;
        color: #081b14;
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

LANG_ENGLISH = "English"
LANG_HINDI = "हिन्दी"

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
        "back_home": "← Back to Home",
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
        "back_home": "← होम पर वापस जाएं",
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
    st.session_state.page = PAGE_HOME
if "language" not in st.session_state:
    st.session_state.language = LANG_ENGLISH
if "last_result" not in st.session_state:
    st.session_state.last_result = None

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

    page_options = [PAGE_HOME, PAGE_INVESTIGATE, PAGE_COMPARE, PAGE_DEMO, PAGE_ABOUT]
    page_keys = ["home", "investigate", "compare", "demo", "about"]
    page_labels = [t[key] for key in page_keys]
    current_index = page_options.index(st.session_state.page) if st.session_state.page in page_options else 0
    selected_label = st.radio(
        "Navigate",
        page_labels,
        index=current_index,
        label_visibility="collapsed",
    )
    st.session_state.page = page_options[page_labels.index(selected_label)]

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


# -------------------------------------------------------------------
# DATA HELPERS
# -------------------------------------------------------------------
@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_nasa_fetch(latitude: float, longitude: float, variable: str, start_year: int, end_year: int):
    return fetch_nasa_monthly(latitude, longitude, variable, start_year, end_year)


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
            source = "NASA POWER live API"
        except Exception as exc:
            raise RuntimeError(
                f"NASA POWER request failed ({type(exc).__name__}: {exc}). "
                "Open Demo lab to view clearly labelled synthetic data."
            ) from exc

    return analyze_series(frame, variable, source=source)


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
    verdict_result = result if adjusted_p is None else {
        **result,
        "significant": adjusted_p < 0.05,
    }
    verdict = build_verdict(verdict_result, language)
    is_demo = "DEMO DATA" in result["source"]

    st.markdown(
        "<div class='eyebrow'>जांच का परिणाम</div>"
        if language == LANG_HINDI
        else "<div class='eyebrow'>INVESTIGATION RESULT</div>",
        unsafe_allow_html=True,
    )
    st.subheader(f"{city} · {result['variable']}")

    if is_demo:
        st.warning(
            "डेमो डेटा — ये केवल उदाहरण के लिए बनाए गए मान हैं, NASA के वास्तविक अवलोकन नहीं।"
            if language == LANG_HINDI
            else "DEMO DATA — synthetic values for demonstration only. Do not cite as NASA observations."
        )
    else:
        st.success(
            "NASA POWER से लाइव डेटा मिला। यह ग्रिड-आधारित डेटा है, किसी सड़क-स्तर के मौसम स्टेशन की रीडिंग नहीं।"
            if language == LANG_HINDI
            else "Live data received from NASA POWER. This is gridded data, not a street-level station reading."
        )

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
        if st.button(f"🔎  {t['start']}", width="stretch", type="primary"):
            st.session_state.page = PAGE_INVESTIGATE
            st.rerun()
    with demo_col:
        if st.button(f"🧭  {t['watch']}", width="stretch"):
            st.session_state.page = PAGE_DEMO
            st.rerun()

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


def render_investigate():
    is_hi = st.session_state.language == LANG_HINDI

    st.markdown(
        f"<div class='eyebrow'>{t['globe']}</div>",
        unsafe_allow_html=True,
    )
    st.title("पृथ्वी को देखें" if is_hi else "Explore the living planet")
    st.caption(t["globe_help"])

    # The interactive 3D Earth is intentionally placed INSIDE Investigate.
    render_earth_globe(height=500)

    st.divider()
    st.markdown(
        "<div class='eyebrow'>01 · संकेत चुनें</div>"
        if is_hi
        else "<div class='eyebrow'>01 · CHOOSE A SIGNAL</div>",
        unsafe_allow_html=True,
    )
    st.title(t["what"])

    variable_names = list(VARIABLES.keys())
    if not variable_names:
        st.error("No variables are configured in earth_pulse.data.VARIABLES.")
        return

    # Keep the actual data-layer key as the selected value.
    variable = st.selectbox(t["variable"], variable_names, index=0)
    desc_key = "description_hi" if is_hi else "description"
    description = VARIABLES[variable].get(desc_key) or VARIABLES[variable].get("description")
    if description:
        st.caption(description)

    st.markdown(
        "<div class='eyebrow'>02 · जगह और समय चुनें</div>"
        if is_hi
        else "<div class='eyebrow'>02 · CHOOSE A PLACE AND PERIOD</div>",
        unsafe_allow_html=True,
    )

    with st.form("investigation_form"):
        city = st.selectbox(t["city"], list(CITIES.keys()), index=list(CITIES).index("Delhi"))
        use_custom = st.checkbox(t["custom"])
        loc1, loc2 = st.columns(2)
        lat = loc1.number_input(
            t["latitude"],
            min_value=-90.0,
            max_value=90.0,
            value=float(CITIES[city]["latitude"]),
            format="%.4f",
            disabled=not use_custom,
        )
        lon = loc2.number_input(
            t["longitude"],
            min_value=-180.0,
            max_value=180.0,
            value=float(CITIES[city]["longitude"]),
            format="%.4f",
            disabled=not use_custom,
        )

        current_end = datetime.now().year - 1
        default_start = max(2004, current_end - 21)
        start_year = st.slider(
            t["start_year"],
            min_value=1981,
            max_value=current_end - 7,
            value=default_start,
        )
        st.caption(
            f"Data request: {start_year}–{current_end}. "
            + (
                "उपलब्धता NASA POWER के संग्रह पर निर्भर करती है।"
                if is_hi
                else "Actual availability depends on the NASA POWER archive."
            )
        )
        submitted = st.form_submit_button(t["analyze"], width="stretch")

    if submitted:
        st.session_state.last_result = None
        latitude, longitude = get_location(city, use_custom, lat, lon)
        report_location = (
            f"Custom point ({latitude:.4f}, {longitude:.4f})" if use_custom else city
        )
        with st.spinner(
            "NASA POWER से डेटा लिया जा रहा है और ट्रेंड जांचा जा रहा है..."
            if is_hi
            else "Fetching NASA POWER data and testing the trend..."
        ):
            try:
                result = load_and_analyze(
                    report_location,
                    latitude,
                    longitude,
                    variable,
                    start_year,
                    current_end,
                )
                st.session_state.last_result = {
                    "result": result,
                    "city": report_location,
                    "latitude": latitude,
                    "longitude": longitude,
                    "language": st.session_state.language,
                }
            except Exception as exc:
                st.error(str(exc))
                st.info(
                    "आप Demo lab में उदाहरण डेटा देख सकते हैं।"
                    if is_hi
                    else "You can open Demo lab to explore the workflow with synthetic data."
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


def render_demo():
    is_hi = st.session_state.language == LANG_HINDI
    st.markdown(
        "<div class='eyebrow'>निर्देशित उदाहरण</div>"
        if is_hi
        else "<div class='eyebrow'>GUIDED INVESTIGATIONS</div>",
        unsafe_allow_html=True,
    )
    st.title(t["demo"])
    st.write(
        "ये उदाहरण के लिए बनाए गए synthetic data हैं, NASA के वास्तविक अवलोकन नहीं।"
        if is_hi
        else "These ready-made investigations use synthetic training data, not NASA observations."
    )

    d1, d2 = st.columns(2)
    with d1:
        st.markdown(
            "<div class='panel'><div class='eyebrow'>DEMO 01 · TEMPERATURE</div><h3>Delhi temperature</h3><p class='muted'>Illustrative warming signal with a seasonal cycle.</p></div>",
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
            "<div class='panel'><div class='eyebrow'>DEMO 02 · RAINFALL</div><h3>Mumbai rainfall</h3><p class='muted'>Illustrative monsoon-shaped rainfall pattern.</p></div>",
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
        variable = st.selectbox(
            "पर्यावरणीय मान" if is_hi else "Earth system variable",
            list(VARIABLES.keys()),
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


def render_back_button():
    label = t["back_home"]
    if st.button(label, key=f"back_home_{st.session_state.page}", type="secondary"):
        st.session_state.page = PAGE_HOME
        st.rerun()


# -------------------------------------------------------------------
# MAIN ROUTER
# -------------------------------------------------------------------
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

if st.session_state.page != PAGE_HOME:
    render_back_button()