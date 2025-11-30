import os
import feedparser
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import uuid
import json
from sqlalchemy import or_

# Local imports
from models import db, Post, VideoUploadLog, FootballNews, BirthdayPost
from image_generator import generate_post_image, generate_hashtags, PLACEHOLDER_PATH, generate_post_image_nocrop
from facebook_poster import post_to_facebook, post_to_facebook_scheduled, post_multiple_to_facebook_scheduled
from telegram_webhook import telegram_bp
from generate_birthday_post_v2 import generate_birthday_post_v2
from dotenv import load_dotenv
from youtube_upload import upload_video_stream 
from facebook_poster import upload_video_to_facebook
from config import Config
import threading
import time
import logging
# ---------------- Load Environment Variables ---------------- #
load_dotenv()
# ---------------- App Setup ---------------- #

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder="static")
CORS(app)

# ✅ Register the Telegram webhook blueprint
app.register_blueprint(telegram_bp, url_prefix="/telegram")

# ---------------- Database Setup ---------------- #

DB_PATH = os.path.join(BASE_DIR, "posts.db")
# Use PostgreSQL in production, SQLite locally
if os.environ.get("RENDER"):  # Render sets this environment variable
    database_url = os.environ.get("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    print("🚀 Using PostgreSQL database")
else:
    # Local development - use SQLite
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    print("💻 Using SQLite database")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    try:
        print("🔄 Creating database tables...")
        db.create_all()
        print("✅ Tables created successfully!")
        
        # Check which database we're using
        is_postgres = 'postgresql' in app.config["SQLALCHEMY_DATABASE_URI"]
        
        if is_postgres:
            print("🚀 Using PostgreSQL database")
            # PostgreSQL-specific checks
            result = db.session.execute(db.text("SELECT current_database();"))
            db_name = result.fetchone()[0]
            print(f"📊 Connected to database: {db_name}")
            
            # List all tables
            result = db.session.execute(db.text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"📋 Existing tables: {tables}")
        else:
            print("💻 Using SQLite database")
            # SQLite-specific checks
            result = db.session.execute(db.text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = [row[0] for row in result.fetchall()]
            print(f"📋 Existing tables: {tables}")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()

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

    # By default, show posts fetched within the last 24 hours and not rejected.
    cutoff = datetime.utcnow() - timedelta(days=1)

    # If an explicit status is requested, respect it. For non-rejected
    # statuses, only return items newer than the cutoff. If the caller asks
    # for 'rejected' explicitly, return rejected posts regardless of age.
    if status:
        if status == "rejected":
            query = Post.query.filter_by(status="rejected")
        elif status in ["draft", "approved", "published"]:
            query = Post.query.filter_by(status=status).filter(Post.created_at >= cutoff)
        else:
            # unknown status -> return empty
            return jsonify([])
    else:
        # no explicit status -> return all non-rejected posts within 24h
        query = Post.query.filter(Post.status != "rejected").filter(Post.created_at >= cutoff)

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

# ---------------- Auto Fetch News ---------------- #
def auto_fetch_news():
        """Background task to fetch news automatically every 4 hours"""
        with app.app_context():
            try:
                print("🔄 Auto-fetching news...")
                articles = fetch_news()
                new_count = 0
                if not isinstance(articles, list):
                    logger.error(f"Scraper {source_name} returned non-list: {type(articles)}")
                    articles = []

                for a in articles:
                    if Post.query.filter_by(title=a["title"]).first():
                        continue  # Skip duplicates

                    img_path = generate_post_image_nocrop("", a["image_url"], a["url"], a["summary"], add_title=False)
                    if not img_path:
                        print(f"⚠️ Skipped {a['title']} due to missing image")
                        continue

                    hashtags = " ".join(generate_hashtags(a["title"], a["summary"]))

                    post = Post(
                        title=a["title"],
                        link=a["url"],
                        summary=a["summary"],
                        full_description=a["summary"],
                        image=img_path,
                        hashtags=hashtags,
                        status="draft",
                    )
                    db.session.add(post)
                    new_count += 1

                db.session.commit()
                print(f"✅ Auto-fetched {new_count} new posts at {datetime.now()}")
                
            except Exception as e:
                print(f"🔥 ERROR in auto_fetch_news: {str(e)}")
                import traceback
                traceback.print_exc()

# ---------------- Manual Upload Endpoint ---------------- #

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
        # Save uploaded file to a temporary path so we can send the same file
        # to both YouTube (stream) and Facebook (file path). Use static/tmp
        # under the project so it's writable on most hosts.
        upload_dir = os.path.join(BASE_DIR, "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        safe_name = secure_filename(file.filename)
        tmp_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}_{safe_name}")

        # Write file to disk
        with open(tmp_path, "wb") as out:
            out.write(file.read())

        # Upload to YouTube using a file stream
        with open(tmp_path, "rb") as stream:
            yt_video_id = upload_video_stream(stream, file.filename)

        # Upload to Facebook (expects a file path)
        try:
            fb_result = upload_video_to_facebook(tmp_path, file.filename)
        except Exception as e:
            fb_result = {"error": str(e)}

        log = VideoUploadLog(
            source="ui",
            original_filename=file.filename,
            youtube_video_id=(yt_video_id.get("id") if isinstance(yt_video_id, dict) else None),
            error=None if isinstance(yt_video_id, dict) else str(yt_video_id),
        )
        # attach facebook info as a text blob on the log if present
        try:
            log.facebook_response = json.dumps(fb_result)
        except Exception:
            log.facebook_response = str(fb_result)

        db.session.add(log)
        db.session.commit()

        # Cleanup temp file
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

        return jsonify({"ok": True, "youtube_id": yt_video_id, "facebook": fb_result})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ---------------- Birthday Posts Endpoints ---------------- #

# ✅ Fetch and auto-generate birthday posts      
@app.route("/birthday_posts", methods=["GET"])
def birthday_posts():
    try:
        
        # --- CLEANUP: Remove OLD birthday posts (anything not from today) ---
        today_date = datetime.now(timezone.utc).date()

        old_posts = BirthdayPost.query.filter(
            db.func.date(BirthdayPost.created_at) != today_date
        ).all()

        if old_posts:
            for p in old_posts:
                db.session.delete(p)
            db.session.commit()
            print(f"🧹 Deleted {len(old_posts)} old birthday posts.")
            
        # --- Step 1: Fetch today's Wikipedia birthdays ---
        today = datetime.now(timezone.utc)
        month = f"{today.month:02d}"
        day = f"{today.day:02d}"
        url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/births/{month}/{day}"
        
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://commons.wikimedia.org/"
        }

        res = safe_get(url, headers, timeout=25)
        if not res:
            return {"error": "Wikipedia unreachable"}
        status = request.args.get("status")

        if res.status_code != 200:
            print(f"⚠️ Wikipedia API returned {res.status_code}")
            return jsonify({"count": 0, "posts": []})

        data = res.json()
        births = data.get("births", []) if isinstance(data, dict) else []
        results = []

        # --- Step 2: Filter Film/TV personalities ---
        film_keywords = [
            "actor", "actress", "film", "television", "tv", "cinema",
            "director", "producer", "filmmaker", "show", "drama"
        ]

        for person in births:
            name = person.get("text", "")
            year = person.get("year", "Unknown")
            pages = person.get("pages", []) or []
            if not name or not pages:
                continue

            first_page = pages[0]
            summary = first_page.get("extract", "") or ""
            thumb = first_page.get("thumbnail")
            image = thumb.get("source", "") if isinstance(thumb, dict) else ""

            is_film_tv = any(k in summary.lower() for k in film_keywords)

            results.append({
                "name": name,
                "year": year,
                "summary": summary,
                "image": image,
                "is_film_tv": is_film_tv,
            })

        if not results:
            print("⚠️ No birthdays found.")
            return jsonify({"count": 0, "posts": []})

        # --- Step 3: Save all results to DB ---
        film_tv_results = [r for r in results if r["is_film_tv"] and r["year"] > 1950]
        saved_posts = []
        for r in film_tv_results:
            birth_year_str = str(r["year"])
            # Avoid duplicate insert if already exists for today
            
            existing = BirthdayPost.query.filter_by(
                name=r["name"], 
                birth_year=birth_year_str  # Compare as string
            ).first()
            if existing:
                continue
                
            post = BirthdayPost(
                name=r["name"],
                birth_year=birth_year_str,  # Store as string
                summary=r["summary"],
                image=r["image"],
                status="pending_generation",
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(post)
            saved_posts.append(post)
        db.session.commit()

        print(f"✅ Saved {len(saved_posts)} new Film/TV posts to DB.")

        # --- Step 5: Return all posts from DB ---
        query = BirthdayPost.query
        if status:
            query = query.filter_by(status=status)
        else:
            # Default: show only posts that are pending generation
            query = query.filter_by(status="pending_generation")

        posts = query.order_by(BirthdayPost.created_at.desc()).all()

        # ✅ SAFELY SERIALIZE — fix for “NoneType has no attribute isoformat”
        def safe_serialize(post):
            return {
                "id": post.id,
                "name": post.name,
                "birth_year": post.birth_year,
                "summary": post.summary,
                "image": post.image,
                "title": getattr(post, "title", None),
                "status": post.status,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "updated_at": post.updated_at.isoformat() if getattr(post, "updated_at", None) else None,
                "image_urls": getattr(post, "image_urls", None),
                "composite_style": getattr(post, "composite_style", None),
                "text_position": getattr(post, "text_position", None),
                "theme": getattr(post, "theme", None),
                "source_type": getattr(post, "source_type", None),
                "output_path": getattr(post, "output_path", None),
            }

        return jsonify([safe_serialize(p) for p in posts])

    except Exception as e:
        print("🔥 Error in birthday_posts:", str(e))
        return jsonify({"count": 0, "posts": []}), 500

# ✅ Approve Birthday Post
@app.route("/reject_post/<int:post_id>", methods=["POST"])
def reject_post_api(post_id):
    try:
        post = BirthdayPost.query.get(post_id)
        if not post:
            return jsonify({"error": "Post not found"}), 404

        post.status = "rejected"
        db.session.commit()

        return jsonify({"success": True, "message": f"Post {post_id} rejected."})
    except Exception as e:
        print("🔥 Error rejecting post:", str(e))
        return jsonify({"error": "Failed to reject post"}), 500

# ✅ Advanced Birthday Post Generation (v2)
@app.route("/birthday_post_direct", methods=["POST"])
def birthday_post_direct():
    try:
        # If JSON was sent (rare), handle it
        if request.content_type and "application/json" in request.content_type:
            data = request.get_json()
            name = data.get("name")
            year = data.get("year")
            image_urls = data.get("image_urls", [])
            uploaded_files = []
        else:
            # ✔️ FormData (React FE)
            name = request.form.get("name")
            year = request.form.get("year")
            image_urls = request.form.getlist("image_urls")  
            uploaded_files = request.files.getlist("images")  

        # Convert uploaded files → local saved paths
        local_paths = []
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)

        for file in uploaded_files:
            filename = secure_filename(file.filename)
            save_path = os.path.join(upload_dir, filename)
            file.save(save_path)
            local_paths.append(save_path)

        # Use uploaded images OR remote URLs
        final_image_sources = local_paths if local_paths else image_urls

        if not final_image_sources:
            return jsonify({"error": "No images provided"}), 400

        # 2️⃣ Build message
        message = f"Happy Birthday {name}! 🎉🎂"

        # 3️⃣ POST all images to Facebook (multi-image post)
        fb_result = post_multiple_to_facebook_scheduled(
            title=message,
            summary="",
            hashtags="",
            image_paths=final_image_sources,  # <-- ALL IMAGES
            scheduled_time=request.form.get("scheduled_time")
        )

        # 4️⃣ Update status in DB
        post_id = request.form.get("post_id")
        if post_id:
            bp = BirthdayPost.query.get(int(post_id))
            if bp:
                if "id" in fb_result:     # Facebook success
                    bp.status = "posted"
                    bp.fb_post_id = fb_result["id"]
                else:
                    bp.status = "failed"

                bp.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                print(f"📌 Updated DB record {post_id} → {bp.status}")
                
        # 4️⃣ Cleanup local files if any
        for path in local_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    print(f"🧹 Deleted local file: {path}")
            except Exception as cleanup_err:
                print(f"⚠️ Cleanup failed for {path}: {cleanup_err}")

        return jsonify({
            "success": True,
            "message": message,
            "image_count": len(final_image_sources),
            "facebook_result": fb_result
        })

    except Exception as e:
        print("🔥 Error in /birthday_post_direct:", e)
        return jsonify({"error": str(e)}), 500

# ---------------- Scraper API Endpoints ---------------- #
@app.route('/trigger-scraper', methods=['POST'])
def trigger_scraper():
    """Manually trigger the news scraper"""
    try:
        from scraper import run_scraper
        run_scraper(dry_run=False)
        return jsonify({"status": "success", "message": "Scraper run completed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/scraper-status', methods=['GET'])
def scraper_status():
    """Check scraper status"""
    return jsonify({
        "status": "running", 
        "thread_alive": scraper_thread.is_alive() if 'scraper_thread' in globals() else False
    })

# ---------------- Background Scraper Scheduler ---------------- #
def start_scraper_scheduler():
    """Start background scraper that runs every 4 hours"""
    def scraper_worker():
        logger = logging.getLogger("scraper_scheduler")
        interval_hours = 4
        interval_seconds = interval_hours * 3600
        
        logger.info(f"🚀 Scraper scheduler started (interval: {interval_hours} hours)")
        
        # Wait a bit for app to fully start
        time.sleep(30)
        
        while True:
            try:
                logger.info("🔄 Starting scheduled scraper run...")
                from scraper import run_scraper
                run_scraper(dry_run=False)
                logger.info("✅ Scheduled scraper run completed")
                logger.info("🔄 Starting scheduled fetch news run...")
                auto_fetch_news()
                logger.info("✅ Scheduled fetch news run completed")
            except Exception as e:
                logger.error(f"❌ Scheduled scraper run failed: {e}")
            
            logger.info(f"⏰ Waiting {interval_hours} hours until next run...")
            time.sleep(interval_seconds)
    
    # Start in background thread
    thread = threading.Thread(target=scraper_worker, daemon=True)
    thread.start()
    return thread

# Start the scraper scheduler when app starts
scraper_thread = start_scraper_scheduler()

# ---------------- Main ---------------- #
if __name__ == "__main__":
    print("🚀 Football Poster backend running on http://127.0.0.1:5000")
    app.run(host='0.0.0.0',  port=5000)
