"""
World Cup Score Predictor
Fetches match odds, de-vigs using Shin's method, models using Dixon-Coles,
and optimizes score predictions using Expected Points grid search.
"""

import os
import json
import math
import datetime
import requests
import pandas as pd
import penaltyblog as pb
from dotenv import load_dotenv

load_dotenv()


# Configuration
API_KEY = os.getenv("THE_ODDS_API_KEY", "YOUR_API_KEY")
SPORT = "soccer_fifa_world_cup"
REGION = "eu,us,uk"
MARKET = "h2h,totals"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(SCRIPT_DIR, "results.json")

# Realistic Mock Data if API fails or lacks active matches
MOCK_ODDS_RESPONSE = [
    {
        "id": "mock_match_1",
        "sport_key": "soccer_fifa_world_cup",
        "commence_time": "2026-06-15T18:00:00Z",
        "home_team": "Mock Team A",
        "away_team": "Mock Team B",
        "bookmakers": [
            {
                "key": "mock_bookmaker_1",
                "title": "Mock Bookmaker 1",
                "last_update": "2026-06-11T12:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Mock Team A", "price": 2.10},
                            {"name": "Mock Team B", "price": 3.40},
                            {"name": "Draw", "price": 3.20}
                        ]
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.95, "point": 2.5},
                            {"name": "Under", "price": 1.85, "point": 2.5}
                        ]
                    }
                ]
            },
            {
                "key": "mock_bookmaker_2",
                "title": "Mock Bookmaker 2",
                "last_update": "2026-06-11T12:05:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Mock Team A", "price": 2.15},
                            {"name": "Mock Team B", "price": 3.30},
                            {"name": "Draw", "price": 3.25}
                        ]
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.90, "point": 2.5},
                            {"name": "Under", "price": 1.90, "point": 2.5}
                        ]
                    }
                ]
            }
        ]
    },
    {
        "id": "mock_match_2",
        "sport_key": "soccer_fifa_world_cup",
        "commence_time": "2026-06-16T20:00:00Z",
        "home_team": "Mock Team C",
        "away_team": "Mock Team D",
        "bookmakers": [
            {
                "key": "mock_bookmaker_1",
                "title": "Mock Bookmaker 1",
                "last_update": "2026-06-11T12:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Mock Team C", "price": 1.95},
                            {"name": "Mock Team D", "price": 3.80},
                            {"name": "Draw", "price": 3.30}
                        ]
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.80, "point": 2.5},
                            {"name": "Under", "price": 2.00, "point": 2.5}
                        ]
                    }
                ]
            }
        ]
    },
    {
        "id": "mock_match_3",
        "sport_key": "soccer_fifa_world_cup",
        "commence_time": "2026-06-17T15:00:00Z",
        "home_team": "Mock Team E",
        "away_team": "Mock Team F",
        "bookmakers": [
            {
                "key": "mock_bookmaker_1",
                "title": "Mock Bookmaker 1",
                "last_update": "2026-06-11T12:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Mock Team E", "price": 2.50},
                            {"name": "Mock Team F", "price": 2.90},
                            {"name": "Draw", "price": 3.10}
                        ]
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 2.10, "point": 2.5},
                            {"name": "Under", "price": 1.70, "point": 2.5}
                        ]
                    }
                ]
            }
        ]
    }
]

def fetch_odds():
    """
    Fetch match odds from The Odds API. Falls back to mock data if API key
    is placeholder, request fails, or returns no data.
    """
    if API_KEY == "YOUR_API_KEY" or not API_KEY:
        print("Using placeholder API key. Falling back to mock data.")
        return MOCK_ODDS_RESPONSE

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": REGION,
        "markets": MARKET,
        "oddsFormat": "decimal"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                print(f"Successfully fetched {len(data)} matches from The Odds API.")
                return data
            else:
                print("API returned empty matches. Falling back to mock data.")
                return MOCK_ODDS_RESPONSE
        else:
            print(f"API request failed with code {response.status_code}. Falling back to mock data.")
            print(f"Response: {response.text}")
            return MOCK_ODDS_RESPONSE
    except Exception as e:
        print(f"Exception during API fetch: {e}. Falling back to mock data.")
        return MOCK_ODDS_RESPONSE

