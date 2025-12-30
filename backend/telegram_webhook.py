import os
import shutil
import requests
import traceback
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from config import Config
from models import db, TelePost
from image_generator import generate_post_image_nocrop
from facebook_poster import upload_to_facebook, upload_video_to_facebook

telegram_bp = Blueprint("telegram", __name__)

BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
ALLOWED_CHANNELS = set(map(str, Config.ALLOWED_CHANNELS or []))
TMP_DIR = "/tmp"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def telegram_get(url: str, timeout=10):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise Exception(f"Telegram API error: {data}")
    return data["result"]


def download_telegram_file(file_path: str) -> str:
    os.makedirs(TMP_DIR, exist_ok=True)
    local_path = os.path.join(TMP_DIR, os.path.basename(file_path))

    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    r = requests.get(file_url, stream=True, timeout=20)
    r.raise_for_status()

    with open(local_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

    return local_path


def cleanup_tmp():
    try:
        if os.path.exists(TMP_DIR):
            for f in os.listdir(TMP_DIR):
                os.remove(os.path.join(TMP_DIR, f))
    except Exception:
        pass


# --------------------------------------------------
# Webhook
# --------------------------------------------------

@telegram_bp.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    payload = request.get_json(silent=True) or {}

    msg = payload.get("channel_post") or payload.get("message")
    if not msg:
        return jsonify({"status": "ignored"}), 200

    chat = msg.get("chat", {})
    channel_id = str(chat.get("id", ""))
    channel_title = chat.get("title", "Unknown Channel")

    print(f"📥 Telegram post from {channel_title} ({channel_id})")

    # Allow only whitelisted channels
    if ALLOWED_CHANNELS and channel_id not in ALLOWED_CHANNELS:
        print("🚫 Channel not allowed")
        return jsonify({"status": "ignored_channel"}), 200

    caption = (msg.get("caption") or msg.get("text") or "").strip()
    photos = msg.get("photo", [])
    video = msg.get("video")

    media_type = "photo" if photos else "video" if video else None

    # ---------------- DUPLICATE GUARD ----------------
    existing = (
        TelePost.query
        .filter(TelePost.channel_id == channel_id)
        .filter(TelePost.caption == caption)
        .filter(TelePost.image_path.isnot(None))
        .first()
    )

    if existing:
        print("⚠️ Duplicate post skipped")
        return jsonify({"status": "duplicate"}), 200

    try:
        # ---------------- PHOTO ----------------
        if photos:
            file_id = photos[-1]["file_id"]
            file_info = telegram_get(f"{TELEGRAM_API}/getFile?file_id={file_id}")
            local_image = download_telegram_file(file_info["file_path"])

            branded_image = generate_post_image_nocrop(
                title=caption,
                image_url=local_image,
                article_url=""
            )

            fb_caption = f"{caption}\n\n📢 From {channel_title}"
            upload_to_facebook(branded_image, fb_caption)

            post = TelePost(
                channel_id=channel_id,
                channel_title=channel_title,
                caption=caption,
                image_path=branded_image,
                status="posted",
                created_at=datetime.now(timezone.utc)
            )

        # ---------------- VIDEO ----------------
        elif video:
            file_id = video["file_id"]
            file_info = telegram_get(f"{TELEGRAM_API}/getFile?file_id={file_id}")
            local_video = download_telegram_file(file_info["file_path"])

            fb_caption = f"{caption}\n\n📢 From {channel_title}"
            upload_video_to_facebook(local_video, fb_caption)

            post = TelePost(
                channel_id=channel_id,
                channel_title=channel_title,
                caption=caption,
                image_path=local_video,
                status="posted",
                created_at=datetime.now(timezone.utc)
            )

        else:
            return jsonify({"status": "no_media"}), 200

        db.session.add(post)
        db.session.commit()

        print("✅ Successfully posted to Facebook")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        cleanup_tmp()


# --------------------------------------------------
# Secure cleanup endpoint
# --------------------------------------------------

@telegram_bp.route("/cleanup_tmp", methods=["POST"])
def cleanup_tmp_endpoint():
    secret = request.headers.get("X-ADMIN-KEY")
    if Config.ADMIN_CLEANUP_KEY and secret != Config.ADMIN_CLEANUP_KEY:
        return jsonify({"error": "unauthorized"}), 401

    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
        os.makedirs(TMP_DIR, exist_ok=True)

    return jsonify({"status": "cleaned"}), 200


# --------------------------------------------------
# Test alias
# --------------------------------------------------

@telegram_bp.route("/test_webhook", methods=["POST"])
def test_webhook():
    return telegram_webhook()
