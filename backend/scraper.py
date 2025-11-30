"""
Cron-ready scraper for football news with built-in Facebook scheduling
"""
import os
import sys
import json
import hashlib
import argparse
import logging
import time
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from models import db, FootballNews
from config import Config
from app import app

# Facebook Config (add to your .env)
FACEBOOK_PAGE_ID = Config.FACEBOOK_PAGE_ID
FACEBOOK_ACCESS_TOKEN = Config.FACEBOOK_ACCESS_TOKEN

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("football-scraper")

# Helpers
def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# Football keywords (SOCCER ONLY - excluding American football)
FOOTBALL_KEYWORDS = [
    "premier league", "premierleague", "epl", "english premier league",
    "la liga", "laliga", "serie a", "seriea", "bundesliga", 
    "champions league", "europa league", "europa conference", "uefa",
    "world cup", "euro", "euros", "euro2024", "euro 2024",
    "transfer", "signing", "transfer news", "transfer window",
    "goal", "goals", "match", "fixture", "lineup", "starting xi",
    "injury", "injury update", "team news", "tactics", "formation",
    "manager", "coach", "preseason", "pre-season", "friendly",
    "hat-trick", "clean sheet", "assist", "penalty", "free kick",
    "man city", "manchester city", "man utd", "manchester united", 
    "liverpool", "chelsea", "arsenal", "tottenham", "spurs",
    "real madrid", "barcelona", "atletico", "atlético", "barca",
    "bayern", "dortmund", "psg", "juventus", "milan", "inter",
    "fifa", "uefa", "premier league", "premierleague", "fifa world cup",
    "world cup qualifier", "international", "national team"
]

# American football exclusion patterns
AMERICAN_FOOTBALL_KEYWORDS = [
    "nfl", "super bowl", "touchdown", "quarterback", "running back",
    "wide receiver", "offensive line", "defensive line", "linebacker",
    "cornerback", "safety", "field goal", "extra point", "punt",
    "kickoff", "onside kick", "hail mary", "playoff", "pro bowl",
    "american football", "gridiron", "first down", "end zone",
    "ncaa football", "college football", "cfb", "xfl", "usfl", "question", 
    "quiz", "?"
]

def looks_like_football(title: str, summary: str, url: str) -> bool:
    """Check if content is about football (soccer) and NOT American football"""
    text = " ".join([title or "", summary or "", url or ""]).lower()
    
    # First, exclude American football
    if any(af_kw in text for af_kw in AMERICAN_FOOTBALL_KEYWORDS):
        return False
    
    # Then check for real football content
    return any(kw in text for kw in FOOTBALL_KEYWORDS)