def parse_match_odds(match):
    """
    Calculate average odds for home win, draw, away win, and totals (Over/Under).
    Group totals by their 'point' value and choose the line closest to 2.5.
    Returns:
        (home_odds, draw_odds, away_odds, over_odds, under_odds, totals_line) or None
    """
    home_team = match.get("home_team")
    away_team = match.get("away_team")
    if not home_team or not away_team:
        return None
    
    sum_home, sum_draw, sum_away = 0.0, 0.0, 0.0
    h2h_count = 0
    
    totals_data = {}
    
    # Filter and prioritize sharp bookmakers (pinnacle, betfair_ex)
    sharp_keys = {"pinnacle", "betfair_ex"}
    available_bookmakers = match.get("bookmakers", [])
    sharp_bookmakers = [b for b in available_bookmakers if b.get("key") in sharp_keys]
    target_bookmakers = sharp_bookmakers if sharp_bookmakers else available_bookmakers
    
    for bookmaker in target_bookmakers:
        for market in bookmaker.get("markets", []):
            market_key = market.get("key")
            
            if market_key == "h2h":
                outcomes = market.get("outcomes", [])
                odds_dict = {}
                for outcome in outcomes:
                    name = outcome.get("name")
                    price = outcome.get("price")
                    if name and price is not None:
                        odds_dict[name] = float(price)
                
                h_price = odds_dict.get(home_team)
                a_price = odds_dict.get(away_team)
                d_price = odds_dict.get("Draw")
                
                if h_price is not None and a_price is not None and d_price is not None:
                    sum_home += h_price
                    sum_away += a_price
                    sum_draw += d_price
                    h2h_count += 1
                    
            elif market_key == "totals":
                outcomes = market.get("outcomes", [])
                for outcome in outcomes:
                    name = outcome.get("name")
                    price = outcome.get("price")
                    point = outcome.get("point")
                    
                    if name and price is not None and point is not None:
                        point = float(point)
                        price = float(price)
                        
                        if abs(point - round(point)) == 0.5:
                            if point not in totals_data:
                                totals_data[point] = {"over": [], "under": []}
                            if name.lower() == "over":
                                totals_data[point]["over"].append(price)
                            elif name.lower() == "under":
                                totals_data[point]["under"].append(price)
                                
    h2h_odds = None
    if h2h_count > 0:
        h2h_odds = (sum_home / h2h_count, sum_draw / h2h_count, sum_away / h2h_count)
    else:
        return None
        
    totals_odds = (None, None, None)
    best_point = None
    min_diff = 999.0
    
    for point, data in totals_data.items():
        overs = data["over"]
        unders = data["under"]
        if overs and unders:
            diff = abs(point - 2.5)
            if diff < min_diff:
                min_diff = diff
                best_point = point
                
    if best_point is not None:
        avg_over = sum(totals_data[best_point]["over"]) / len(totals_data[best_point]["over"])
        avg_under = sum(totals_data[best_point]["under"]) / len(totals_data[best_point]["under"])
        totals_odds = (avg_over, avg_under, best_point)
        
    return h2h_odds[0], h2h_odds[1], h2h_odds[2], totals_odds[0], totals_odds[1], totals_odds[2]

def de_vig_odds(home_odds, draw_odds, away_odds):
    """
    De-vig odds using Shin's method via penaltyblog.
    Falls back to multiplicative de-vigging if solver fails.
    """
    odds = [home_odds, draw_odds, away_odds]
    try:
        result = pb.implied.calculate_implied(odds, method="shin")
        return result.probabilities
    except Exception as e:
        print(f"Shin de-vigging failed for {odds}: {e}. Falling back to multiplicative.")
        implied = [1.0 / o if (o and o > 0) else 0.0 for o in odds]
        total = sum(implied)
        if total > 0:
            return [p / total for p in implied]
        return [0.3333, 0.3333, 0.3333]

