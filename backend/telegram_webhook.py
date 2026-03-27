import os
import shutil
import requests
import traceback
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from config import Config
from models import db, TelePost
from facebook_poster import upload_to_facebook, upload_video_to_facebook, upload_video_to_facebook_scheduled

# --------------------------------------------------
# Logging (CRITICAL)
# --------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_webhook")

# --------------------------------------------------
# Blueprint
# --------------------------------------------------
telegram_bp = Blueprint("telegram", __name__)

BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
ALLOWED_CHANNELS = set(map(str, Config.ALLOWED_CHANNELS or []))
TMP_DIR = "/tmp"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def telegram_get(url: str, timeout=15):
    logger.info("➡️ Telegram GET %s", url)
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
    logger.info("⬇️ Downloading %s", file_url)

    r = requests.get(file_url, stream=True, timeout=60)
    r.raise_for_status()

    with open(local_path, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            if chunk:
                f.write(chunk)

    logger.info("✅ Downloaded to %s", local_path)
    return local_path


def cleanup_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
            logger.info("🧹 Cleaned %s", path)
    except Exception as e:
        logger.warning("Cleanup failed: %s", e)


# --------------------------------------------------
# Webhook
# --------------------------------------------------

@telegram_bp.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    logger.info("🔥 TELEGRAM WEBHOOK HIT")

    payload = request.get_json(force=True, silent=True)
    logger.info("📥 Payload: %s", payload)

    msg = payload.get("channel_post") or payload.get("message")
    if not msg:
        logger.warning("⚠️ No message object")
        return jsonify({"status": "ignored"}), 200

    chat = msg.get("chat", {})
    channel_id = str(chat.get("id", ""))
    channel_title = chat.get("title", "Unknown")

    logger.info("📢 Channel %s (%s)", channel_title, channel_id)
    logger.info("🔑 Message keys: %s", list(msg.keys()))

    if ALLOWED_CHANNELS and channel_id not in ALLOWED_CHANNELS:
        logger.warning("🚫 Channel not allowed")
        return jsonify({"status": "ignored_channel"}), 200

    caption = (msg.get("caption") or msg.get("text") or "").strip()

    # -------- MEDIA DETECTION --------
    media_type = None
    file_id = None

    if msg.get("photo"):
        media_type = "photo"
        file_id = msg["photo"][-1]["file_id"]

    elif msg.get("video"):
        media_type = "video"
        file_id = msg["video"]["file_id"]

    elif msg.get("document", {}).get("mime_type", "").startswith("video/"):
        media_type = "video"
        file_id = msg["document"]["file_id"]

    elif msg.get("video_note"):
        media_type = "video"
        file_id = msg["video_note"]["file_id"]

    else:
        logger.warning("⚠️ No supported media")
        return jsonify({"status": "no_media"}), 200

    logger.info("📦 Media type: %s", media_type)

    # -------- DUPLICATE GUARD --------
    if TelePost.query.filter_by(channel_id=channel_id, caption=caption).first():
        logger.warning("⚠️ Duplicate skipped")
        return jsonify({"status": "duplicate"}), 200

    local_file = None

    try:
        file_info = telegram_get(f"{TELEGRAM_API}/getFile?file_id={file_id}")
        local_file = download_telegram_file(file_info["file_path"])

        # -------- PHOTO --------
        if media_type == "photo":
            fb_result = upload_to_facebook(local_file, caption)
            logger.info("📘 Facebook image response: %s", fb_result)

            post = TelePost(
                channel_id=channel_id,
                channel_title=channel_title,
                caption=caption,
                image_path=local_file,
                status="posted",
                created_at=datetime.now(timezone.utc),
            )

        # -------- VIDEO --------
        else:
            fb_result, scheduled_dt_utc = upload_video_to_facebook_scheduled(local_file, caption)
            logger.info("📘 Facebook video response: %s", fb_result)

            post = TelePost(
                channel_id=channel_id,
                channel_title=channel_title,
                caption=caption,
                image_path=local_file,
                status="posted",
                created_at=scheduled_dt_utc,
            )

        db.session.add(post)
        db.session.commit()

        logger.info("✅ Facebook post completed")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        db.session.rollback()
        logger.error("🔥 ERROR: %s", e)
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        cleanup_file(local_file)


# --------------------------------------------------
# Cleanup endpoint
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
