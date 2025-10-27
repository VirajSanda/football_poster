# telegram_webhook.py
import os
import requests
from flask import Blueprint, request, jsonify, render_template_string, send_file
from image_generator import generate_post_image_nocrop
from facebook_poster import upload_to_facebook
from config import Config
from models import db, TelePost

telegram_bp = Blueprint("telegram", __name__)

BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
ALLOWED_CHANNELS = Config.ALLOWED_CHANNELS


@telegram_bp.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    if not data or "message" not in data:
        return jsonify({"status": "ignored"}), 200

    msg = data["message"]
    chat_info = msg.get("chat", {})
    channel_id = str(chat_info.get("id", ""))
    channel_title = chat_info.get("title", "Unknown Channel")

    # ✅ Filter only allowed channels (your collector or list of channels)
    if ALLOWED_CHANNELS and channel_id not in ALLOWED_CHANNELS:
        print(f"Ignored message from {channel_title} ({channel_id})")
        return jsonify({"status": "ignored_channel"}), 200

    caption = msg.get("caption", "")
    photos = msg.get("photo", [])

    if not photos:
        return jsonify({"status": "no_photo"}), 200

    # Get highest-resolution photo
    file_id = photos[-1]["file_id"]
    file_info = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    ).json()

    if "result" not in file_info:
        return jsonify({"status": "file_error"}), 200

    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    # Download image locally
    local_image = f"/tmp/{file_path.split('/')[-1]}"
    with open(local_image, "wb") as f:
        f.write(requests.get(file_url).content)

    # 🖼️ Generate your branded image (small title area)
    branded_image = generate_post_image_nocrop(
        title=caption,
        image_path=local_image
    )

    # 🏷️ Add Telegram channel name tag to Facebook caption
    fb_caption = f"{caption}\n\n📢 From {channel_title}"

    # 🚀 Post directly to Facebook
    fb_result = upload_to_facebook(branded_image, fb_caption)

    print(f"Posted from {channel_title} ({channel_id}) to Facebook.")
    return jsonify({"status": "ok", "facebook_result": fb_result}), 200