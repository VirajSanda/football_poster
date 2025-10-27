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

    # Filter only allowed channels
    if ALLOWED_CHANNELS and channel_id not in ALLOWED_CHANNELS:
        print(f"Ignored message from channel {channel_title} ({channel_id})")
        return jsonify({"status": "ignored_channel"}), 200

    caption = msg.get("caption", "")
    photos = msg.get("photo", [])

    if not photos:
        return jsonify({"status": "no_photo"}), 200

    # Get highest resolution image
    file_id = photos[-1]["file_id"]
    file_info = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    ).json()
    if "result" not in file_info:
        return jsonify({"status": "file_error"}), 200

    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    # Download locally
    local_image = f"/tmp/{file_path.split('/')[-1]}"
    with open(local_image, "wb") as f:
        f.write(requests.get(file_url).content)

    # Generate branded image (you already have generate_post_image_nocrop)
    branded_image = generate_post_image_nocrop(
        title=caption,
        image_path=local_image
    )

    # Save as pending post
    tele_post = TelePost(
        channel_id=channel_id,
        channel_title=channel_title,
        caption=caption,
        image_path=branded_image,
        status="pending"
    )
    db.session.add(tele_post)
    db.session.commit()

    print(f"Saved pending Telegram post {tele_post.id} from {channel_title}")
    return jsonify({"status": "pending", "id": tele_post.id}), 200

@telegram_bp.route("/review", methods=["GET"])
def review_posts():
    pending_posts = TelePost.query.filter_by(status="pending").order_by(TelePost.created_at.desc()).all()

    if not pending_posts:
        return "<h3>No pending posts</h3>"

    html = "<h2>Pending Telegram Posts</h2>"
    for p in pending_posts:
        html += f"""
        <div style='border:1px solid #ccc; margin:10px; padding:10px; max-width:600px;'>
            <h4>{p.caption}</h4>
            <p>📢 From {p.channel_title}</p>
            <img src='/telegram/view_image/{p.id}' width='400'/><br>
            <a href='/telegram/approve/{p.id}'>✅ Approve</a> |
            <a href='/telegram/reject/{p.id}'>❌ Reject</a>
        </div>
        """
    return html


@telegram_bp.route("/view_image/<int:post_id>")
def view_image(post_id):
    post = TelePost.query.get(post_id)
    if not post or not os.path.exists(post.image_path):
        return "Image not found", 404
    return send_file(post.image_path, mimetype="image/jpeg")


@telegram_bp.route("/approve/<int:post_id>")
def approve_post(post_id):
    post = TelePost.query.get(post_id)
    if not post:
        return "Post not found", 404

    fb_caption = f"{post.caption}\n\n📢 From {post.channel_title}"
    result = upload_to_facebook(post.image_path, fb_caption)

    post.status = "posted"
    db.session.commit()

    return f"<h3>✅ Posted to Facebook!</h3><p>{result}</p><a href='/telegram/review'>Back</a>"


@telegram_bp.route("/reject/<int:post_id>")
def reject_post(post_id):
    post = TelePost.query.get(post_id)
    if not post:
        return "Post not found", 404

    db.session.delete(post)
    db.session.commit()

    return "<h3>❌ Rejected and deleted</h3><a href='/telegram/review'>Back</a>"
    
@telegram_bp.route("/")
def index():
    return "<h3>Telegram Webhook is running.</h3>"