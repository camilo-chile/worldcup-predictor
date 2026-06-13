import streamlit as st
import pandas as pd
import requests
import json
import os
import zoneinfo
import email.utils
from datetime import datetime

# Set page config - Collapsed sidebar state to hide it completely
st.set_page_config(
    page_title="World Cup 2026 Predictor",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Dark Mode and Premium Glassmorphic Styling Override
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main Gradient Header */
    .gradient-header {
        background: linear-gradient(90deg, #10B981 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3rem;
        letter-spacing: -0.03em;
        margin-bottom: 0.2rem;
    }
    
    /* Metrics Card Styling */
    div[data-testid="metric-container"] {
        background: rgba(17, 24, 39, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 18px 24px;
        box-shadow: 0 4px 25px rgba(0, 0, 0, 0.25);
        transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
    }
    
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        border-color: rgba(16, 185, 129, 0.3);
        box-shadow: 0 8px 30px rgba(16, 185, 129, 0.15);
    }
    
    [data-testid="stMetricValue"] {
        font-size: 2.3rem;
        font-weight: 700;
        color: #10B981 !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #9CA3AF !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.12em;
    }
    
    /* GitHub repository button styling */
    .github-btn {
        background-color: #24292e;
        color: #ffffff !important;
        padding: 10px 18px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.95rem;
        border: 1px solid #444;
        display: inline-flex;
        align-items: center;
        text-decoration: none !important;
        transition: background-color 0.2s ease, border-color 0.2s ease;
    }
    .github-btn:hover {
        background-color: #2f363d;
        border-color: #555;
    }
    
    /* Center aligning footer credits */
    .footer-credits {
        text-align: center;
        padding: 40px 0 20px 0;
        color: #6B7280;
        font-size: 0.95rem;
        border-top: 1px solid rgba(255, 255, 255, 0.05);
        margin-top: 60px;
    }
</style>
""", unsafe_allow_html=True)

# Constants
DEFAULT_URL = "https://raw.githubusercontent.com/camilo-chile/worldcup-predictor/main/predictor/results.json"
LOCAL_FILE = "predictor/results.json"

@st.cache_data(ttl=60)
def load_predictions(url):
    """
    Fetch predictions from the raw GitHub URL. Falls back to local results.json file.
    Returns: (data, source_name)
    """
    source = "Unknown"
    data = None
    
    # Try raw GitHub URL if it is configured
    if "YOUR_USERNAME" not in url and url.startswith("http"):
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                source = "GitHub Repository"
        except Exception:
            pass
            
    # Fallback to local file if GitHub fetch was not attempted or failed
    if data is None:
        if os.path.exists(LOCAL_FILE):
            try:
                with open(LOCAL_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                source = "Local System Cache"
            except Exception as e:
                return None, f"Error reading local file: {e}"
        else:
            return None, "No data found. Please run 'predictor/main.py' or check GitHub Raw URL."
            
    return data, source

@st.cache_data(ttl=60)
def load_metadata(url):
    """
    Load metadata.json (last updated time) from GitHub or local cache.
    """
    metadata_url = url.replace("results.json", "metadata.json")
    local_metadata = LOCAL_FILE.replace("results.json", "metadata.json")
    
    # Try fetching from URL first
    if "YOUR_USERNAME" not in metadata_url and metadata_url.startswith("http"):
        try:
            res = requests.get(metadata_url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                return data.get("last_updated")
        except Exception:
            pass
            
    # Fallback to local file
    if os.path.exists(local_metadata):
        try:
            with open(local_metadata, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_updated")
        except Exception:
            pass
            
    return None

# ==========================================
# MAIN DASHBOARD LAYOUT
# ==========================================

# Header section with clean columns
col_title, col_link = st.columns([3, 1])
with col_title:
    st.markdown('<div class="gradient-header">🏆 World Cup 2026 Predictor</div>', unsafe_allow_html=True)
    st.markdown("##### Optimizing tournament predictions using market odds, Dixon-Coles goal modeling, and expected points search.")
with col_link:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="text-align: right;">
            <a class="github-btn" href="https://github.com/camilo-chile/worldcup-predictor" target="_blank">
                <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" style="margin-right: 8px; display: inline-block; vertical-align: text-bottom;"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.35 2.69.91 0 .67.01 1.3.01 1.48 0 .21-.15.47-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8z"></path></svg>
                View Repository
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("---")

# Load predictions using session state or default URL
github_url = st.session_state.get("github_url", DEFAULT_URL)
data, data_source = load_predictions(github_url)

# Load metadata timestamp
last_updated_raw = load_metadata(github_url)
if last_updated_raw:
    try:
        dt = datetime.fromisoformat(last_updated_raw)
        dt_est = dt.astimezone(zoneinfo.ZoneInfo("America/Toronto"))
        last_updated = dt_est.strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        last_updated = "Unknown"
else:
    last_updated = "Unknown"

if data is None:
    st.error("❌ Data status: NOT LOADED")
    st.info(data_source)
else:
    # Top Status Banner showing Last Run time in EST
    st.markdown(
        f"""
        <div style="background-color: rgba(59, 130, 246, 0.1); border-left: 4px solid #3B82F6; padding: 14px 20px; border-radius: 8px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="color: #9CA3AF; font-size: 0.95rem;">Last Model Update (EST/EDT):</span>
                <strong style="color: #3B82F6; font-size: 1.1rem; margin-left: 8px;">{last_updated}</strong>
            </div>
            <span style="color: #6B7280; font-size: 0.85rem; font-style: italic;">Source: {data_source}</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Convert data list to DataFrame
    df = pd.DataFrame(data)
    
    # Calculate Summary Metrics
    total_matches = len(df)
    total_exp_pts = int(round(df["expected_points"].sum()))
    avg_exp_pts = df["expected_points"].mean()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Remaining Matches", f"{total_matches}")
    col2.metric("Total Expected Points", f"{total_exp_pts}", help="Sum of expected points across all remaining matches")
    col3.metric("Avg Expected Points per Match", f"{avg_exp_pts:.3f} pts", help="Average expected points per match")
    
    st.markdown("### 📋 Active Predictions")
    
    # Format columns for presentation (Convert UTC to America/Toronto which matches Santiago de Chile time in June)
    times = pd.to_datetime(df["commence_time"])
    if times.dt.tz is None:
        times = times.dt.tz_localize("UTC")
        
    presentation_df = pd.DataFrame()
    presentation_df["Kickoff (EST/EDT)"] = times.dt.tz_convert("America/Toronto").dt.strftime("%Y-%m-%d %H:%M %Z")
    presentation_df["Home Team"] = df["home_team"]
    presentation_df["Away Team"] = df["away_team"]
    presentation_df["Pred Score (Optimized)"] = df.apply(lambda r: f"{r['predicted_home_goals']} - {r['predicted_away_goals']}", axis=1)
    
    # Add most likely score if columns exist in data
    if "most_likely_home_goals" in df.columns:
        presentation_df["Most Likely Score"] = df.apply(lambda r: f"{r['most_likely_home_goals']} - {r['most_likely_away_goals']} ({round(r['most_likely_prob']*100, 1)}%)", axis=1)
    else:
        presentation_df["Most Likely Score"] = "N/A"
        
    presentation_df["E[Points]"] = df["expected_points"].round(0).astype(int).astype(str) + " pts"
    presentation_df["Home Prob (de-vig)"] = (df["de_vigged_home_prob"] * 100).round(1).astype(str) + "%"
    presentation_df["Draw Prob (de-vig)"] = (df["de_vigged_draw_prob"] * 100).round(1).astype(str) + "%"
    presentation_df["Away Prob (de-vig)"] = (df["de_vigged_away_prob"] * 100).round(1).astype(str) + "%"
    
    # Display styled predictions dataframe
    st.dataframe(
        presentation_df,
        use_container_width=True,
        hide_index=True
    )

st.markdown("<br>", unsafe_allow_html=True)

# Collapsible Settings (Placed between the table and the documentation)
with st.expander("⚙️ Configuration Settings", expanded=False):
    st.markdown("### Dashboard Config")
    new_url = st.text_input(
        "GitHub Raw URL for results.json",
        value=github_url,
        help="Input a custom raw results.json URL if you have forked or modified this repository."
    )
    if new_url != github_url:
        st.session_state["github_url"] = new_url
        st.rerun()

# Expander: Structured LaTeX Math Documentation & Methodology
with st.expander("📘 Model Documentation & Mathematical Methodology", expanded=False):
    st.markdown("""
    ### Model Methodology Overview
    This project implements a highly sophisticated, premium-grade predictive system to forecast scorelines for the remaining matches of the FIFA World Cup 2026. The model utilizes real-time market consensus data, mathematical bookmaker margin elimination (De-Vigging), tactical goal expectancy modeling (Dixon-Coles), and a Bayesian decision-theoretic optimizer to maximize tournament bracket points.
    
    The prediction pipeline consists of six key statistical stages:
    """)
    
    st.markdown("#### 1. Market Odds Extraction")
    st.write("The system fetches decimal head-to-head (1X2) odds from **The Odds API**. Financial betting markets serve as highly efficient aggregators of real-time variables (team form, injury updates, climate, and tactical shifts).")
    
    st.markdown("#### 2. Market Margin Removal (De-Vigging) via Shin's Method")
    st.write("Bookmakers price outcomes with a profit commission margin (*overround*), meaning the implied probabilities sum to $> 1.0$. Rather than using simple multiplicative normalization, this model employs **Shin's Method (1993)**, which solves for the proportion of informed trading $z$ and the true probabilities $p_{Home}$, $p_{Draw}$, and $p_{Away}$ such that their sum equals exactly $1.0$:")
    st.latex(r"\pi_i = (1-z)p_i + z\sqrt{p_i}")
    
    st.markdown("#### 3. Goal Expectancy Parameter Inversion")
    st.write("Using the clean probabilities, the system solves for the underlying goal expectancy parameters—$\\lambda_H$ (Home Expected Goals) and $\\lambda_A$ (Away Expected Goals). This step translates win/draw/loss probabilities into raw offensive and defensive performance intensities.")
    
    st.markdown("#### 4. Base Independent Poisson Distribution")
    st.write("As a baseline, the number of goals scored by the Home team ($X$) and Away team ($Y$) are modeled as independent Poisson random variables:")
    st.latex(r"P(X = x) = \frac{\lambda_H^x e^{-\lambda_H}}{x!}, \quad P(Y = y) = \frac{\lambda_A^y e^{-\lambda_A}}{y!}")
    st.write("The joint probability of a specific scoreline $(x, y)$ is calculated as the product of their individual probabilities: $P(X=x, Y=y) = P(X=x) \times P(Y=y)$.")
    
    st.markdown("#### 5. Dixon-Coles Low-Scoring Correlation Calibration")
    st.write("In real-world football, goal outcomes are not completely independent. There is a statistically significant correlation that produces more low-scoring draws (0-0, 1-1) than predicted by independent Poisson distributions. To correct for this, we apply the **Dixon and Coles Model (1997)** with an international tournament adjustment factor $\\rho = -0.13$:")
    st.latex(r"P_{DC}(X=x, Y=y) = \tau(x, y) \times P(X=x) \times P(Y=y)")
    st.write("Where the scaling factor $\\tau(x, y)$ adjusts the low scorelines (0-0, 1-0, 0-1, 1-1) dynamically based on the expected goals $\\lambda_H$ and $\\lambda_A$ and the dependency parameter $\\rho$:")
    st.latex(r"\tau(x,y) = \begin{cases} 1 - \lambda_H \lambda_A \rho & \text{if } (x,y) = (0,0) \\ 1 + \lambda_A \rho & \text{if } (x,y) = (1,0) \\ 1 + \lambda_H \rho & \text{if } (x,y) = (0,1) \\ 1 - \rho & \text{if } (x,y) = (1,1) \\ 1 & \text{otherwise} \end{cases}")
    
    st.markdown("#### 6. Bayesian Expected Points Grid Search")
    st.write("Predicting the single most likely scoreline is mathematically suboptimal for tournament brackets. Your prediction strategy must align with the point structure of your competition:")
    st.markdown("""
    *   **Correct Match Outcome (Winner/Draw) (1X2)**: **5 points**
    *   **Correct Home Goals**: **2 points**
    *   **Correct Away Goals**: **2 points**
    *   **Correct Goal Difference**: **1 point**
    """)
    st.write("The expected points $\\mathbb{E}[\\text{Points}]$ for any score prediction $P_{pred} = (p_h, p_a)$ given joint probability matrix $P_{DC}$ is:")
    st.latex(r"\mathbb{E}[\text{Points}(p_h, p_a)] = \sum_{a_h=0}^{5} \sum_{a_a=0}^{5} P_{DC}(a_h, a_a) \times S\Big((p_h, p_a), (a_h, a_a)\Big)")
    st.write(r"The system executes a discrete grid search over all $(p_h, p_a) \in \{0, 1, 2, 3, 4, 5\}^2$ and selects the prediction that **maximizes this expected value**.")

# Footer credits
st.markdown(
    """
    <div class="footer-credits">
        Made with ❤️ by <b>Camilo Yañez</b>
    </div>
    """,
    unsafe_allow_html=True
)
