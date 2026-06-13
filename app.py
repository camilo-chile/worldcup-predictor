import streamlit as st
import pandas as pd
import requests
import json
import os

# Set page config
st.set_page_config(
    page_title="World Cup Predictor Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Mode and Premium Styling Override
st.markdown("""
<style>
    /* Styling metrics card */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #10B981;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #9CA3AF;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)

# Default URLs and Constants
DEFAULT_URL = "https://raw.githubusercontent.com/camilo-chile/worldcup-predictor/main/predictor/results.json"
LOCAL_FILE = "predictor/results.json"

@st.cache_data(ttl=60)
def load_predictions(url):
    """
    Fetch predictions from the raw GitHub URL. Falls back to local results.json file
    if raw URL contains placeholders, fetch fails, or is unavailable.
    """
    source = "Unknown"
    data = None
    
    # Try raw GitHub URL if it is configured (i.e. does not contain default placeholders)
    if "YOUR_USERNAME" not in url and url.startswith("http"):
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                source = "GitHub Raw URL"
        except Exception as e:
            st.sidebar.warning(f"Failed to fetch from GitHub: {e}")
            
    # Fallback to local file if GitHub fetch was not attempted or failed
    if data is None:
        if os.path.exists(LOCAL_FILE):
            try:
                with open(LOCAL_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                source = f"Local File System ({LOCAL_FILE})"
            except Exception as e:
                return None, f"Error reading local file: {e}"
        else:
            return None, f"No data found. Please run 'main.py' or check GitHub Raw URL."
            
    return data, source

# Sidebar Layout
st.sidebar.title("⚽ Configuration")
st.sidebar.markdown("---")

github_url = st.sidebar.text_input(
    "GitHub Raw URL for results.json",
    value=DEFAULT_URL,
    help="Enter the raw GitHub URL for your results.json file to fetch live predictions."
)

st.sidebar.markdown("### Data Status")
data, data_source = load_predictions(github_url)

if data is None:
    st.sidebar.error("❌ Data status: NOT LOADED")
    st.sidebar.caption(data_source) # Displays error message
else:
    st.sidebar.success("✅ Data status: LOADED")
    st.sidebar.caption(f"Source: **{data_source}**")

st.sidebar.markdown("---")
st.sidebar.markdown("""
### Model Methodology
1. **Odds API**: Live market odds are aggregated from global bookmakers.
2. **De-vigging**: **Shin's method** is applied to remove the bookmakers' overround.
3. **Dixon-Coles Model**: Match goal expectations ($\lambda_H$, $\lambda_A$) are calculated with a default international $\rho = -0.13$.
4. **Optimization**: A 6x6 joint probability grid search selects the prediction maximizing expected points ($E[\text{Points}]$).
""")

# Main Content Layout
st.title("⚽ World Cup Score Predictor")
st.markdown("##### Optimizing tournament bracket predictions using market consensus odds and probability modeling.")
st.markdown("---")

if data is not None and len(data) > 0:
    # Convert data to DataFrame
    df = pd.DataFrame(data)
    
    # Calculate Summary Metrics
    total_matches = len(df)
    max_exp_pts = df["expected_points"].max()
    avg_exp_pts = df["expected_points"].mean()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Matches Predicted", f"{total_matches}")
    col2.metric("Max Expected Points", f"{max_exp_pts:.3f} pts", help="The match with the highest confidence prediction")
    col3.metric("Avg Expected Points", f"{avg_exp_pts:.3f} pts", help="Average expected points across all matches")
    
    st.markdown("### 📋 Match Predictions")
    
    # Format columns for presentation (Convert UTC to America/Toronto which matches Santiago de Chile time in June)
    times = pd.to_datetime(df["commence_time"])
    if times.dt.tz is None:
        times = times.dt.tz_localize("UTC")
    presentation_df = pd.DataFrame()
    presentation_df["Kickoff (Toronto/Santiago Time)"] = times.dt.tz_convert("America/Toronto").dt.strftime("%Y-%m-%d %H:%M")
    presentation_df["Home Team"] = df["home_team"]
    presentation_df["Away Team"] = df["away_team"]
    presentation_df["Pred Score"] = df.apply(lambda r: f"{r['predicted_home_goals']} - {r['predicted_away_goals']}", axis=1)
    presentation_df["E[Points]"] = df["expected_points"]
    presentation_df["Avg Home Odds"] = df["home_odds"]
    presentation_df["Avg Draw Odds"] = df["draw_odds"]
    presentation_df["Avg Away Odds"] = df["away_odds"]
    presentation_df["Home Prob (de-vig)"] = (df["de_vigged_home_prob"] * 100).round(1).astype(str) + "%"
    presentation_df["Draw Prob (de-vig)"] = (df["de_vigged_draw_prob"] * 100).round(1).astype(str) + "%"
    presentation_df["Away Prob (de-vig)"] = (df["de_vigged_away_prob"] * 100).round(1).astype(str) + "%"
    presentation_df["lambda_H"] = df["lambda_h"]
    presentation_df["lambda_A"] = df["lambda_a"]
    
    # Display styled dataframe
    st.dataframe(
        presentation_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Interactive Details Expander
    with st.expander("🔍 Expected Points Scoring Guide"):
        st.markdown("""
        The grid search optimization maximizes the expected points of your prediction using this tournament scoring system:
        *   **Correct Outcome (1X2)**: **5 points**
        *   **Correct Home Goals**: **2 points**
        *   **Correct Away Goals**: **2 points**
        *   **Correct Goal Difference**: **1 point**
        
        *Example*: If you predict **2 - 1** (Home Win):
        - If match ends **2 - 1**: You get 5 (outcome) + 2 (home goals) + 2 (away goals) + 1 (diff) = **10 points** (maximum).
        - If match ends **1 - 0**: You get 5 (outcome) + 0 (home goals) + 0 (away goals) + 1 (diff: 2-1=1 and 1-0=1) = **6 points**.
        - If match ends **1 - 1**: You get **0 points** (wrong outcome, home goals, away goals, and difference).
        """)
else:
    st.info("No prediction data has been generated yet. Please run 'main.py' to generate 'results.json'.")