def normalize_article(item: Dict) -> Dict:
    return {
        "title": (item.get("title") or "").strip(),
        "summary": (item.get("summary") or "").strip(),
        "url": (item.get("url") or "").strip(),
        "image_url": (item.get("image_url") or "").strip() if item.get("image_url") else None,
        "source": (item.get("source") or "").strip(),
    }

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# --------------------------------------------------------------------
# PREMIER LEAGUE OFFICIAL SITE - IMPROVED VERSION
# --------------------------------------------------------------------
def scrape_premier_league():
    """Scrape official Premier League news - IMPROVED SELECTORS"""
    urls = [
        "https://www.premierleague.com/news",
        "https://www.premierleague.com/news?page=1",
        "https://www.premierleague.com/news?page=2"
    ]
    
    logger.info("Scraping Premier League news...")
    all_results = []
    
    for url in urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Multiple selector strategies for Premier League
            selectors = [
                'a[href*="/news/"]',
                '.newsArticle',
                '.article',
                '.news-item',
                '.news-list__item',
                '[data-component="news-article"]',
                '.news-card',
                '.card--news'
            ]
            
            articles = []
            for selector in selectors:
                found = soup.select(selector)
                articles.extend(found)
                if found:
                    logger.debug(f"Found {len(found)} articles with selector: {selector}")
            
            # Remove duplicates by URL
            seen_urls = set()
            for article in articles:
                try:
                    # Get URL first
                    href = article.get('href', '')
                    if not href and article.find('a'):
                        href = article.find('a').get('href', '')
                    
                    if not href or href in seen_urls:
                        continue
                    
                    seen_urls.add(href)
                    
                    # Get title
                    title = ""
                    title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.headline', '.newsArticle__title']
                    for title_sel in title_selectors:
                        title_el = article.select_one(title_sel)
                        if title_el:
                            title = title_el.get_text(strip=True)
                            if title:
                                break
                    
                    if not title and article.get_text(strip=True):
                        title = article.get_text(strip=True)
                    
                    if not title or len(title) < 10:
                        continue
                    
                    # Filter out non-football content
                    if not looks_like_football(title, "", href):
                        continue
                    
                    # Construct full URL
                    if href.startswith('/'):
                        href = f"https://www.premierleague.com{href}"
                    elif not href.startswith('http'):
                        continue
                    
                    # Extract summary
                    summary = ""
                    summary_selectors = ['p', '.summary', '.excerpt', '.description', '.newsArticle__summary']
                    for summary_sel in summary_selectors:
                        summary_el = article.select_one(summary_sel)
                        if summary_el:
                            summary = summary_el.get_text(strip=True)
                            if summary:
                                break
                    
                    # Extract image
                    image_url = None
                    img_el = article.find('img')
                    if img_el:
                        image_url = img_el.get('src') or img_el.get('data-src') or img_el.get('data-lazy')
                        if image_url:
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            elif image_url.startswith('/'):
                                image_url = f"https://www.premierleague.com{image_url}"
                    
                    results.append({
                        "title": title[:300],  # Limit title length
                        "summary": summary[:500],  # Limit summary length
                        "url": href,
                        "image_url": image_url,
                        "source": "Premier League"
                    })
                    
                except Exception as e:
                    logger.debug("Error processing Premier League article: %s", e)
                    continue
            
            all_results.extend(results)
            logger.info("Found %d Premier League items from %s", len(results), url)
            
        except Exception as e:
            logger.error("Premier League scrape failed for %s: %s", url, e)
            continue
    
    # Remove duplicates across all URLs
    unique_results = []
    seen_urls = set()
    for result in all_results:
        if result['url'] not in seen_urls:
            seen_urls.add(result['url'])
            unique_results.append(result)
    
    logger.info("Total unique Premier League items: %d", len(unique_results))
    return unique_results[:20]  # Return top 20

# --------------------------------------------------------------------
# FIFA NEWS SCRAPER
# --------------------------------------------------------------------
def scrape_fifa_news():
    """Scrape FIFA official news"""
    urls = [
        "https://www.fifa.com/fifaplus/en/articles",
        "https://www.fifa.com/fifaplus/en/news",
        "https://www.fifa.com/fifaplus/en/tournaments/mens/worldcup"
    ]
    
    logger.info("Scraping FIFA news...")
    all_results = []
    
    for url in urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # FIFA selectors
            selectors = [
                'a[href*="/articles/"]',
                'a[href*="/news/"]',
                '.article-card',
                '.news-item',
                '.content-item',
                '[data-testid*="article"]',
                '.fifa-article'
            ]
            
            articles = []
            for selector in selectors:
                found = soup.select(selector)
                articles.extend(found)
            
            seen_urls = set()
            for article in articles:
                try:
                    # Get URL
                    href = article.get('href', '')
                    if not href:
                        continue
                    
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                    
                    # Get title
                    title = ""
                    title_el = article.select_one('h1, h2, h3, h4, .title, .headline, .article-title')
                    if title_el:
                        title = title_el.get_text(strip=True)
                    
                    if not title:
                        # Try to get text content
                        title = article.get_text(strip=True)
                        if len(title) > 100:  # Too long, probably not a title
                            continue
                    
                    if not title or len(title) < 10:
                        continue
                    
                    # Construct full URL
                    if href.startswith('/'):
                        href = f"https://www.fifa.com{href}"
                    elif href.startswith('//'):
                        href = 'https:' + href
                    elif not href.startswith('http'):
                        continue
                    
                    # Extract summary
                    summary = ""
                    summary_el = article.select_one('p, .summary, .excerpt, .description')
                    if summary_el:
                        summary = summary_el.get_text(strip=True)
                    
                    # Extract image
                    image_url = None
                    img_el = article.select_one('img')
                    if img_el:
                        image_url = img_el.get('src') or img_el.get('data-src')
                        if image_url:
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            elif image_url.startswith('/'):
                                image_url = f"https://www.fifa.com{image_url}"
                    
                    results.append({
                        "title": title[:300],
                        "summary": summary[:500],
                        "url": href,
                        "image_url": image_url,
                        "source": "FIFA"
                    })
                    
                except Exception as e:
                    logger.debug("Error processing FIFA article: %s", e)
                    continue
            
            all_results.extend(results)
            logger.info("Found %d FIFA items from %s", len(results), url)
            
        except Exception as e:
            logger.error("FIFA scrape failed for %s: %s", url, e)
            continue
    
    # Remove duplicates
    unique_results = []
    seen_urls = set()
    for result in all_results:
        if result['url'] not in seen_urls:
            seen_urls.add(result['url'])
            unique_results.append(result)
    
    logger.info("Total unique FIFA items: %d", len(unique_results))
    return unique_results[:15]

