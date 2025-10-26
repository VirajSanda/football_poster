import os
import json
import re
import datetime
import sqlite3
import requests
from PIL import Image
from io import BytesIO

# === Paths ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "birthday_posts.db")
BIRTHDAY_JSON = os.path.join(BASE_DIR, "upcoming_birthdays.json")
IMAGE_DIR = os.path.join(BASE_DIR, "static", "birthdays")
LOCAL_PLAYER_DIR = os.path.join(BASE_DIR, "assets", "players")
DEFAULT_LOCAL_IMAGE = os.path.join(LOCAL_PLAYER_DIR, "default.jpg")

# === Image Settings ===
BANNER_WIDTH = 1080
BANNER_HEIGHT = 1350


# === Database Setup ===
def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS birthday_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            team TEXT,
            image_path TEXT,
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


# === Image Resize / Crop Helper ===
def resize_and_crop_image(image_path):
    """Resize and crop image to match banner aspect ratio (1080x1350)."""
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            target_ratio = BANNER_WIDTH / BANNER_HEIGHT
            img_ratio = img.width / img.height

            # Crop to maintain ratio
            if img_ratio > target_ratio:
                new_width = int(img.height * target_ratio)
                left = (img.width - new_width) // 2
                right = left + new_width
                img = img.crop((left, 0, right, img.height))
            elif img_ratio < target_ratio:
                new_height = int(img.width / target_ratio)
                top = (img.height - new_height) // 2
                bottom = top + new_height
                img = img.crop((0, top, img.width, bottom))

            img = img.resize((BANNER_WIDTH, BANNER_HEIGHT), Image.LANCZOS)
            img.save(image_path, "JPEG", quality=95)
    except Exception as e:
        print(f"⚠️ Error resizing {image_path}: {e}")


# === Local Image Detector ===
def detect_local_image(player_name):
    """
    Check assets/players for local image (.jpg, .jpeg, .png).
    """
    safe_name = player_name.replace(" ", "_")
    for ext in [".jpg", ".jpeg", ".png"]:
        candidate = os.path.join(LOCAL_PLAYER_DIR, f"{safe_name}{ext}")
        if os.path.exists(candidate):
            resize_and_crop_image(candidate)
            return candidate

    if os.path.exists(DEFAULT_LOCAL_IMAGE):
        resize_and_crop_image(DEFAULT_LOCAL_IMAGE)
        return DEFAULT_LOCAL_IMAGE

    return None


# === Safe Image Downloader ===
def safe_download_image(url, player_name):
    """
    Download or use local image for player.
    Falls back to local or default image when invalid/missing.
    """
    os.makedirs(IMAGE_DIR, exist_ok=True)
    safe_name = re.sub(r'[^A-Za-z0-9_]', '_', player_name)
    file_path = os.path.join(IMAGE_DIR, f"{safe_name}.jpg")

    # Empty or invalid URL → try local
    if not url or not url.startswith("http"):
        local_path = detect_local_image(player_name)
        if local_path:
            print(f"🖼️ Using local image for {player_name}: {local_path}")
            return local_path
        print(f"⚠️ Invalid URL & no local image found for {player_name}")
        return None

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        img.save(file_path, "JPEG", quality=95)
        resize_and_crop_image(file_path)
        return file_path

    except Exception as e:
        print(f"⚠️ Failed to download {player_name}: {e}")
        local_path = detect_local_image(player_name)
        if local_path:
            print(f"🖼️ Using fallback local image for {player_name}: {local_path}")
            return local_path
        return None


# === Get Upcoming Birthdays ===
def get_upcoming_birthdays(days_ahead=14):
    if not os.path.exists(BIRTHDAY_JSON):
        print(f"⚠️ Missing JSON file: {BIRTHDAY_JSON}")
        return []

    with open(BIRTHDAY_JSON, "r", encoding="utf-8") as f:
        players = json.load(f)

    today = datetime.date.today()
    window_end = today + datetime.timedelta(days=days_ahead)

    conn = get_db_connection()
    cursor = conn.cursor()
    new_players = []

    for p in players:
        name = p.get("name")
        team = p.get("team", "")
        dob_str = p.get("dob")
        photo_url = p.get("photo_url", "")

        if not name or not dob_str:
            continue

        try:
            dob = datetime.datetime.strptime(dob_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        # Leap year handling
        this_year_bday = dob.replace(year=today.year)
        if dob.month == 2 and dob.day == 29:
            this_year_bday = datetime.date(today.year, 2, 28)

        if today <= this_year_bday <= window_end:
            cursor.execute("SELECT id FROM birthday_posts WHERE name = ?", (name,))
            if cursor.fetchone():
                continue
            new_players.append({
                "name": name,
                "team": team,
                "dob": dob_str,
                "photo_url": photo_url
            })

    conn.close()
    return new_players


# === Generate Birthday Posts ===
def generate_birthday_posts():
    players = get_upcoming_birthdays(days_ahead=14)
    if not players:
        print("ℹ️ No upcoming birthdays found.")
        return {"status": "success", "message": "Generated 0 birthday posts.", "players": []}

    print(f"✅ Found {len(players)} birthdays between now and +14 days.")

    conn = get_db_connection()
    cursor = conn.cursor()
    created = []

    for player in players:
        name = player["name"]
        team = player.get("team", "")
        photo_url = player.get("photo_url")

        image_path = safe_download_image(photo_url, name)
        if not image_path:
            print(f"⚠️ Skipping {name}: could not obtain a valid image.")
            continue

        cursor.execute("""
            INSERT INTO birthday_posts (name, team, image_path, status)
            VALUES (?, ?, ?, 'draft')
        """, (name, team, image_path))
        conn.commit()

        created.append({"name": name, "team": team, "image": image_path})

    conn.close()
    print(f"🎉 Created {len(created)} new birthday posts.")
    return {"status": "success", "message": f"Generated {len(created)} birthday posts.", "players": created}


# === Optional Short Helper ===
def get_week_birthdays(days_ahead=7):
    return get_upcoming_birthdays(days_ahead)


# === Run Manually ===
if __name__ == "__main__":
    result = generate_birthday_posts()
    print(json.dumps(result, indent=2))