def de_vig_totals(over_price, under_price):
    """
    De-vig Over/Under odds using standard multiplicative de-vigging.
    """
    implied_over = 1.0 / over_price if (over_price and over_price > 0) else 0.0
    implied_under = 1.0 / under_price if (under_price and under_price > 0) else 0.0
    sum_implied = implied_over + implied_under
    if sum_implied > 0:
        return implied_over / sum_implied, implied_under / sum_implied
    return 0.5, 0.5

def poisson_pmf(k, mu):
    """Calculate Poisson Probability Mass Function."""
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    return (mu ** k) * math.exp(-mu) / math.factorial(k)

def poisson_cdf(k, mu):
    """Calculate Poisson Cumulative Distribution Function."""
    return sum(poisson_pmf(i, mu) for i in range(k + 1))

def solve_lambda_total(under_prob, line):
    """
    Solve for lambda_total such that Poisson CDF at floor(line) matches under_prob.
    Uses binary search.
    """
    k = math.floor(line)
    low, high = 0.001, 20.0
    for _ in range(30):
        mid = (low + high) / 2
        prob = poisson_cdf(k, mid)
        if prob > under_prob:
            low = mid
        else:
            high = mid
    return (low + high) / 2

def get_dynamic_rho(lambda_h, lambda_a):
    """
    Calibrate Dixon-Coles rho dynamically based on goal expectancies.
    Decays correlation for high-scoring games and guarantees mathematical validity
    (non-negative probabilities) by enforcing the Dixon-Coles parameter bounds.
    """
    if lambda_h <= 0 or lambda_a <= 0:
        return 0.0
        
    lambda_total = lambda_h + lambda_a
    # Base rho of -0.13, decaying as total expected goals increase
    rho_target = -0.13 * math.exp(-0.2 * (lambda_total - 2.5))
    
    # Enforce Dixon-Coles mathematical bounds to prevent negative probabilities:
    # rho must be >= -1/lambda_h and >= -1/lambda_a
    lower_bound = -0.95 * min(1.0 / lambda_h, 1.0 / lambda_a)
    
    # Clamp to [lower_bound, 0.0]
    rho = max(rho_target, lower_bound)
    return min(0.0, rho)

def get_dixon_coles_probs(lambda_h, lambda_a, rho=None):
    """
    Calculate Home/Draw/Away win probabilities using Dixon-Coles adjustments.
    Uses a 12x12 matrix to cover almost all probability mass.
    """
    if rho is None:
        rho = get_dynamic_rho(lambda_h, lambda_a)
        
    max_g = 12
    matrix = [[0.0] * max_g for _ in range(max_g)]
    
    h_probs = [poisson_pmf(i, lambda_h) for i in range(max_g)]
    a_probs = [poisson_pmf(i, lambda_a) for i in range(max_g)]
    
    for h in range(max_g):
        for a in range(max_g):
            matrix[h][a] = h_probs[h] * a_probs[a]
            
    if lambda_h > 0 and lambda_a > 0:
        tau_00 = max(0.0, 1 - lambda_h * lambda_a * rho)
        tau_10 = max(0.0, 1 + lambda_a * rho)
        tau_01 = max(0.0, 1 + lambda_h * rho)
        tau_11 = max(0.0, 1 - rho)
        
        matrix[0][0] *= tau_00
        matrix[1][0] *= tau_10
        matrix[0][1] *= tau_01
        matrix[1][1] *= tau_11
        
    total = sum(sum(row) for row in matrix)
    if total > 0:
        for h in range(max_g):
            for a in range(max_g):
                matrix[h][a] /= total
                
    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    for h in range(max_g):
        for a in range(max_g):
            prob = matrix[h][a]
            if h > a:
                p_home += prob
            elif h < a:
                p_away += prob
            else:
                p_draw += prob
                
    return p_home, p_draw, p_away