# --------------------------------------------------------------------
# ESPN FC (SOCCER ONLY) - FIXED URL
# --------------------------------------------------------------------
def scrape_espn_fc():
    """Scrape ESPN FC soccer news - FIXED URL"""
    url = "https://www.espn.com/soccer/"
    logger.info("Scraping ESPN FC news...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # ESPN FC article selectors - updated
        articles = soup.select('.contentItem, .headlineStack__list-item, article, a[href*="/soccer/"]')
        
        for article in articles[:25]:  # Limit to first 25
            try:
                # ESPN specific structure
                title_el = article.select_one('a')
                if not title_el:
                    continue
                    
                title = title_el.get_text(strip=True)
                href = title_el.get('href', '')
                
                if not title or len(title) < 10:
                    continue
                    
                # Double-check for American football exclusion
                if any(af_kw in title.lower() for af_kw in AMERICAN_FOOTBALL_KEYWORDS):
                    continue
                    
                # Construct full URL if needed
                if href and href.startswith('/'):
                    href = f"https://www.espn.com{href}"
                elif not href.startswith('http'):
                    continue
                
                # Extract summary
                summary = ""
                summary_el = article.select_one('p')
                if summary_el:
                    summary = summary_el.get_text(strip=True)
                
                # Extract image
                image_url = None
                img_el = article.select_one('img')
                if img_el:
                    image_url = img_el.get('src') or img_el.get('data-src')
                    if image_url and image_url.startswith('//'):
                        image_url = 'https:' + image_url
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": href,
                    "image_url": image_url,
                    "source": "ESPN FC"
                })
                
            except Exception as e:
                logger.debug("Error processing ESPN FC article: %s", e)
                continue
                
    except Exception as e:
        logger.error("ESPN FC scrape failed: %s", e)
        return []
    
    logger.info("Found %d ESPN FC items", len(results))
    return results[:15]

# --------------------------------------------------------------------
# SKY SPORTS FOOTBALL - FIXED SELECTORS
# --------------------------------------------------------------------
def scrape_sky_sports():
    """Scrape Sky Sports Football news - FIXED SELECTORS"""
    url = "https://www.skysports.com/football/news"
    logger.info("Scraping Sky Sports Football news...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # Sky Sports selectors - updated
        articles = soup.select('.news-list__item, .article, .news-story, .site-layout__secondary-column a')
        
        for article in articles[:20]:
            try:
                title_el = article
                if article.select_one('h4, h3, h2'):
                    title_el = article.select_one('h4, h3, h2')
                
                title = title_el.get_text(strip=True)
                href = article.get('href', '') if article.name == 'a' else article.get('href', '')
                
                if not title or len(title) < 10:
                    continue
                
                # Construct full URL
                if href and href.startswith('/'):
                    href = f"https://www.skysports.com{href}"
                elif not href.startswith('http'):
                    continue
                
                # Extract summary
                summary = ""
                summary_el = article.select_one('p')
                if summary_el:
                    summary = summary_el.get_text(strip=True)
                
                # Extract image
                image_url = None
                img_el = article.select_one('img')
                if img_el:
                    image_url = img_el.get('src') or img_el.get('data-src')
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = f"https://www.skysports.com{image_url}"
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": href,
                    "image_url": image_url,
                    "source": "Sky Sports"
                })
                
            except Exception as e:
                logger.debug("Error processing Sky Sports article: %s", e)
                continue
                
    except Exception as e:
        logger.error("Sky Sports scrape failed: %s", e)
        return []
    
    logger.info("Found %d Sky Sports items", len(results))
    return results[:15]

