# telegram_webhook.py
import os
import requests
from flask import Blueprint, request, jsonify, render_template_string, send_file
from image_generator import generate_post_image_nocrop
from facebook_poster import upload_to_facebook, upload_video_to_facebook
from config import Config
from models import db, TelePost
import traceback
from datetime import datetime

telegram_bp = Blueprint("telegram", __name__)

BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
ALLOWED_CHANNELS = Config.ALLOWED_CHANNELS


@telegram_bp.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    msg = data.get("message") or data.get("channel_post")
    if not msg:
        return jsonify({"status": "ignored"}), 200

    chat_info = msg.get("chat", {})
    channel_id = str(chat_info.get("id", ""))
    channel_title = chat_info.get("title", "Unknown Channel")

    print(f"📥 Received post from {channel_title} ({channel_id})")

    # ✅ Allow only whitelisted channels
    if ALLOWED_CHANNELS and channel_id not in ALLOWED_CHANNELS:
        print(f"🚫 Ignored message from {channel_title} ({channel_id}) - not in allowed list")
        return jsonify({"status": "ignored_channel"}), 200

    caption = msg.get("caption", msg.get("text", "") or "").strip()
    photos = msg.get("photo", [])
    video = msg.get("video")

    # ✅ Duplicate guard (same caption & channel)
    existing = TelePost.query.filter_by(channel_id=channel_id, caption=caption).first()
    if existing:
        print(f"⚠️ Duplicate detected: already posted '{caption[:40]}...' from {channel_title}")
        return jsonify({"status": "duplicate_skipped"}), 200

    try:
        # Handle PHOTO post
        if photos:
            file_id = photos[-1]["file_id"]
            file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

            # Download image
            local_image = f"/tmp/{os.path.basename(file_path)}"
            with open(local_image, "wb") as f:
                f.write(requests.get(file_url).content)

            branded_image = generate_post_image_nocrop(
                title=caption,
                image_url=local_image,
                article_url=""
            )

            fb_caption = f"{caption}\n\n📢 From {channel_title}"
            fb_result = upload_to_facebook(branded_image, fb_caption)

            new_post = TelePost(
                channel_id=channel_id,
                channel_title=channel_title,
                caption=caption,
                image_path=branded_image,
                status="posted",
                created_at=datetime.utcnow()
            )
            db.session.add(new_post)
            db.session.commit()

            print(f"✅ Image post uploaded for {channel_title}")
            return jsonify({"status": "ok", "facebook_result": fb_result}), 200

        # Handle VIDEO post
        elif video:
            file_id = video["file_id"]
            file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

            # ✅ Download video locally
            local_video = f"/tmp/{os.path.basename(file_path)}"
            with open(local_video, "wb") as f:
                f.write(requests.get(file_url).content)

            fb_caption = f"{caption}\n\n📢 From {channel_title}"
            fb_result = upload_video_to_facebook(local_video, fb_caption)

            new_post = TelePost(
                channel_id=channel_id,
                channel_title=channel_title,
                caption=caption,
                image_path=local_video,
                status="posted",
                created_at=datetime.utcnow()
            )
            db.session.add(new_post)
            db.session.commit()

            print(f"✅ Video post uploaded for {channel_title}")
            return jsonify({"status": "ok", "facebook_result": fb_result}), 200

        else:
            print(f"⚠️ No media found from {channel_title}")
            return jsonify({"status": "no_media"}), 200

    except Exception as e:
        print(f"🔥 Error processing message from {channel_title}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@telegram_bp.route("/cleanup_tmp", methods=["POST"])
def cleanup_tmp():
    """
    Manually cleanup temporary folders to save Railway disk space.
    Deletes known temp folders like downloads/ and static/images/.
    """
    base_path = "/app"
    folders_to_clean = [
        os.path.join(base_path, "downloads"),
        os.path.join(base_path, "static", "images"),
        os.path.join(base_path, "tmp"),  # optional if you use this
    ]

    deleted = []
    skipped = []

    for folder in folders_to_clean:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                os.makedirs(folder, exist_ok=True)  # recreate empty folder
                deleted.append(folder)
            except Exception as e:
                skipped.append({"folder": folder, "error": str(e)})
        else:
            skipped.append({"folder": folder, "error": "Not found"})

    return jsonify({
        "status": "cleanup_complete",
        "deleted": deleted,
        "skipped": skipped
    })
