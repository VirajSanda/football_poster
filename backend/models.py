from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(500))
    image = db.Column(db.String(255))
    summary = db.Column(db.Text)
    full_description = db.Column(db.Text)
    hashtags = db.Column(db.String(500))
    status = db.Column(db.String(20), default="draft")  # draft, approved, published
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "image": self.image,
            "summary": self.summary,
            "full_description": self.full_description,
            "hashtags": self.hashtags.split(",") if self.hashtags else [],
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

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