# --------------------------------------------------------------------
# BBC SPORT FOOTBALL - FIXED SELECTORS
# --------------------------------------------------------------------
def scrape_bbc_sport():
    """Scrape BBC Sport Football news - FIXED SELECTORS"""
    url = "https://www.bbc.com/sport/football"
    logger.info("Scraping BBC Sport Football news...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # BBC Sport selectors - more comprehensive
        articles = soup.select('[data-testid*="card"], .gs-c-promo, .sp-c-promo, .ssrcss-1s51t2k, a[href*="/sport/football/"]')
        
        for article in articles[:25]:
            try:
                title_el = article.select_one('h2, h3, h4, [data-testid*="card-headline"]')
                if not title_el:
                    # If no title element, try to get text from the link itself
                    title_el = article
                
                title = title_el.get_text(strip=True)
                href = article.get('href', '')
                
                if not title or len(title) < 10 or "bbc.com" not in href:
                    continue
                
                # Construct full URL if needed
                if href.startswith('/'):
                    href = f"https://www.bbc.com{href}"
                
                # Extract summary
                summary = ""
                summary_el = article.select_one('p, [data-testid*="card-description"]')
                if summary_el:
                    summary = summary_el.get_text(strip=True)
                
                # Extract image
                image_url = None
                img_el = article.select_one('img')
                if img_el:
                    image_url = img_el.get('src') or img_el.get('data-src')
                    if image_url and image_url.startswith('//'):
                        image_url = 'https:' + image_url
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": href,
                    "image_url": image_url,
                    "source": "BBC Sport"
                })
                
            except Exception as e:
                logger.debug("Error processing BBC Sport article: %s", e)
                continue
                
    except Exception as e:
        logger.error("BBC Sport scrape failed: %s", e)
        return []
    
    logger.info("Found %d BBC Sport items", len(results))
    return results[:15]

# --------------------------------------------------------------------
# GOAL.COM - ADDITIONAL RELIABLE SOURCE
# --------------------------------------------------------------------
def scrape_goal_com():
    """Scrape Goal.com football news"""
    url = "https://www.goal.com/en/news"
    logger.info("Scraping Goal.com news...")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        # Goal.com selectors
        articles = soup.select('.widget-news-item, .news-item, article, a[href*="/en/news/"]')
        
        for article in articles[:20]:
            try:
                title_el = article.select_one('h3, h2, .title')
                if not title_el:
                    title_el = article
                
                title = title_el.get_text(strip=True)
                href = article.get('href', '')
                
                if not title or len(title) < 10:
                    continue
                    
                # Construct full URL if needed
                if href and href.startswith('/'):
                    href = f"https://www.goal.com{href}"
                elif not href.startswith('http'):
                    continue
                
                # Extract summary
                summary = ""
                summary_el = article.select_one('p, .excerpt')
                if summary_el:
                    summary = summary_el.get_text(strip=True)
                
                # Extract image
                image_url = None
                img_el = article.select_one('img')
                if img_el:
                    image_url = img_el.get('src') or img_el.get('data-src')
                    if image_url and image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url and image_url.startswith('/'):
                        image_url = f"https://www.goal.com{image_url}"
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": href,
                    "image_url": image_url,
                    "source": "Goal.com"
                })
                
            except Exception as e:
                logger.debug("Error processing Goal.com article: %s", e)
                continue
                
    except Exception as e:
        logger.error("Goal.com scrape failed: %s", e)
        return []
    
    logger.info("Found %d Goal.com items", len(results))
    return results[:15]

