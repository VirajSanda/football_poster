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

    # ✅ Telegram sends "channel_post" for channels
    msg = data.get("message") or data.get("channel_post")
    if not msg:
        print("⚠️ No message or channel_post in update.")
        return jsonify({"status": "ignored"}), 200

    chat_info = msg.get("chat", {})
    channel_id = str(chat_info.get("id", ""))
    channel_title = chat_info.get("title", "Unknown Channel")

    print(f"📥 Received post from {channel_title} ({channel_id})")

    # ✅ Filter allowed channels
    print(f"🔍 Channel ID: '{channel_id}' | Allowed: {ALLOWED_CHANNELS}")
    if ALLOWED_CHANNELS and channel_id not in ALLOWED_CHANNELS:
        print(f"🚫 Ignored message from {channel_title} ({channel_id}) - not in allowed list")
        return jsonify({"status": "ignored_channel"}), 200

    caption = msg.get("caption", msg.get("text", "") or "").strip()
    photos = msg.get("photo", [])

    if not photos:
        print(f"⚠️ No photo found in message from {channel_title}")
        return jsonify({"status": "no_photo"}), 200

    try:
        # ✅ Get highest resolution photo
        file_id = photos[-1]["file_id"]
        file_info = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        ).json()

        if "result" not in file_info:
            print("❌ Telegram file info missing 'result'")
            return jsonify({"status": "file_error"}), 200

        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        # ✅ Download image
        local_image = f"/tmp/{file_path.split('/')[-1]}"
        response = requests.get(file_url)
        with open(local_image, "wb") as f:
            f.write(response.content)

        # ✅ Generate your branded image
        branded_image = generate_post_image_nocrop(
            caption,
            local_image,
            ""
        )

        # ✅ Add Telegram channel tag to caption
        fb_caption = f"{caption}\n\n📢 From {channel_title}"

        # ✅ Upload to Facebook
        fb_result = upload_to_facebook(branded_image, fb_caption)

        print(f"✅ Posted from {channel_title} ({channel_id}) to Facebook.")
        return jsonify({"status": "ok", "facebook_result": fb_result}), 200

    except Exception as e:
        print("🔥 Full error traceback:")
        traceback.print_exc()
        print(f"🔥 Error processing message from {channel_title}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
