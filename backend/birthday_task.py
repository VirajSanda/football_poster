# backend/birthday_task.py
import requests
import os
from datetime import datetime, timezone
from backend.football_birthdays import get_week_birthdays

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000/api/birthdays")

def run_daily_birthday_task():
    """
    Fetch today's footballer birthdays (from Wikidata or fallback list),
    generate posts via backend API, and optionally auto-post to Facebook.
    """
    print(f"🎂 [Birthday Task] Running at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    players = get_week_birthdays()
    if not players:
        print("ℹ️ No player birthdays today.")
        return

    for p in players:
        try:
            payload = {
                "player_name": p["name"],
                "team": p.get("team"),
                "image_url": p.get("photo"),
                "post_now": False,  # Set True if you want to post automatically
            }
            res = requests.post(f"{API_BASE_URL}/generate", json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "success":
                    print(f"✅ Generated birthday post for {p['name']}")
                else:
                    print(f"⚠️ Failed for {p['name']}: {data.get('error')}")
            else:
                print(f"❌ API error for {p['name']}: {res.text}")
        except Exception as e:
            print(f"🚨 Exception while processing {p['name']}: {e}")

    print("🎉 [Birthday Task] Completed.\n")