# --------------------------------------------------------------------
# DUPLICATE PREVENTION & OTHER FUNCTIONS (keep the same as before)
# --------------------------------------------------------------------
def get_recent_facebook_posts(hours=48):
    """Get recent posts from Facebook to check for duplicates"""
    try:
        # Facebook API to get recent posts - FIXED timestamp
        since_time = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
        
        url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/posts"
        params = {
            'access_token': FACEBOOK_ACCESS_TOKEN,
            'fields': 'message,created_time',
            'limit': 50,
            'since': since_time
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        else:
            logger.error("Failed to fetch Facebook posts: %s", response.text)
            return []
    except Exception as e:
        logger.error("Error fetching Facebook posts: %s", e)
        return []

def is_duplicate_post(title, summary, recent_posts):
    """Check if a post is duplicate by comparing with recent posts"""
    # Create a signature from title and summary
    signature = f"{title} {summary}".lower().strip()
    signature_words = set(signature.split()[:10])  # First 10 words as signature
    
    for post in recent_posts:
        post_message = post.get('message', '').lower()
        post_words = set(post_message.split()[:10])
        
        # Check for significant overlap
        common_words = signature_words.intersection(post_words)
        if len(common_words) >= 5:  # If 5+ common words in first 10 words
            logger.warning("⚠️ Potential duplicate detected: %s", title)
            return True
    
    return False

def get_scheduled_posts(session):
    """Get all scheduled posts that haven't been posted yet"""
    return session.query(FootballNews).filter(
        FootballNews.posted == False,
        FootballNews.scheduled_time.isnot(None)
    ).all()

def is_already_scheduled(session, title, url):
    """Check if a post is already scheduled"""
    scheduled_posts = get_scheduled_posts(session)
    
    for post in scheduled_posts:
        # Check title similarity
        existing_title = post.title.lower()
        new_title = title.lower()
        
        # Simple similarity check
        if (existing_title in new_title or new_title in existing_title or
            post.url == url):
            return True
    
    return False

def check_missing_images(articles):
    """Check for articles without images and log warnings"""
    articles_without_images = []
    
    for article in articles:
        image_url = article.get('image_url')
        if not image_url or image_url.strip() == '':
            articles_without_images.append({
                'title': article.get('title', 'No Title'),
                'url': article.get('url', 'No URL'),
                'source': article.get('source', 'Unknown Source')
            })
    
    if articles_without_images:
        logger.warning("🚨 ARTICLES WITHOUT IMAGES FOUND:")
        for article in articles_without_images:
            logger.warning("   - Title: %s", article['title'])
            logger.warning("     URL: %s", article['url'])
            logger.warning("     Source: %s", article['source'])
            logger.warning("     ---")
    
    return articles_without_images

# --------------------------------------------------------------------
# SCHEDULING LOGIC
# --------------------------------------------------------------------
def get_next_schedule_time(start_time=None, hour_interval=2):
    """Calculate next posting time with 2-hour gaps (as requested)"""
    if start_time is None:
        start_time = datetime.now(timezone.utc)
    
    # Round to next hour
    next_time = start_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    # Ensure it's at least 10 minutes ahead for Facebook
    if next_time < datetime.now(timezone.utc) + timedelta(minutes=10):
        next_time = datetime.now(timezone.utc) + timedelta(minutes=11)
        # Round to next hour
        next_time = next_time.replace(minute=0, second=0, microsecond=0)
    
    return next_time

def schedule_new_posts(session, dry_run=False):
    """Schedule posts with enhanced duplicate checking and image detection"""
    try:
        # Get unscheduled, non-posted articles
        unscheduled_posts = session.query(FootballNews).filter(
            FootballNews.posted == False,
            FootballNews.scheduled_time.is_(None)
        ).order_by(FootballNews.seq.asc()).all()
        
        if not unscheduled_posts:
            logger.info("No unscheduled posts found")
            return 0
            
        logger.info("Found %d unscheduled posts", len(unscheduled_posts))
        
        # Get recent Facebook posts for final duplicate check
        recent_posts = get_recent_facebook_posts()
        
        # Get the last scheduled time or use current time
        last_scheduled = session.query(FootballNews.scheduled_time).filter(
            FootballNews.scheduled_time.isnot(None)
        ).order_by(FootballNews.scheduled_time.desc()).first()
        
        if last_scheduled:
            next_time = last_scheduled[0] + timedelta(hours=2)  # 2-hour intervals
        else:
            next_time = get_next_schedule_time()
        
        # Ensure next_time is in future
        now = datetime.now(timezone.utc)
        if next_time <= now:
            next_time = get_next_schedule_time()
        
        scheduled_count = 0
        
        for post in unscheduled_posts:
            # Final duplicate check before scheduling
            if is_duplicate_post(post.title, post.summary or "", recent_posts):
                logger.warning("Skipping final duplicate: %s", post.title)
                continue
            
            # Create a good summary if empty
            summary = post.summary or f"Latest football news from {post.source}"
            if not summary and post.title:
                summary = f"Check out this new football update from {post.source}"
            
            # Prepare hashtags
            hashtags = get_hashtags_for_source(post.source)
            
            # Log if post has no image
            if not post.image_url:
                logger.warning("📸 Scheduling post WITHOUT IMAGE: %s", post.title)
            
            # Schedule Facebook post with image
            if not dry_run:
                result = post_to_facebook_scheduled(
                    title=post.title,
                    summary=summary,
                    hashtags=hashtags,
                    image_url=post.image_url,
                    link=post.url,
                    scheduled_time=next_time
                )
                
                if "id" in result:
                    if not post.image_url:
                        logger.warning("✅ Scheduled post WITHOUT IMAGE: %s for %s", post.title, next_time)
                    else:
                        logger.info("✅ Scheduled Facebook post with image: %s for %s", post.title, next_time)
                    # Mark as scheduled in database
                    post.scheduled_time = next_time
                else:
                    logger.error("❌ Failed to schedule Facebook post: %s", result.get("error", "Unknown error"))
            
            scheduled_count += 1
            
            # Move to next time slot (2-hour gap as requested)
            next_time = next_time + timedelta(hours=2)
        
        if not dry_run:
            session.commit()
        
        logger.info("Scheduled %d posts", scheduled_count)
        return scheduled_count
        
    except Exception as e:
        logger.error("Error scheduling posts: %s", e)
        if not dry_run:
            session.rollback()
        return 0
        
def get_hashtags_for_source(source):
    """Generate relevant hashtags based on source"""
    base_hashtags = "#Football #Soccer #FootyNews"
    if "Premier League" in source:
        return f"{base_hashtags} #PremierLeague #EPL"
    elif "ESPN" in source:
        return f"{base_hashtags} #ESPNFC"
    elif "Sky Sports" in source:
        return f"{base_hashtags} #SkySports #Football"
    elif "BBC" in source:
        return f"{base_hashtags} #BBCSport"
    elif "Goal" in source:
        return f"{base_hashtags} #GoalCom #FootballNews"
    elif "FIFA" in source:
        return f"{base_hashtags} #FIFA #WorldCup #International"
    else:
        return base_hashtags

# --------------------------------------------------------------------
# FACEBOOK INTEGRATION (keep the same as before)
# --------------------------------------------------------------------
def post_to_facebook_scheduled(title, summary, hashtags, image_url=None, link=None, scheduled_time=None):
    """
    Posts to Facebook Page feed with rich media - image + text, not just link sharing.
    Can be scheduled or published immediately.
    """
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        return {"error": "Facebook credentials not configured"}

    # Combine message with title and description
    message = f"{title}\n\n{summary}\n\n{hashtags}".strip()

    # Prepare scheduled time
    scheduled_timestamp = None
    if scheduled_time:
        try:
            if isinstance(scheduled_time, str):
                scheduled_dt = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
            else:
                scheduled_dt = scheduled_time

            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)

            now_utc = datetime.now(timezone.utc)

            # Facebook requires at least 10 minutes ahead
            if scheduled_dt < now_utc + timedelta(minutes=10):
                scheduled_dt = now_utc + timedelta(minutes=11)

            scheduled_timestamp = int(scheduled_dt.timestamp())

        except Exception as e:
            return {"error": f"Invalid scheduled_time: {str(e)}"}

    # If we have an image URL, download and upload it
    if image_url:
        try:
            # Download the image
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                # Create a temporary file
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    temp_file.write(response.content)
                    temp_image_path = temp_file.name

                # Upload image to Facebook
                photo_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"
                
                with open(temp_image_path, "rb") as img:
                    files = {"source": img}
                    photo_res = requests.post(
                        photo_url,
                        params={
                            "published": "false",
                            "access_token": FACEBOOK_ACCESS_TOKEN,
                        },
                        files=files,
                    )

                # Clean up temp file
                os.unlink(temp_image_path)

                photo_data = photo_res.json()

                if "id" in photo_data:
                    # Post with attached image
                    post_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
                    payload = {
                        "message": message,
                        "access_token": FACEBOOK_ACCESS_TOKEN,
                        "attached_media": json.dumps([{"media_fbid": photo_data["id"]}])
                    }

                    # Add scheduling if needed
                    if scheduled_timestamp:
                        payload["published"] = "false"
                        payload["scheduled_publish_time"] = scheduled_timestamp
                    else:
                        payload["published"] = "true"

                    response = requests.post(post_url, data=payload)
                    result = response.json()
                    
                    result["debug_info"] = {
                        "scheduled_time_final": scheduled_timestamp,
                        "message": message,
                        "published": payload.get("published"),
                        "has_image": True
                    }
                    
                    return result
                else:
                    return {
                        "error": "Failed to upload image to Facebook",
                        "details": photo_data
                    }
            else:
                logger.warning(f"Failed to download image from {image_url}, falling back to text post")
        except Exception as e:
            logger.warning(f"Image processing failed: {e}, falling back to text post")

    # Fallback: Simple text post with link in message
    if link:
        message += f"\n\nRead more: {link}"

    # Prepare payload for text post
    post_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
    payload = {
        "message": message,
        "access_token": FACEBOOK_ACCESS_TOKEN,
    }

    # Determine if it's scheduled or immediate
    if scheduled_timestamp:
        payload["published"] = "false"
        payload["scheduled_publish_time"] = scheduled_timestamp
    else:
        payload["published"] = "true"

    # Send post request
    response = requests.post(post_url, data=payload)
    try:
        data = response.json()
    except Exception:
        data = {"error": "Invalid JSON response", "raw": response.text}

    data["debug_info"] = {
        "scheduled_time_final": scheduled_timestamp,
        "message": message,
        "published": payload.get("published"),
        "has_image": False
    }

    return data

