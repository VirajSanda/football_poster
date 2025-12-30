from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import LargeBinary
import json
import os
from flask import url_for

db = SQLAlchemy()


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(500))
    image = db.Column(db.String(255))  # Keep for backward compatibility
    image_data = db.Column(db.LargeBinary, nullable=True)  # Binary image data
    image_filename = db.Column(db.String(255), nullable=True)
    summary = db.Column(db.Text)
    full_description = db.Column(db.Text)
    hashtags = db.Column(db.String(500))
    status = db.Column(db.String(20), default="draft")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        """Return serialized post data"""
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "image": self.get_image_url(),  # Use dynamic URL
            "summary": self.summary,
            "full_description": self.full_description,
            "hashtags": self.hashtags.split(",") if self.hashtags else [],
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def get_image_url(self):
        """Get image URL - works with both old and new storage"""
        # New method: use /image/{id} endpoint
        return f"/image/{self.id}"
    
    def get_image_data(self):
        """Get image binary data"""
        # First try image_data (new storage)
        if self.image_data:
            return self.image_data
        
        # Fallback: try to read from file path (old storage)
        if self.image and os.path.exists(self.image):
            try:
                with open(self.image, 'rb') as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading image file {self.image}: {e}")
        
        return None

class TelePost(db.Model):
    __tablename__ = "tele_posts"

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(50))
    channel_title = db.Column(db.String(255))
    caption = db.Column(db.Text)
    image_path = db.Column(db.String(500))
    status = db.Column(db.String(20), default="pending")  # pending, approved, rejected, posted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "caption": self.caption,
            "image_path": self.image_path,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

class VideoUploadLog(db.Model):
    __tablename__ = "video_upload_logs"

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(50))
    original_filename = db.Column(db.String(500))
    youtube_video_id = db.Column(db.String(50))
    error = db.Column(db.Text, nullable=True)
    facebook_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "source": self.source,
            "original_filename": self.original_filename,
            "youtube_video_id": self.youtube_video_id,
            "error": self.error,
            "facebook_response": self.facebook_response,
            "created_at": self.created_at.isoformat(),
        }

class BirthdayPost(db.Model):
    __tablename__ = "birthday_posts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    birth_year = db.Column(db.String(10))
    summary = db.Column(db.Text)
    image = db.Column(db.String(512))
    title = db.Column(db.String(255))
    status = db.Column(db.String(50), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- 🔸 New fields (safe to add) ---
    image_urls = db.Column(db.Text)  # JSON-encoded list of image URLs (for collage/multiple)
    composite_style = db.Column(db.String(50), default="single")  # single | collage | side_by_side
    text_position = db.Column(db.String(50), default="auto")  # auto | top | middle | bottom | custom
    theme = db.Column(db.String(50), default="gold")  # for consistent look
    source_type = db.Column(db.String(50), default="wiki_fallback")  # or manual_upload
    output_path = db.Column(db.String(512))  # final generated file path (static/birthday_posts/*.jpg)

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "birth_year": self.birth_year,
            "summary": self.summary,
            "image": self.image,
            "image_urls": json.loads(self.image_urls) if self.image_urls else [],
            "title": self.title,
            "status": self.status,
            "composite_style": self.composite_style,
            "text_position": self.text_position,
            "theme": self.theme,
            "source_type": self.source_type,
            "output_path": self.output_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        
class FootballNews(db.Model):
    __tablename__ = "football_news"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    url = db.Column(db.Text, unique=True, nullable=False)
    image_url = db.Column(db.Text)
    source = db.Column(db.String(100))
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    seq = db.Column(db.Integer, index=True)          # sequence number for posting
    posted = db.Column(db.Boolean, default=False)    # posted flag
    hash = db.Column(db.String(64), index=True)      # sha256(title+summary)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scheduled_time = db.Column(db.DateTime, nullable=True)
    posted_at = db.Column(db.DateTime, nullable=True)
    video_url = db.Column(db.String(500), nullable=True) 

    def serialize(self):
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "image_url": self.image_url,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "seq": self.seq,
            "posted": bool(self.posted),
            "hash": self.hash,
            "created_at": self.created_at.isoformat(),
            "scheduled_time": self.scheduled_time.isoformat(),
            "posted_at": self.posted_at.isoformat(),
            "video_url": self.video_url,
        }

        