import os
import feedparser
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename

# Local imports
from models import db, Post, VideoUploadLog
from image_generator import generate_post_image, generate_hashtags, PLACEHOLDER_PATH, generate_post_image_nocrop
from facebook_poster import post_to_facebook, post_to_facebook_scheduled
from football_birthdays import get_week_birthdays
from birthday_image import generate_birthday_image
from routes_birthday import birthday_routes  # ✅ Blueprint import
from telegram_webhook import telegram_bp
from dotenv import load_dotenv
from youtube_upload import upload_video_stream 

# ---------------- Load Environment Variables ---------------- #
load_dotenv()
# ---------------- App Setup ---------------- #

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, static_folder="static")
CORS(app)

# ✅ Register the birthday blueprint routes
app.register_blueprint(birthday_routes)

# ✅ Register the Telegram webhook blueprint
app.register_blueprint(telegram_bp, url_prefix="/telegram")

# ---------------- Database Setup ---------------- #
DB_PATH = os.path.join(BASE_DIR, "posts.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()


# ---------------- Helpers ---------------- #

def get_main_image(article_url: str):
    """Try to extract a main image from an article page."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(article_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # OpenGraph image
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            return og_img["content"]

        # First <img>
        img = soup.find("img")
        if img and img.get("src"):
            return urljoin(article_url, img["src"])
    except Exception as e:
        print("[ERROR] get_main_image:", e)
    return None


# ---------------- Routes ---------------- #

@app.route("/posts", methods=["GET"])
def get_posts():
    status = request.args.get("status")
    query = Post.query
    if status in ["draft", "approved", "published", "rejected"]:
        query = query.filter_by(status=status)
    posts = query.order_by(Post.created_at.desc()).all()
    return jsonify([p.serialize() for p in posts])


@app.route("/posts", methods=["POST"])
def create_post():
    data = request.json or {}

    title = data.get("title")
    summary = data.get("summary", "")
    full_description = data.get("full_description", "")
    article_url = data.get("article_url", "")
    image_url = data.get("image_url", "")

    if not title:
        return jsonify({"error": "Title is required"}), 400

    img_path = generate_post_image(title, image_url, article_url, summary)
    
    if not img_path:
        print(f"⚠️ Skipped {entry.title} due to missing image")
        return jsonify({"error": "Failed to generate post image"}), 500
    hashtags = generate_hashtags(title, summary)

    post = Post(
        title=title,
        link=article_url,
        summary=summary,
        full_description=full_description,
        image=img_path,
        hashtags=",".join(hashtags),
        status="draft",
    )
    db.session.add(post)
    db.session.commit()

    return jsonify(post.serialize()), 201


@app.route("/approve/<int:post_id>", methods=["POST"])
def approve_post(post_id):
    try:
        post = Post.query.get(post_id)
        if not post:
            return jsonify({"status": "error", "message": "Post not found"}), 404

        post.status = "approved"
        db.session.commit()

        fb_result = post_to_facebook(
            title=post.title,
            summary=post.summary,
            hashtags=post.hashtags.split(",") if post.hashtags else [],
            image_path=post.image if post.image else None
        )

        return jsonify({
            "status": "success",
            "message": f"Post {post_id} approved",
            "post": post.serialize(),
            "facebook": fb_result
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/reject/<int:post_id>", methods=["POST"])
def reject_post(post_id):
    try:
        post = Post.query.get(post_id)
        if not post:
            return jsonify({"status": "error", "message": "Post not found"}), 404

        post.status = "rejected"
        db.session.commit()
        return jsonify({"status": "success", "message": f"Post {post_id} rejected"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/posts/<int:post_id>/publish", methods=["POST"])
def publish_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.status = "published"
    db.session.commit()
    return jsonify(post.serialize())


@app.route("/fetch_news", methods=["POST"])
def fetch_news():
    """Fetch football news from RSS feeds and save as draft posts."""
    from rss_feeds import RSS_FEEDS

    new_posts = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:  # limit 5 per feed
            if Post.query.filter_by(title=entry.title).first():
                continue

            image_url = get_main_image(entry.link)
            summary = entry.get("summary", "")
            img_path = generate_post_image(entry.title, image_url, entry.link, summary)
            
            if not img_path:
                print(f"⚠️ Skipped {entry.title} due to missing image")
                continue  # skip this entry
            hashtags = generate_hashtags(entry.title, summary)

            post = Post(
                title=entry.title,
                link=entry.link,
                summary=summary,
                full_description=summary,
                image=img_path,
                hashtags=",".join(hashtags),
                status="draft",
            )
            db.session.add(post)
            new_posts.append(post)

    db.session.commit()
    return jsonify([p.serialize() for p in new_posts])


@app.route("/upload_manual_post", methods=["POST"])
def upload_manual_post():
    file = request.files.get("image")
    title = request.form.get("title", "").strip()
    summary = request.form.get("summary", "")
    post_now = request.form.get("post_now", "false").lower() == "true"
    scheduled_time_str = request.form.get("scheduled_time", "").strip()

    if not file or not title:
        return jsonify({"error": "Image and title are required"}), 400

    upload_dir = os.path.join(BASE_DIR, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Generate post image via image generator (so alignment/style stays consistent)
    img_path = generate_post_image_nocrop(title, filepath, "", summary)
    
    if not img_path:
        print(f"⚠️ Skipped {entry.title} due to missing image")
        return jsonify({"error": "Failed to generate post image"}), 500
    hashtags = generate_hashtags(title, summary)

    scheduled_time = None
    fb_result = None

    # Parse scheduled time if provided
    if scheduled_time_str:
        try:
            scheduled_time = datetime.fromisoformat(scheduled_time_str)
        except ValueError:
            try:
                scheduled_time = datetime.strptime(scheduled_time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                return jsonify({"error": "Invalid scheduled_time format. Use ISO or 'YYYY-MM-DD HH:MM'."}), 400

    post = Post(
        title=title,
        summary=summary,
        full_description=summary,
        image=img_path,
        hashtags=",".join(hashtags),
        status="approved" if (post_now or scheduled_time) else "draft",
    )
    db.session.add(post)
    db.session.commit()

    # If scheduled_time provided → schedule via Facebook API directly
    if scheduled_time:
        fb_result = post_to_facebook_scheduled(
            title=post.title,
            summary=post.summary,
            hashtags=hashtags,
            image_path=post.image,
            scheduled_time=scheduled_time
        )
        post.status = "scheduled"
        db.session.commit()

    elif post_now:
        fb_result = post_to_facebook(
            title=post.title,
            summary=post.summary,
            hashtags=hashtags,
            image_path=post.image
        )
        post.status = "published"
        db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Manual post created successfully",
        "post": post.serialize(),
        "facebook": fb_result
    })


# ✅ Unified static serving (works for all /static/* paths)
@app.route("/static/<path:filename>")
def serve_static(filename):
    """Serve any file inside the /static directory."""
    static_dir = os.path.join(BASE_DIR, "static")
    return send_from_directory(static_dir, filename)


@app.route("/delete_post/<int:post_id>", methods=["DELETE"])
def delete_post(post_id):
    try:
        post = Post.query.get(post_id)
        if not post:
            return jsonify({"status": "error", "message": "Post not found"}), 404

        if post.image:
            img_path = os.path.join(BASE_DIR, post.image) if not os.path.isabs(post.image) else post.image
            try:
                if os.path.exists(img_path):
                    os.remove(img_path)
            except Exception as e:
                print("[WARN] could not remove image:", e)

        db.session.delete(post)
        db.session.commit()
        return jsonify({"status": "success", "message": f"Post {post_id} deleted"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------- Upload Endpoint ---------------- #
@app.route("/upload_video", methods=["POST"])
def upload_video():
    """Upload a video from React UI."""
    if "file" not in request.files:
        return jsonify({"error": "Missing file"}), 400

    file = request.files["file"]

    try:
        yt_video_id = upload_video_stream(file.stream, file.filename)

        log = VideoUploadLog(
            source="ui",
            original_filename=file.filename,
            youtube_video_id=yt_video_id["id"]
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({"ok": True, "youtube_id": yt_video_id})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ---------------- Main ---------------- #
if __name__ == "__main__":
    print("🚀 Football Poster backend running on http://127.0.0.1:5000")
    app.run(host='0.0.0.0',  port=5000)
