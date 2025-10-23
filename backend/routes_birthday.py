import os
import sqlite3
import requests
from flask import Blueprint, jsonify, request
from facebook_poster import upload_to_facebook
from birthday_image import generate_birthday_image
from football_birthdays import get_week_birthdays

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "birthday_posts.db")

birthday_routes = Blueprint("birthday_routes", __name__)

# ---------------- Helpers ---------------- #

def get_db_connection():
    """Ensure DB and table exist before returning connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    create_table_if_missing(conn)
    return conn


def create_table_if_missing(conn):
    """Create table if not exists."""
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

# ---------------- Routes ---------------- #

@birthday_routes.route("/api/birthdays", methods=["GET"])
def get_birthdays():
    """Get all birthday posts filtered by status (draft/approved/rejected)."""
    status = request.args.get("status")
    conn = get_db_connection()
    cursor = conn.cursor()

    if status:
        cursor.execute("SELECT * FROM birthday_posts WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM birthday_posts ORDER BY created_at DESC")

    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@birthday_routes.route("/api/birthdays/generate", methods=["POST"])
def generate_birthday_post():
    """
    Generate a birthday post.
    - If frontend sends JSON with player info → generate single player post.
    - If no payload (like from current frontend) → auto-generate all birthdays for this week.
    """
    # Try reading JSON or form data
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    print("\n🧠 DEBUG LOG -------------------------")
    print(f"Content-Type: {request.content_type}")
    print(f"Raw data: {request.get_data()}")
    print(f"Form data: {request.form}")
    print(f"JSON data: {data}")
    print("-------------------------------------\n")

    player_name = data.get("player_name") or data.get("name")

    # ✅ If no player_name provided → auto-generate all birthdays
    if not player_name:
        birthdays = get_week_birthdays()
        if not birthdays:
            return jsonify({"message": "No birthdays found for this week."}), 200

        created = []
        for player in birthdays:
            name = player.get("name")
            team = player.get("team", "")
            image_url = player.get("photo", "")

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Download image
                img_data = requests.get(image_url, timeout=10).content
                image_dir = os.path.join(BASE_DIR, "static", "birthdays")
                os.makedirs(image_dir, exist_ok=True)
                img_path = os.path.join(image_dir, f"{name.replace(' ', '_')}.jpg")
                with open(img_path, "wb") as f:
                    f.write(img_data)

                # Generate banner
                final_image = generate_birthday_image(name, img_path, "Football", team)

                cursor.execute("""
                    INSERT INTO birthday_posts (name, team, image_path, status)
                    VALUES (?, ?, ?, ?)
                """, (name, team, final_image, "draft"))
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

    # ✅ Otherwise handle a single player request
    team = data.get("team", "")
    image_url = data.get("image_url") or data.get("image", "")
    post_now = str(data.get("post_now", "false")).lower() in ["true", "1", "yes"]

    conn = get_db_connection()
    cursor = conn.cursor()

    # Download player image
    try:
        image_dir = os.path.join(BASE_DIR, "static", "birthdays")
        os.makedirs(image_dir, exist_ok=True)
        img_path = os.path.join(image_dir, f"{player_name.replace(' ', '_')}.jpg")
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        with open(img_path, "wb") as f:
            f.write(response.content)
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to download image: {e}"}), 500

    # Generate banner
    try:
        final_image = generate_birthday_image(player_name, img_path, "Football", team)
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Image generation failed: {e}"}), 500

    # Save to DB
    status = "approved" if post_now else "draft"
    cursor.execute("""
        INSERT INTO birthday_posts (name, team, image_path, status)
        VALUES (?, ?, ?, ?)
    """, (player_name, team, final_image, status))
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
            "image_path": final_image,
            "status": status,
        },
        "facebook": fb_result
    })


@birthday_routes.route("/api/birthdays/<int:id>/approve", methods=["POST"])
def approve_birthday(id):
    """Approve a birthday post and upload to Facebook."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, team, image_path, status FROM birthday_posts WHERE id=?", (id,))
    post = cursor.fetchone()

    if not post:
        conn.close()
        return jsonify({"error": "Post not found"}), 404

    if post["status"] == "approved":
        conn.close()
        return jsonify({"message": "Already approved"}), 200

    caption = f"🎉 Happy Birthday {post['name']}! 🎂⚽ Wishing you success with {post['team'] or 'your club'}!"
    fb_result = upload_to_facebook(post["image_path"], caption)

    if fb_result and isinstance(fb_result, dict) and "id" in fb_result:
        cursor.execute("UPDATE birthday_posts SET status='approved' WHERE id=?", (id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Posted to Facebook successfully!"})
    else:
        conn.close()
        return jsonify({"error": fb_result.get('error', 'Facebook upload failed')}), 500


@birthday_routes.route("/api/birthdays/<int:id>/reject", methods=["POST"])
def reject_birthday(id):
    """Reject a birthday post."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE birthday_posts SET status='rejected' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Post rejected"})


@birthday_routes.route("/api/birthdays/<int:id>/delete", methods=["DELETE"])
def delete_birthday(id):
    """Delete a birthday post and remove the local image."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT image_path FROM birthday_posts WHERE id=?", (id,))
    post = cursor.fetchone()

    if post and os.path.exists(post["image_path"]):
        try:
            os.remove(post["image_path"])
        except Exception as e:
            print(f"[WARN] Could not delete image: {e}")

    cursor.execute("DELETE FROM birthday_posts WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Post deleted successfully"})
