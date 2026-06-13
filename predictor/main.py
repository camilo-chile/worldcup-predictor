"""
World Cup Score Predictor
Fetches match odds, de-vigs using Shin's method, models using Dixon-Coles,
and optimizes score predictions using Expected Points grid search.
"""

import os
import json
import math
import requests
import pandas as pd
import penaltyblog as pb
from dotenv import load_dotenv

load_dotenv()


# Configuration
API_KEY = os.getenv("THE_ODDS_API_KEY", "YOUR_API_KEY")
SPORT = "soccer_fifa_world_cup"
REGION = "eu,us,uk"
MARKET = "h2h"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(SCRIPT_DIR, "results.json")

# Realistic Mock Data if API fails or lacks active matches
MOCK_ODDS_RESPONSE = [
    {
        "id": "mock_match_1",
        "sport_key": "soccer_fifa_world_cup",
        "commence_time": "2026-06-15T18:00:00Z",
        "home_team": "Brazil",
        "away_team": "France",
        "bookmakers": [
            {
                "key": "mock_bookmaker_1",
                "title": "Mock Bookmaker 1",
                "last_update": "2026-06-11T12:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Brazil", "price": 2.10},
                            {"name": "France", "price": 3.40},
                            {"name": "Draw", "price": 3.20}
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
                            {"name": "Brazil", "price": 2.15},
                            {"name": "France", "price": 3.30},
                            {"name": "Draw", "price": 3.25}
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
        "home_team": "Argentina",
        "away_team": "Germany",
        "bookmakers": [
            {
                "key": "mock_bookmaker_1",
                "title": "Mock Bookmaker 1",
                "last_update": "2026-06-11T12:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Argentina", "price": 1.95},
                            {"name": "Germany", "price": 3.80},
                            {"name": "Draw", "price": 3.30}
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
        "home_team": "Spain",
        "away_team": "England",
        "bookmakers": [
            {
                "key": "mock_bookmaker_1",
                "title": "Mock Bookmaker 1",
                "last_update": "2026-06-11T12:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Spain", "price": 2.50},
                            {"name": "England", "price": 2.90},
                            {"name": "Draw", "price": 3.10}
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
    Calculate average odds for home win, draw, and away win across all bookmakers.
    """
    home_team = match["home_team"]
    away_team = match["away_team"]
    
    sum_home, sum_draw, sum_away = 0.0, 0.0, 0.0
    count = 0
    
    for bookmaker in match.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") == "h2h":
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
                    count += 1
                    
    if count > 0:
        return sum_home / count, sum_draw / count, sum_away / count
    return None

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
        implied = [1.0 / o for o in odds]
        total = sum(implied)
        return [p / total for p in implied]

def calculate_lambdas(home_prob, draw_prob, away_prob):
    """
    Infer goal expectations (lambdas) from de-vigged 1X2 probabilities
    using Dixon-Coles model with a default international rho of -0.13.
    """
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
        
    # Robust mathematical fallback if solver fails
    total_prob = home_prob + away_prob
    if total_prob > 0:
        ratio = home_prob / total_prob
        return float(ratio * 1.5), float((1.0 - ratio) * 1.3)
    return 1.4, 1.2

def build_probability_grid(lambda_h, lambda_a):
    """
    Build a 6x6 joint probability grid using Dixon-Coles with rho=-0.13.
    Grid is normalized to sum to 1.0.
    """
    try:
        grid_obj = pb.models.create_dixon_coles_grid(
            home_lambda=lambda_h,
            away_lambda=lambda_a,
            rho=-0.13,
            max_goals=5
        )
        matrix = grid_obj.goal_matrix
        matrix_sum = matrix.sum()
        if matrix_sum > 0:
            matrix = matrix / matrix_sum
        return matrix
    except Exception as e:
        print(f"create_dixon_coles_grid failed: {e}. Using manual Poisson grid fallback.")
        return build_fallback_grid(lambda_h, lambda_a)

def poisson_pmf(k, mu):
    """Calculate Poisson Probability Mass Function."""
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    return (mu ** k) * math.exp(-mu) / math.factorial(k)

def build_fallback_grid(lambda_h, lambda_a):
    """
    Manual fallback 6x6 grid with Dixon-Coles adjustment using rho=-0.13.
    """
    matrix = [[0.0] * 6 for _ in range(6)]
    for h in range(6):
        for a in range(6):
            matrix[h][a] = poisson_pmf(h, lambda_h) * poisson_pmf(a, lambda_a)
            
    # Apply standard Dixon-Coles adjustment for low scores
    rho = -0.13
    if lambda_h > 0 and lambda_a > 0:
        matrix[0][0] *= max(0.0, 1 - lambda_h * lambda_a * rho)
        matrix[1][0] *= max(0.0, 1 + lambda_a * rho)
        matrix[0][1] *= max(0.0, 1 + lambda_h * rho)
        matrix[1][1] *= max(0.0, 1 - rho)
        
    # Normalize
    total = sum(sum(row) for row in matrix)
    if total > 0:
        for h in range(6):
            for a in range(6):
                matrix[h][a] /= total
    import numpy as np
    return np.array(matrix)

def optimize_score_prediction(prob_matrix):
    """
    Perform a grid search over all possible score predictions P_H, P_A in [0..5]
    to maximize Expected Points based on World Cup scoring rules:
    - Correct Outcome (1X2): 5 pts
    - Correct Home Goals: 2 pts
    - Correct Away Goals: 2 pts
    - Correct Goal Difference: 1 pt
    """
    best_h, best_a = 0, 0
    best_expected_points = -1.0
    
    # Grid search over predictions P_H, P_A in [0..5]
    for p_h in range(6):
        for p_a in range(6):
            expected_points = 0.0
            
            # Sum expected points across all possible actual outcomes A_H, A_A
            for a_h in range(6):
                for a_a in range(6):
                    prob = prob_matrix[a_h][a_a]
                    points = 0
                    
                    # 1. Correct Outcome (1X2): 5 pts
                    pred_outcome = 1 if p_h > p_a else (-1 if p_h < p_a else 0)
                    actual_outcome = 1 if a_h > a_a else (-1 if a_h < a_a else 0)
                    if pred_outcome == actual_outcome:
                        points += 5
                        
                    # 2. Correct Home Goals: 2 pts
                    if p_h == a_h:
                        points += 2
                        
                    # 3. Correct Away Goals: 2 pts
                    if p_a == a_a:
                        points += 2
                        
                    # 4. Correct Goal Difference: 1 pt
                    if p_h - p_a == a_h - a_a:
                        points += 1
                        
                    expected_points += prob * points
                    
            if expected_points > best_expected_points:
                best_expected_points = expected_points
                best_h, best_a = p_h, p_a
                
    return best_h, best_a, best_expected_points

def main():
    print("=== Starting World Cup Score Predictor ===")
    raw_matches = fetch_odds()
    predictions = []
    
    for match in raw_matches:
        home_team = match.get("home_team")
        away_team = match.get("away_team")
        commence_time = match.get("commence_time")
        match_id = match.get("id")
        
        print(f"\nProcessing match: {home_team} vs {away_team} ({commence_time})")
        
        # Parse average odds
        parsed_odds = parse_match_odds(match)
        if not parsed_odds:
            print(f"Skipping match {home_team} vs {away_team}: No valid odds found.")
            continue
            
        home_odds, draw_odds, away_odds = parsed_odds
        print(f"  Average Market Odds: Home={home_odds:.2f}, Draw={draw_odds:.2f}, Away={away_odds:.2f}")
        
        # De-vig odds using Shin's method
        de_vigged_probs = de_vig_odds(home_odds, draw_odds, away_odds)
        home_prob, draw_prob, away_prob = de_vigged_probs
        print(f"  De-vigged Probabilities (Shin): Home={home_prob:.3f}, Draw={draw_prob:.3f}, Away={away_prob:.3f}")
        
        # Calculate goal expectations (lambdas)
        lambda_h, lambda_a = calculate_lambdas(home_prob, draw_prob, away_prob)
        print(f"  Dixon-Coles Lambdas: lambda_H={lambda_h:.3f}, lambda_A={lambda_a:.3f}")
        
        # Build joint probability matrix
        prob_matrix = build_probability_grid(lambda_h, lambda_a)
        
        # Find optimal prediction to maximize Expected Points
        pred_h, pred_a, exp_pts = optimize_score_prediction(prob_matrix)
        print(f"  Optimal Prediction: {pred_h} - {pred_a} (Expected Points: {exp_pts:.3f})")
        
        # Store prediction
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
            "expected_points": round(exp_pts, 3)
        })
        
    # Save predictions to results.json
    try:
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(predictions, f, indent=4)
        print(f"\nSuccessfully saved predictions for {len(predictions)} matches to '{RESULTS_FILE}'.")
    except Exception as e:
        print(f"Failed to save predictions to JSON file: {e}")

if __name__ == "__main__":
    main()