def solve_ratio(lambda_total, home_prob, draw_prob, away_prob):
    """
    Solve for ratio r = lambda_H / lambda_total using coarse-to-fine search
    to match H2H de-vigged probabilities.
    """
    best_r = 0.5
    min_error = 1e9
    
    for i in range(1, 100):
        r = i / 100.0
        lh = r * lambda_total
        la = (1.0 - r) * lambda_total
        ph, pd, pa = get_dixon_coles_probs(lh, la)
        error = (ph - home_prob)**2 + (pd - draw_prob)**2 + (pa - away_prob)**2
        if error < min_error:
            min_error = error
            best_r = r
            
    r_start = max(0.001, best_r - 0.01)
    r_end = min(0.999, best_r + 0.01)
    for i in range(200):
        r = r_start + (r_end - r_start) * (i / 200.0)
        lh = r * lambda_total
        la = (1.0 - r) * lambda_total
        ph, pd, pa = get_dixon_coles_probs(lh, la)
        error = (ph - home_prob)**2 + (pd - draw_prob)**2 + (pa - away_prob)**2
        if error < min_error:
            min_error = error
            best_r = r
            
    return best_r

def calculate_lambdas(home_prob, draw_prob, away_prob, over_prob=None, under_prob=None, totals_line=None):
    """
    Infer goal expectancies (lambda_H, lambda_A) from de-vigged H2H and Over/Under probabilities.
    If totals odds are available, solves for lambda_total from totals, and then
    solves for the ratio r using H2H probabilities.
    If totals are not available, falls back to Dixon-Coles goal expectancy from H2H.
    """
    if over_prob is not None and under_prob is not None and totals_line is not None:
        try:
            lambda_total = solve_lambda_total(under_prob, totals_line)
            r = solve_ratio(lambda_total, home_prob, draw_prob, away_prob)
            lambda_h = r * lambda_total
            lambda_a = (1.0 - r) * lambda_total
            return lambda_h, lambda_a
        except Exception as e:
            print(f"Error solving lambdas using H2H + Totals: {e}. Falling back to H2H only.")
            
    try:
        res = pb.models.goal_expectancy(
            home=home_prob,
            draw=draw_prob,
            away=away_prob,
            dc_adj=True,
            rho=-0.13
        )
        if res.get("success"):
            return res["home_exp"], res["away_exp"]
        else:
            print(f"Dixon-Coles goal expectancy solver failed: {res.get('error')}")
    except Exception as e:
        print(f"Error calculating goal expectancy lambdas: {e}")
        
    if home_prob > 0 and away_prob > 0:
        # Non-linear heuristic mapping win probability ratio to lambda ratio
        ratio = (home_prob / away_prob) ** 0.6
        lambda_a = 2.6 / (ratio + 1.0)
        lambda_h = 2.6 - lambda_a
        return float(lambda_h), float(lambda_a)
        
    total_prob = home_prob + away_prob
    if total_prob > 0:
        ratio = home_prob / total_prob
        return float(ratio * 2.6), float((1.0 - ratio) * 2.6)
    return 1.4, 1.2


def build_probability_grid(lambda_h, lambda_a):
    """
    Build a 9x9 joint probability grid using Dixon-Coles with dynamic rho.
    Grid is normalized to sum to 1.0.
    """
    rho = get_dynamic_rho(lambda_h, lambda_a)
    try:
        grid_obj = pb.models.create_dixon_coles_grid(
            home_lambda=lambda_h,
            away_lambda=lambda_a,
            rho=rho,
            max_goals=8
        )
        matrix = grid_obj.goal_matrix
        matrix_sum = matrix.sum()
        if matrix_sum > 0:
            matrix = matrix / matrix_sum
        return matrix
    except Exception as e:
        print(f"create_dixon_coles_grid failed: {e}. Using manual Poisson grid fallback.")
        return build_fallback_grid(lambda_h, lambda_a)

