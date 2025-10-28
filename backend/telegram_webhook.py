# telegram_webhook.py
import os
import requests
from flask import Blueprint, request, jsonify, render_template_string, send_file
from image_generator import generate_post_image_nocrop
from facebook_poster import upload_to_facebook
from config import Config
from models import db, TelePost
import traceback

telegram_bp = Blueprint("telegram", __name__)

BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
ALLOWED_CHANNELS = Config.ALLOWED_CHANNELS


@telegram_bp.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid payload"}), 400

    message = data.get("message") or data.get("channel_post")
    if not message:
        return jsonify({"error": "No message"}), 200

    chat = message.get("chat", {})
    channel_id = str(chat.get("id"))
    channel_title = chat.get("title", "Unknown")

    if ALLOWED_CHANNELS and channel_id not in ALLOWED_CHANNELS:
        print(f"🚫 Ignored message from {channel_title} ({channel_id}) - not in allowed list")
        return jsonify({"ignored": True}), 200

    caption = message.get("caption", "").strip()
    photo = message.get("photo")
    video = message.get("video")

    # --- Duplicate guard (check by caption + channel_id) --- #
    existing = (
        TelePost.query.filter_by(channel_id=channel_id, caption=caption)
        .order_by(TelePost.created_at.desc())
        .first()
    )
    if existing:
        print(f"⚠️ Duplicate detected: same caption already processed from {channel_title}")
        return jsonify({"duplicate": True}), 200

    local_image = None

    # --- Handle photos --- #
    if photo:
        file_id = photo[-1]["file_id"]
        file_path_resp = requests.get(
            f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/getFile?file_id={file_id}"
        )
        file_path = file_path_resp.json()["result"]["file_path"]
        img_url = f"https://api.telegram.org/file/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/{file_path}"
        local_image = generate_post_image_nocrop(title=caption or "Kick Off Zone", image_url=img_url, article_url="")

    # --- Handle videos (optional future) --- #
    local_video = None
    if video:
        file_id = video["file_id"]
        file_path_resp = requests.get(
            f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/getFile?file_id={file_id}"
        )
        file_path = file_path_resp.json()["result"]["file_path"]
        local_video = f"https://api.telegram.org/file/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/{file_path}"
        print(f"🎥 Video detected: {local_video}")

    # --- Save post in DB --- #
    post = TelePost(
        channel_id=channel_id,
        channel_title=channel_title,
        caption=caption,
        image_path=local_image or local_video,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.session.add(post)
    db.session.commit()

    print(f"✅ Saved Telegram post from {channel_title} ({channel_id})")

    # --- Optional: Auto-upload to Facebook if you want --- #
    if local_video:
        upload_video_to_facebook(local_video, caption)
    elif local_image:
        upload_to_facebook(local_image, caption)

    return jsonify({"ok": True}), 200