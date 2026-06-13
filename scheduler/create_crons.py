import csv
import os
import sys
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()


# ==========================================
# CONFIGURATION
# ==========================================
# 1. Cron-job.org credentials
CRON_JOB_API_KEY = os.getenv("CRON_JOB_API_KEY", "YOUR_CRON_JOB_API_KEY")

# 2. GitHub credentials and repository details
GITHUB_PAT = os.getenv("GITHUB_PAT", "YOUR_GITHUB_PAT")
GITHUB_USER = "camilo-chile"
GITHUB_REPO = "worldcup-predictor"
# Note: By default, the script triggers the workflow file name you provided.
# If your workflow file is named 'predict_games.yml' (the one in this repo), 
# make sure to use 'predict_games.yml' in the URL!
WORKFLOW_FILE = "predict_games.yml" # Change to "predict.yml" if that is your target file

# ==========================================
# MAIN ROUTINE
# ==========================================
def load_matches_from_csv(csv_path=None):
    """
    Parse the CSV and extract remaining group stage matches (Match 3 to 72).
    Calculates execution time (kickoff - 45 minutes).
    """
    if csv_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(script_dir, "fifa-world-cup-2026-UTC.csv")

    if not os.path.exists(csv_path):
        print(f"Error: The schedule file '{csv_path}' was not found.")
        sys.exit(1)
        
    matches = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get("Date", "").strip()
            if not date_str:
                continue
                
            try:
                # Date format in CSV: DD/MM/YYYY HH:MM (already in UTC)
                kickoff = datetime.strptime(date_str, "%d/%m/%Y %H:%M")
            except ValueError:
                continue
                
            match_num = int(row.get("Match Number", 0))
            # Filter for Matches 3 to 72 inclusive (the 70 remaining group stage matches)
            if 3 <= match_num <= 72:
                exec_time = kickoff - timedelta(minutes=45)
                matches.append({
                    "match_number": match_num,
                    "home": row.get("Home Team", "").strip(),
                    "away": row.get("Away Team", "").strip(),
                    "kickoff": kickoff,
                    "exec_time": exec_time
                })
                
    # Sort chronologically by execution time
    matches.sort(key=lambda x: x["exec_time"])
    return matches

def create_cron_job(match):
    """
    Calls the cron-job.org API to create a one-time cron job for a match.
    """
    headers = {
        "Authorization": f"Bearer {CRON_JOB_API_KEY}",
        "Content-Type": "application/json"
    }
    
    url = "https://api.cron-job.org/jobs"
    
    # Calculate schedule parameters (all integers)
    exec_dt = match["exec_time"]
    minutes = [exec_dt.minute]
    hours = [exec_dt.hour]
    mdays = [exec_dt.day]
    months = [exec_dt.month]
    wdays = [-1] # Any day of the week
    
    title = f"WC2026 Match #{match['match_number']}: {match['home']} vs {match['away']}"
    github_webhook_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    
    payload = {
        "job": {
            "title": title,
            "url": github_webhook_url,
            "enabled": True,
            "schedule": {
                "timezone": "UTC",
                "minutes": minutes,
                "hours": hours,
                "mdays": mdays,
                "months": months,
                "wdays": wdays
            },
            "extendedData": {
                "method": 1, # HTTP POST method in cron-job.org API
                "headers": {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "cron-job-org-client",
                    "Authorization": f"token {GITHUB_PAT}"
                },
                "body": "{\"ref\": \"main\"}"
            }
        }
    }
    
    try:
        # PUT request is used to create jobs in the cron-job.org API
        response = requests.put(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 201 or response.status_code == 200:
            print(f"✔ Successfully created cron job for Match #{match['match_number']} ({match['home']} vs {match['away']})")
            return True
        else:
            print(f"❌ Failed to create cron job for Match #{match['match_number']}: Code {response.status_code}")
            print(f"   Response details: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error during API call for Match #{match['match_number']}: {e}")
        return False

def main():
    print("=== World Cup 2026 Cron Scheduler ===")
    
    # Check if API keys have been configured
    if CRON_JOB_API_KEY == "YOUR_CRON_JOB_API_KEY" or GITHUB_PAT == "YOUR_GITHUB_PAT":
        print("\n[WARNING] Please configure your 'CRON_JOB_API_KEY' and 'GITHUB_PAT' variables in the script first.")
        print("You can also set them as environment variables before running.")
        
    matches = load_matches_from_csv()
    print(f"Parsed {len(matches)} group stage matches remaining.")
    
    confirm = input(f"\nDo you want to create {len(matches)} cron jobs on cron-job.org? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("Execution cancelled by user.")
        return
        
    success_count = 0
    for match in matches:
        if create_cron_job(match):
            success_count += 1
            
    print(f"\nCompleted! Created {success_count}/{len(matches)} cron jobs successfully.")

if __name__ == "__main__":
    main()