def build_fallback_grid(lambda_h, lambda_a):
    """
    Manual fallback 9x9 grid with Dixon-Coles adjustment using dynamic rho.
    """
    rho = get_dynamic_rho(lambda_h, lambda_a)
    matrix = [[0.0] * 9 for _ in range(9)]
    for h in range(9):
        for a in range(9):
            matrix[h][a] = poisson_pmf(h, lambda_h) * poisson_pmf(a, lambda_a)
            
    if lambda_h > 0 and lambda_a > 0:
        matrix[0][0] *= max(0.0, 1 - lambda_h * lambda_a * rho)
        matrix[1][0] *= max(0.0, 1 + lambda_a * rho)
        matrix[0][1] *= max(0.0, 1 + lambda_h * rho)
        matrix[1][1] *= max(0.0, 1 - rho)
        
    total = sum(sum(row) for row in matrix)
    if total > 0:
        for h in range(9):
            for a in range(9):
                matrix[h][a] /= total
    import numpy as np
    return np.array(matrix)

def optimize_score_prediction(prob_matrix):
    """
    Perform a grid search over all possible score predictions P_H, P_A in [0..8]
    to maximize Expected Points based on World Cup scoring rules:
    - Correct Outcome (1X2): 5 pts
    - Correct Home Goals: 2 pts
    - Correct Away Goals: 2 pts
    - Correct Goal Difference: 1 pt
    """
    best_h, best_a = 0, 0
    best_expected_points = -1.0
    n_goals = prob_matrix.shape[0]
    
    for p_h in range(n_goals):
        for p_a in range(n_goals):
            expected_points = 0.0
            
            for a_h in range(n_goals):
                for a_a in range(n_goals):
                    prob = prob_matrix[a_h][a_a]
                    points = 0
                    
                    pred_outcome = 1 if p_h > p_a else (-1 if p_h < p_a else 0)
                    actual_outcome = 1 if a_h > a_a else (-1 if a_h < a_a else 0)
                    if pred_outcome == actual_outcome:
                        points += 5
                        
                    if p_h == a_h:
                        points += 2
                        
                    if p_a == a_a:
                        points += 2
                        
                    if p_h - p_a == a_h - a_a:
                        points += 1
                        
                    expected_points += prob * points
                    
            if expected_points > best_expected_points:
                best_expected_points = expected_points
                best_h, best_a = p_h, p_a
                
    return best_h, best_a, best_expected_points

def fetch_scores():
    """
    Fetch recent scores from The Odds API.
    """
    if API_KEY == "YOUR_API_KEY" or not API_KEY:
        print("Using placeholder API key. Skipping scores fetch.")
        return []

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/scores/"
    params = {
        "apiKey": API_KEY,
        "daysFrom": 3
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"Successfully fetched {len(data)} event scores from The Odds API.")
            return data
        else:
            print(f"Failed to fetch scores: Code {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching scores: {e}")
        return []