# --------------------------------------------------------------------
# DB INSERTION (keep the same as before)
# --------------------------------------------------------------------
def get_existing_urls(session):
    """Get all existing URLs to avoid duplicates"""
    existing = session.query(FootballNews.url).filter(FootballNews.url.isnot(None)).all()
    return set(url for (url,) in existing)

def get_existing_hashes(session):
    """Get all existing hashes to avoid duplicates"""
    existing = session.query(FootballNews.hash).filter(FootballNews.hash.isnot(None)).all()
    return set(h for (h,) in existing)

def insert_articles(session, articles, dry_run=False):
    inserted = []
    if not articles:
        return inserted

    # Get existing data once (more efficient)
    existing_urls = get_existing_urls(session)
    existing_hashes = get_existing_hashes(session)
    
    if not isinstance(results, list):
        logger.error(f"Scraper {source_name} returned non-list: {type(results)}")
        results = []
        
    normalized = [normalize_article(a) for a in articles]
    filtered = [a for a in normalized if looks_like_football(a["title"], a["summary"], a["url"])]

    logger.info("After football filter: %d items", len(filtered))

    to_insert = []
    for a in filtered:
        h = sha256_hex(a["title"] + "||" + a["summary"])
        a["hash"] = h

        # Check both URL and hash for duplicates
        if a["url"] and a["url"] in existing_urls:
            continue
        if h in existing_hashes:
            continue

        to_insert.append(a)
        # Add to existing sets to avoid duplicates in this batch
        if a["url"]:
            existing_urls.add(a["url"])
        existing_hashes.add(h)

    if not to_insert:
        logger.info("No new items to insert.")
        return inserted

    max_seq = get_max_seq(session)
    next_seq = max_seq + 1

    for a in to_insert:
        row = FootballNews(
            title=a["title"],
            summary=a["summary"],
            url=a["url"],
            image_url=a["image_url"],
            source=a["source"],
            published_at=datetime.now(timezone.utc),
            seq=next_seq,
            posted=False,
            hash=a["hash"],
            created_at=datetime.now(timezone.utc)
        )

        if not dry_run:
            session.add(row)

        inserted.append({
            "seq": next_seq,
            "title": a["title"],
            "url": a["url"],
            "source": a["source"]
        })

        next_seq += 1

    if not dry_run:
        session.commit()
        logger.info("Committed %d new rows", len(inserted))

    return inserted

