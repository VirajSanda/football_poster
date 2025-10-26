import os
import sqlite3
import requests
from PIL import Image
from flask import Blueprint, jsonify, request
from facebook_poster import upload_to_facebook
from birthday_image import generate_birthday_image
from football_birthdays import get_week_birthdays

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "birthday_posts.db")

# ✅ Correct image directories
LOCAL_PLAYER_DIR = os.path.join(BASE_DIR, "assets", "players")
BIRTHDAY_IMAGE_DIR = os.path.join(BASE_DIR, "static", "birthdays")
DEFAULT_LOCAL_IMAGE = os.path.join(LOCAL_PLAYER_DIR, "default.jpg")

# ✅ Resize settings (portrait format)
TARGET_SIZE = (1080, 1350)

birthday_routes = Blueprint("birthday_routes", __name__)


# ---------------- Helpers ---------------- #

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


def resize_or_crop_image(image_path):
    """Resize and crop to portrait ratio 1080x1350."""
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            target_ratio = TARGET_SIZE[0] / TARGET_SIZE[1]
            img_ratio = img.width / img.height

            # Crop to keep center focus
            if img_ratio > target_ratio:
                new_width = int(img.height * target_ratio)
                left = (img.width - new_width) // 2
                img = img.crop((left, 0, left + new_width, img.height))
            elif img_ratio < target_ratio:
                new_height = int(img.width / target_ratio)
                top = (img.height - new_height) // 2
                img = img.crop((0, top, img.width, top + new_height))

            img = img.resize(TARGET_SIZE, Image.LANCZOS)
            img.save(image_path, "JPEG", quality=95)
    except Exception as e:
        print(f"⚠️ Could not resize/crop image {image_path}: {e}")


def find_local_image(player_name):
    """Find an image in assets/players folder."""
    safe_name = player_name.replace(" ", "_")
    for ext in [".jpg", ".jpeg", ".png"]:
        path = os.path.join(LOCAL_PLAYER_DIR, f"{safe_name}{ext}")
        if os.path.exists(path):
            resize_or_crop_image(path)
            return path

    if os.path.exists(DEFAULT_LOCAL_IMAGE):
        resize_or_crop_image(DEFAULT_LOCAL_IMAGE)
        return DEFAULT_LOCAL_IMAGE

    return None


def download_image(image_url, dest_path):
    """Download a valid image URL, raise if invalid."""
    if not image_url or not image_url.startswith(("http://", "https://")):
        raise ValueError("Invalid image URL")
    resp = requests.get(image_url, timeout=10)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(resp.content)
    resize_or_crop_image(dest_path)
    return dest_path


def make_web_url(full_path):
    """Convert absolute local path → web-accessible /static/... URL."""
    rel_path = os.path.relpath(full_path, BASE_DIR).replace("\\", "/")
    if not rel_path.startswith("static/"):
        rel_path = f"static/{rel_path}"
    return f"/{rel_path}"


# ---------------- Routes ---------------- #

@birthday_routes.route("/api/birthdays", methods=["GET"])
def get_birthdays():
    """Get all birthday posts filtered by status."""
    status = request.args.get("status")
    conn = get_db_connection()
    cursor = conn.cursor()

    if status:
        cursor.execute("SELECT * FROM birthday_posts WHERE status=? ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM birthday_posts ORDER BY created_at DESC")

    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@birthday_routes.route("/api/birthdays/generate", methods=["POST"])
def generate_birthday_post():
    """Auto-generate all birthdays for this week or a single player."""
    data = request.get_json(silent=True) or {}
    player_name = data.get("player_name") or data.get("name")

    # ✅ Auto-generate weekly posts
    if not player_name:
        birthdays = get_week_birthdays()
        if not birthdays:
            return jsonify({"message": "No birthdays found for this week."}), 200

        created = []
        for player in birthdays:
            name = player.get("name")
            team = player.get("team", "")
            image_url = player.get("photo", "") or player.get("photo_url", "")

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                os.makedirs(BIRTHDAY_IMAGE_DIR, exist_ok=True)

                # ✅ Try local first
                local_img = find_local_image(name)
                if local_img:
                    img_path = local_img
                else:
                    img_path = os.path.join(BIRTHDAY_IMAGE_DIR, f"{name.replace(' ', '_')}.jpg")
                    try:
                        download_image(image_url, img_path)
                    except Exception:
                        print(f"⚠️ No valid image found for {name}, using default fallback.")
                        img_path = find_local_image("default")

                final_image = generate_birthday_image(name, img_path, "Football", team)
                image_url_web = make_web_url(final_image)

                cursor.execute("""
                    INSERT INTO birthday_posts (name, team, image_path, status)
                    VALUES (?, ?, ?, 'draft')
                """, (name, team, image_url_web))
                conn.commit()
                created.append(name)
            except Exception as e:
                print(f"⚠️ Error creating birthday for {name}: {e}")
            finally:
                conn.close()

        return jsonify({
            "status": "success",
            "message": f"Generated {len(created)} birthday posts for the week.",
            "players": created
        }), 200

    # ✅ Single player handler
    team = data.get("team", "")
    image_url = data.get("image_url") or data.get("image", "")
    post_now = str(data.get("post_now", "false")).lower() in ["true", "1", "yes"]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        os.makedirs(BIRTHDAY_IMAGE_DIR, exist_ok=True)
        local_img = find_local_image(player_name)
        if local_img:
            img_path = local_img
        else:
            img_path = os.path.join(BIRTHDAY_IMAGE_DIR, f"{player_name.replace(' ', '_')}.jpg")
            try:
                download_image(image_url, img_path)
            except Exception:
                print(f"⚠️ No valid image found for {player_name}, using default fallback.")
                img_path = find_local_image("default")

        final_image = generate_birthday_image(player_name, img_path, "Football", team)
        image_url_web = make_web_url(final_image)

        status = "approved" if post_now else "draft"
        cursor.execute("""
            INSERT INTO birthday_posts (name, team, image_path, status)
            VALUES (?, ?, ?, ?)
        """, (player_name, team, image_url_web, status))
        conn.commit()
        post_id = cursor.lastrowid

        fb_result = None
        if post_now:
            caption = f"🎉 Happy Birthday {player_name}! 🎂⚽ Wishing you success with {team or 'your club'}!"
            fb_result = upload_to_facebook(final_image, caption)
            cursor.execute("UPDATE birthday_posts SET status='approved' WHERE id=?", (post_id,))
            conn.commit()

        conn.close()

        return jsonify({
            "status": "success",
            "post": {
                "id": post_id,
                "name": player_name,
                "team": team,
                "image_path": image_url_web,
                "status": status,
            },
            "facebook": fb_result
        })

    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500