def update_history_with_scores(history, scores_data):
    """
    Update historical predictions with actual scores and calculate actual points earned.
    """
    scores_by_id = {}
    scores_by_teams = {}
    
    for event in scores_data:
        event_id = event.get("id")
        completed = event.get("completed", False)
        scores = event.get("scores")
        
        if completed and scores and len(scores) == 2:
            try:
                home_team = event.get("home_team")
                away_team = event.get("away_team")
                
                home_score = None
                away_score = None
                
                for s in scores:
                    if s.get("name") == home_team:
                        home_score = int(s.get("score"))
                    elif s.get("name") == away_team:
                        away_score = int(s.get("score"))
                        
                if home_score is not None and away_score is not None:
                    score_info = {"home": home_score, "away": away_score}
                    if event_id:
                        scores_by_id[event_id] = score_info
                    if isinstance(home_team, str) and isinstance(away_team, str):
                        scores_by_teams[(home_team.lower(), away_team.lower())] = score_info
            except Exception as e:
                print(f"Error parsing event score: {e}")
                
    updated_count = 0
    for entry in history:
        if "actual_home_goals" in entry and "actual_away_goals" in entry:
            continue
            
        match_id = entry.get("match_id")
        home_team = entry.get("home_team") or ""
        away_team = entry.get("away_team") or ""
        
        score_info = None
        if match_id in scores_by_id:
            score_info = scores_by_id[match_id]
        elif (home_team.lower(), away_team.lower()) in scores_by_teams:
            score_info = scores_by_teams[(home_team.lower(), away_team.lower())]
            
        if score_info:
            act_h = score_info["home"]
            act_a = score_info["away"]
            pred_h = entry.get("predicted_home_goals")
            pred_a = entry.get("predicted_away_goals")
            
            if pred_h is not None and pred_a is not None:
                entry["actual_home_goals"] = act_h
                entry["actual_away_goals"] = act_a
                
                pred_outcome = 1 if pred_h > pred_a else (-1 if pred_h < pred_a else 0)
                actual_outcome = 1 if act_h > act_a else (-1 if act_h < act_a else 0)
                
                pts = 0
                if pred_outcome == actual_outcome:
                    pts += 5
                if pred_h == act_h:
                    pts += 2
                if pred_a == act_a:
                    pts += 2
                if pred_h - pred_a == act_h - act_a:
                    pts += 1
                    
                entry["actual_points"] = pts
                updated_count += 1
                print(f"  Updated score for {home_team} vs {away_team}: Actual={act_h}-{act_a}, Predicted={pred_h}-{pred_a}, Points={pts}")
                
    return updated_count