def get_max_seq(session):
    r = session.execute(db.select(db.func.max(FootballNews.seq))).scalar()
    return int(r) if r else 0

# --------------------------------------------------------------------
# MAIN RUNNER - UPDATED WITH FIFA
# --------------------------------------------------------------------
def run_scraper(dry_run=False):
    logger.info("Starting football scraper (dry_run=%s)", dry_run)
    all_articles = []

    # Scrape all football sources
    try:
        results = scrape_premier_league()
        all_articles.extend(results)
        logger.info("Premier League: %d articles", len(results))
    except Exception as e:
        logger.exception("Premier League failed: %s", e)

    try:
        results = scrape_fifa_news()
        all_articles.extend(results)
        logger.info("FIFA: %d articles", len(results))
    except Exception as e:
        logger.exception("FIFA failed: %s", e)

    try:
        results = scrape_espn_fc()
        all_articles.extend(results)
        logger.info("ESPN FC: %d articles", len(results))
    except Exception as e:
        logger.exception("ESPN FC failed: %s", e)

    try:
        results = scrape_sky_sports()
        all_articles.extend(results)
        logger.info("Sky Sports: %d articles", len(results))
    except Exception as e:
        logger.exception("Sky Sports failed: %s", e)

    try:
        results = scrape_bbc_sport()
        all_articles.extend(results)
        logger.info("BBC Sport: %d articles", len(results))
    except Exception as e:
        logger.exception("BBC Sport failed: %s", e)

    try:
        results = scrape_goal_com()
        all_articles.extend(results)
        logger.info("Goal.com: %d articles", len(results))
    except Exception as e:
        logger.exception("Goal.com failed: %s", e)

    logger.info("Total scraped candidate articles: %d", len(all_articles))

    # Enhanced missing image detection
    missing_images = check_missing_images(all_articles)
    if missing_images:
        logger.warning("🚨 Found %d articles without images that need manual attention", len(missing_images))
        logger.warning("📋 Visit http://your-domain.com/admin/posts-without-images to add images")
        for article in missing_images:
            logger.warning("   - %s: %s", article['title'], article['url'])

    with app.app_context():
        session = db.session
        db.create_all()

        # Get recent Facebook posts and scheduled posts for duplicate checking
        recent_posts = get_recent_facebook_posts()
        logger.info("Fetched %d recent Facebook posts for duplicate checking", len(recent_posts))

        # Filter out potential duplicates before insertion
        filtered_articles = []
        for article in all_articles:
            # Check against recent Facebook posts
            if is_duplicate_post(article['title'], article.get('summary', ''), recent_posts):
                logger.warning("Skipping potential duplicate: %s", article['title'])
                continue
            
            # Check against already scheduled posts
            if is_already_scheduled(session, article['title'], article['url']):
                logger.warning("Skipping already scheduled post: %s", article['title'])
                continue
            
            filtered_articles.append(article)

        logger.info("After duplicate filtering: %d articles remaining", len(filtered_articles))

        # Insert new articles
        inserted = insert_articles(session, filtered_articles, dry_run=dry_run)
        logger.info("Inserted %d new records", len(inserted))

        # Schedule posts
        scheduled_count = schedule_new_posts(session, dry_run=dry_run)
        logger.info("Scheduled %d posts", scheduled_count)

        # Final report with admin link
        missing_count = len([p for p in inserted if not p.get('image_url')])
        if missing_count > 0 and not dry_run:
            logger.warning("📋 ADMIN: %d new posts need images. Visit: /admin/posts-without-images", missing_count)

        if dry_run:
            for i in inserted:
                logger.info("DRY: seq=%s title=%s url=%s", i["seq"], i["title"], i["url"])

    logger.info("Football scraper run complete.")
    
# --------------------------------------------------------------------
# WORKER FUNCTION
# --------------------------------------------------------------------
def run_worker(interval_hours=2):
    """
    Run scraper in continuous worker mode (2-hour intervals as requested)
    """
    logger.info("🚀 Starting football scraper worker (interval: %s hours)", interval_hours)
    interval_seconds = interval_hours * 3600
    
    while True:
        try:
            # Run one scrape cycle
            logger.info("🔄 Starting football scrape cycle...")
            run_scraper(dry_run=False)
            logger.info("✅ Football scrape cycle completed successfully")
            
        except Exception as e:
            logger.error("❌ Football scrape cycle failed: %s", e)
        
        # Wait for next cycle
        logger.info("⏰ Waiting %s hours until next run...", interval_hours)
        time.sleep(interval_seconds)

# --------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Football News Scraper")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB or schedule posts")
    parser.add_argument("--worker", action="store_true", help="Run in continuous worker mode")
    parser.add_argument("--interval", type=int, default=2, help="Worker interval in hours (default: 2)")
    
    args = parser.parse_args()

    if args.worker:
        # Run as continuous worker
        run_worker(interval_hours=args.interval)
    else:
        # Run once
        run_scraper(dry_run=args.dry_run)