def main():
    print("=== Starting World Cup Score Predictor ===")
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    raw_matches = fetch_odds()
    predictions = []
    
    # Load existing results.json to check for already calculated predictions (to freeze/lock)
    existing_results_dict = {}
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                old_res = json.load(f)
                if isinstance(old_res, list):
                    existing_results_dict = {r["match_id"]: r for r in old_res if isinstance(r, dict) and "match_id" in r}
        except Exception as e:
            print(f"Failed to load existing results: {e}")
            
    for match in raw_matches:
        home_team = match.get("home_team")
        away_team = match.get("away_team")
        commence_time = match.get("commence_time")
        match_id = match.get("id")
        
        print(f"\nProcessing match: {home_team} vs {away_team} ({commence_time})")
        
        # Check if kickoff starts within 15 minutes or is in the past
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        commence_time_dt = None
        if commence_time:
            try:
                commence_time_dt = datetime.datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
            except Exception:
                pass
                
        is_near_or_past_kickoff = False
        if commence_time_dt:
            is_near_or_past_kickoff = commence_time_dt <= now_utc + datetime.timedelta(minutes=15)
            
        if is_near_or_past_kickoff and match_id in existing_results_dict:
            print(f"  Kickoff is near or has passed ({commence_time}). Reusing existing locked prediction.")
            predictions.append(existing_results_dict[match_id])
            continue
            
        parsed_odds = parse_match_odds(match)
        if not parsed_odds:
            print(f"Skipping match {home_team} vs {away_team}: No valid odds found.")
            continue
            
        home_odds, draw_odds, away_odds, over_odds, under_odds, totals_line = parsed_odds
        print(f"  Average Market Odds: Home={home_odds:.2f}, Draw={draw_odds:.2f}, Away={away_odds:.2f}")
        if over_odds is not None:
            print(f"  Average Totals Odds: Over={over_odds:.2f}, Under={under_odds:.2f} (Line={totals_line})")
        
        de_vigged_probs = de_vig_odds(home_odds, draw_odds, away_odds)
        home_prob, draw_prob, away_prob = de_vigged_probs
        print(f"  De-vigged Probabilities (Shin): Home={home_prob:.3f}, Draw={draw_prob:.3f}, Away={away_prob:.3f}")
        
        over_prob, under_prob = None, None
        if over_odds is not None and under_odds is not None:
            over_prob, under_prob = de_vig_totals(over_odds, under_odds)
            print(f"  De-vigged Totals (Over/Under {totals_line}): Over={over_prob:.3f}, Under={under_prob:.3f}")
            
        lambda_h, lambda_a = calculate_lambdas(
            home_prob, draw_prob, away_prob,
            over_prob, under_prob, totals_line
        )
        print(f"  Dixon-Coles Lambdas: lambda_H={lambda_h:.3f}, lambda_A={lambda_a:.3f}")
        
        prob_matrix = build_probability_grid(lambda_h, lambda_a)
        
        pred_h, pred_a, exp_pts = optimize_score_prediction(prob_matrix)
        print(f"  Optimal Prediction: {pred_h} - {pred_a} (Expected Points: {exp_pts:.3f})")
        
        import numpy as np
        max_idx = np.unravel_index(np.argmax(prob_matrix), prob_matrix.shape)
        most_likely_h, most_likely_a = int(max_idx[0]), int(max_idx[1])
        most_likely_prob = float(prob_matrix[most_likely_h][most_likely_a])
        print(f"  Most Likely Score: {most_likely_h} - {most_likely_a} (Probability: {most_likely_prob * 100:.1f}%)")
        
        predictions.append({
            "match_id": match_id,
            "commence_time": commence_time,
            "home_team": home_team,
            "away_team": away_team,
            "home_odds": round(home_odds, 2),
            "draw_odds": round(draw_odds, 2),
            "away_odds": round(away_odds, 2),
            "de_vigged_home_prob": round(home_prob, 4),
            "de_vigged_draw_prob": round(draw_prob, 4),
            "de_vigged_away_prob": round(away_prob, 4),
            "lambda_h": round(lambda_h, 4),
            "lambda_a": round(lambda_a, 4),
            "predicted_home_goals": pred_h,
            "predicted_away_goals": pred_a,
            "most_likely_home_goals": most_likely_h,
            "most_likely_away_goals": most_likely_a,
            "most_likely_prob": round(most_likely_prob, 4),
            "expected_points": round(exp_pts, 3)
        })
        
    HISTORY_FILE = os.path.join(SCRIPT_DIR, "history.json")
    old_predictions = []
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    old_predictions = loaded
        except Exception as e:
            print(f"Failed to load old predictions for archiving: {e}")
            
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    history = loaded
        except Exception as e:
            print(f"Failed to load existing history: {e}")
            
    archived_ids = {m["match_id"] for m in history if isinstance(m, dict) and "match_id" in m}
    
    archived_count = 0
    for old_match in old_predictions:
        if not isinstance(old_match, dict):
            continue
        match_id = old_match.get("match_id")
        commence_time_str = old_match.get("commence_time")
        
        if not match_id or "mock" in str(match_id):
            continue
            
        if commence_time_str:
            try:
                commence_time = datetime.datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
                if commence_time <= now_utc:
                    if match_id not in archived_ids:
                        history.append(old_match)
                        archived_ids.add(match_id)
                        archived_count += 1
            except Exception as e:
                print(f"Error parsing commence_time for archiving: {e}")
                
    # Fetch recent scores and update history
    print("\nFetching scores to update completed matches...")
    scores_data = fetch_scores()
    if scores_data:
        updated_scores_count = update_history_with_scores(history, scores_data)
        print(f"Updated actual scores/points for {updated_scores_count} matches in history.")
        
    try:
        history = [m for m in history if isinstance(m, dict)]
        history.sort(key=lambda x: x.get("commence_time") or "")
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        if archived_count > 0:
            print(f"Archived {archived_count} new past predictions to '{HISTORY_FILE}'.")
    except Exception as e:
        print(f"Failed to save history: {e}")
 
    try:
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(predictions, f, indent=4)
        print(f"\nSuccessfully saved predictions for {len(predictions)} matches to '{RESULTS_FILE}'.")
    except Exception as e:
        print(f"Failed to save predictions to JSON file: {e}")
 
    try:
        metadata_file = os.path.join(SCRIPT_DIR, "metadata.json")
        metadata = {
            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
        print(f"Successfully saved metadata to '{metadata_file}'.")
    except Exception as e:
        print(f"Failed to save metadata to JSON file: {e}")

if __name__ == "__main__":
    main()
