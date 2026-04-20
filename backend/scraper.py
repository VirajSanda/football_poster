"""
Cron-ready scraper for football news with built-in Facebook scheduling
Supports both images and videos for Facebook posts
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
import pytz
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Facebook Config (add to your .env)
FACEBOOK_PAGE_ID = Config.FACEBOOK_PAGE_ID
FACEBOOK_ACCESS_TOKEN = Config.FACEBOOK_ACCESS_TOKEN

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("football-scraper")

# Helpers
def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

POST_GAP_HOURS = int(os.environ.get("POST_GAP_HOURS", 2)) 

# Football keywords (SOCCER ONLY - excluding American football)
FOOTBALL_KEYWORDS = [
    "premier league", "premierleague", "epl", "english premier league",
    "la liga", "laliga", "serie a", "seriea", "bundesliga", 
    "champions league", "europa league", "europa conference", "uefa",
    "world cup", "euro", "euros", "euro2024", "euro 2024",
    "transfer", "signing",
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
    "quiz", "?", "Latest Transfer News", "Transfer Rumours", 
    "Latest football news from Premier League", "Tickets"
]

def clean_url(url):
    return url.split("?")[0].strip()

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
        "url": clean_url(item.get("url")),
        "image_url": (item.get("image_url") or "").strip() if item.get("image_url") else None,
        "video_url": (item.get("video_url") or "").strip() if item.get("video_url") else None,
        "source": (item.get("source") or "").strip(),
    }

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# --------------------------------------------------------------------
# PREMIER LEAGUE OFFICIAL API
# --------------------------------------------------------------------
def fetch_premier_league_api():
    """Fetch Premier League content from official API"""
    logger.info("Fetching Premier League API...")
    
    # API configurations for different content types
    api_configs = [
        {
            "name": "general",
            "url": "https://api.premierleague.com/content/premierleague/en",
            "params": {
                "contentTypes": "TEXT,VIDEO",
                "offset": 0,
                "limit": 15,
                "onlyRestrictedContent": "false",
                "detail": "DETAILED"
            }
        },
        {
            "name": "fantasy",
            "url": "https://api.premierleague.com/content/premierleague/en",
            "params": {
                "contentTypes": "TEXT",
                "offset": 0,
                "limit": 10,
                "onlyRestrictedContent": "false",
                "tagNames": "label:Fantasy%20Premier%20League",
                "detail": "DETAILED"
            }
        },
        {
            "name": "youth",
            "url": "https://api.premierleague.com/content/premierleague/en",
            "params": {
                "contentTypes": "TEXT",
                "offset": 0,
                "limit": 10,
                "onlyRestrictedContent": "false",
                "tagNames": "label:Youth",
                "detail": "DETAILED"
            }
        }
    ]
    
    all_results = []
    
    for config in api_configs:
        try:
            response = requests.get(
                config["url"],
                params=config["params"],
                headers=HEADERS,
                timeout=15
            )
            response.raise_for_status()
            
            data = response.json()
            results = _process_api_data(data, config["name"])
            all_results.extend(results)
            
            logger.info("Found %d Premier League API items from %s", len(results), config["name"])
            
        except Exception as e:
            logger.error("Premier League API fetch failed for %s: %s", config["name"], e)
            continue
    
    # Remove duplicates
    unique_results = _deduplicate_api_results(all_results)
    logger.info("Total unique Premier League API items: %d", len(unique_results))
    
    return unique_results[:20]  # Return top 20
    
# --------------------------------------------------------------------
# PREMIER LEAGUE OFFICIAL SITE - IMPROVED VERSION
# --------------------------------------------------------------------

def _process_api_data(data: Dict, source_name: str) -> List[Dict]:
    """Process API JSON response into normalized articles"""
    results = []
    
    if not data or "content" not in data:
        return results
    
    for item in data.get("content", []):
        try:
            # Only process text content
            if item.get("type") != "text":
                continue
            
            # Extract and normalize fields
            title = (item.get("title") or "").strip()
            summary = (item.get("summary") or item.get("description") or "").strip()
            
            # Skip if title too short
            if len(title) < 10:
                continue
            
            # Check if football content using your existing function
            if not looks_like_football(title, summary, ""):
                continue
            
            # Get URL
            url = item.get("hotlinkUrl", "")
            if not url and item.get("titleUrlSegment"):
                url = f"https://www.premierleague.com/news/{item['titleUrlSegment']}"
            
            if not url:
                continue
            
            # Get image URL
            image_url = None
            if item.get("leadMedia"):
                image_url = item.get("leadMedia", {}).get("url")
            if not image_url:
                image_url = item.get("imageUrl")
            
            # Get video URL if available
            video_url = item.get("onDemandUrl")
            
            # Create normalized article using your existing function
            article_data = {
                "title": title[:300],
                "summary": summary[:500],
                "url": url,
                "image_url": image_url,
                "video_url": video_url,
                "source": f"Premier League ({source_name.title()})"
            }
            
            normalized_article = normalize_article(article_data)
            results.append(normalized_article)
            
        except Exception as e:
            logger.debug("Error processing Premier League API item: %s", e)
            continue
    
    return results

def _deduplicate_api_results(results: List[Dict]) -> List[Dict]:
    """Remove duplicate API results by URL"""
    seen_urls = set()
    unique_results = []
    
    for result in results:
        url = result.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(result)
    
    return unique_results

# --------------------------------------------------------------------
# ENHANCED MAIN FUNCTION (combines API and scraping)
# --------------------------------------------------------------------
def scrape_premier_league_enhanced() -> List[Dict]:
    """
    Enhanced Premier League scraper that combines:
    1. Web scraping (your existing method)
    2. Official API (new method)
    
    Returns: List of normalized article dictionaries
    """
    all_articles = []
    
    logger.info("Starting enhanced Premier League content collection...")
    
    # 2. Get content from official API (new method)
    try:
        api_articles = fetch_premier_league_api()
        logger.info("Fetched %d articles from API", len(api_articles))
        all_articles.extend(api_articles)
    except Exception as e:
        logger.error("API fetching failed: %s", e)
    
    # 3. Remove duplicates across both sources
    unique_articles = _remove_all_duplicates(all_articles)
    
    # 4. Check for missing media
    check_missing_media(unique_articles)
    
    logger.info("Enhanced collection complete: %d unique articles", len(unique_articles))
    return unique_articles[:30]  # Return top 30

def _remove_all_duplicates(articles: List[Dict]) -> List[Dict]:
    """Remove duplicates by URL and title similarity"""
    seen_urls = set()
    seen_titles = set()
    unique_articles = []
    
    for article in articles:
        url = article.get("url", "")
        title = article.get("title", "").lower().strip()
        
        # Check both exact URL and title similarity
        is_duplicate = False
        
        # Check URL
        if url in seen_urls:
            is_duplicate = True
        
        # Check title similarity (first 5 words)
        title_words = set(title.split()[:5])
        for seen_title in seen_titles:
            seen_words = set(seen_title.split()[:5])
            common_words = title_words.intersection(seen_words)
            if len(common_words) >= 3:  # 3+ common words in first 5
                is_duplicate = True
                break
        
        if not is_duplicate:
            seen_urls.add(url)
            seen_titles.add(title)
            unique_articles.append(article)
    
    return unique_articles

# --------------------------------------------------------------------
# FIFA NEWS SCRAPER - ENHANCED WITH API
# --------------------------------------------------------------------
def scrape_fifa_news():
    """Scrape FIFA official news using FIFA+ CXM API (hardened & production-safe)"""
    logger.info("Scraping FIFA news via API...")

    API_ENDPOINTS = [
        {
            "name": "fifa_news",
            "url": "https://cxm-api.fifa.com/fifaplusweb/api/sections/news/1aQDyhkYnKhkAW347zYi4Y",
            "params": {"locale": "en", "limit": 16},
            "paginated": True
        },
        {
            "name": "fifa_promo",
            "url": "https://cxm-api.fifa.com/fifaplusweb/api/sections/promoCarousel/5Gsmpd2GqyvT2CmXv2aBb7",
            "params": {"locale": "en"},
            "paginated": False
        },
        {
            "name": "fifa_more_news",
            "url": "https://cxm-api.fifa.com/fifaplusweb/api/sections/news/2lsGSGYOtykcJRJQu7bdDg",
            "params": {"locale": "en", "limit": 20},
            "paginated": True
        }
    ]

    MAX_PAGES = 2
    all_results = []

    for endpoint in API_ENDPOINTS:
        pages = MAX_PAGES if endpoint["paginated"] else 1

        for page in range(pages):
            try:
                params = endpoint["params"].copy()
                if endpoint["paginated"]:
                    params["skip"] = page * params.get("limit", 16)

                response = requests.get(
                    endpoint["url"],
                    params=params,
                    headers=HEADERS,
                    timeout=15
                )
                response.raise_for_status()

                data = response.json()
                results = _process_fifa_api_data(data, endpoint["name"])
                all_results.extend(results)

                logger.info(
                    "FIFA %s page %d: %d items",
                    endpoint["name"],
                    page + 1,
                    len(results)
                )

                if not results:
                    break  # stop pagination early

            except Exception as e:
                logger.error(
                    "FIFA API fetch failed (%s page %d): %s",
                    endpoint["name"],
                    page + 1,
                    e
                )
                break

    # De-duplicate results
    seen_urls = set()
    seen_titles = set()
    unique_results = []

    for article in all_results:
        url = article.get("url", "").strip()
        title = article.get("title", "").lower().strip()

        if not url or not title:
            continue

        if url in seen_urls or title in seen_titles:
            continue

        seen_urls.add(url)
        seen_titles.add(title)
        unique_results.append(article)

    logger.info("Total unique FIFA items: %d", len(unique_results))
    return unique_results[:15]

def _process_fifa_api_data(data: Dict, source_name: str) -> List[Dict]:
    """Normalize FIFA API responses (news + promoCarousel compatible)"""
    results = []

    if not isinstance(data, dict):
        return results

    # Handle schema differences
    if source_name == "fifa_promo":
        items = data.get("slides", [])
    else:
        items = data.get("items", [])

    if not isinstance(items, list):
        return results

    for item in items:
        try:
            title = (item.get("title") or "").strip()
            if len(title) < 5:
                continue

            summary = (
                item.get("previewText")
                or item.get("summary")
                or item.get("description")
                or ""
            ).strip()

            article_page_url = item.get("articlePageUrl")
            slug = item.get("slug")

            url = None
            if article_page_url:
                url = (
                    f"https://www.fifa.com{article_page_url}"
                    if article_page_url.startswith("/")
                    else article_page_url
                )
            elif slug:
                url = f"https://www.fifa.com/fifaplus/en/articles/{slug}"

            if not url:
                continue

            image_url = _extract_fifa_image(item)

            if not looks_like_football(title, summary, url):
                continue

            article = normalize_article({
                "title": title[:300],
                "summary": summary[:500],
                "url": url,
                "image_url": image_url,
                "video_url": None,
                "source": "FIFA"
            })

            results.append(article)

        except Exception as e:
            logger.debug("FIFA item processing error: %s", e)

    return results

def _extract_fifa_image(item: Dict) -> str | None:
    """Extract FIFA image URL across all known schema variations"""
    image = item.get("image")
    if isinstance(image, dict):
        return image.get("src") or image.get("url")

    images = item.get("images")
    if isinstance(images, list) and images:
        return images[0].get("src")

    hero = item.get("heroImage")
    if isinstance(hero, dict):
        return hero.get("src")

    return None

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
        articles = soup.select('section.contentItem')
        
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
                
                # Extract video
                video_url = None
                video_el = article.select_one('video, iframe[src*="youtube"], iframe[src*="vimeo"]')
                if video_el:
                    video_url = video_el.get('src') or video_el.get('data-src')
                    if video_url and video_url.startswith('//'):
                        video_url = 'https:' + video_url
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": href,
                    "image_url": image_url,
                    "video_url": video_url,
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
        articles = soup.select('.news-list__item')
        
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
                
                # Extract video
                video_url = None
                video_el = article.select_one('video, iframe[src*="youtube"], iframe[src*="vimeo"]')
                if video_el:
                    video_url = video_el.get('src') or video_el.get('data-src')
                    if video_url:
                        if video_url.startswith('//'):
                            video_url = 'https:' + video_url
                        elif video_url.startswith('/'):
                            video_url = f"https://www.skysports.com{video_url}"
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": href,
                    "image_url": image_url,
                    "video_url": video_url,
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
        articles = soup.select('[data-testid="card"]')
        
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
                
                # Extract video
                video_url = None
                video_el = article.select_one('video, iframe[src*="youtube"], iframe[src*="vimeo"]')
                if video_el:
                    video_url = video_el.get('src') or video_el.get('data-src')
                    if video_url and video_url.startswith('//'):
                        video_url = 'https:' + video_url
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": href,
                    "image_url": image_url,
                    "video_url": video_url,
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
                
                # Extract video
                video_url = None
                video_el = article.select_one('video, iframe[src*="youtube"], iframe[src*="vimeo"]')
                if video_el:
                    video_url = video_el.get('src') or video_el.get('data-src')
                    if video_url:
                        if video_url.startswith('//'):
                            video_url = 'https:' + video_url
                        elif video_url.startswith('/'):
                            video_url = f"https://www.goal.com{video_url}"
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": href,
                    "image_url": image_url,
                    "video_url": video_url,
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
# DUPLICATE PREVENTION & OTHER FUNCTIONS
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

def is_duplicate_post(title, summary, recent_posts, check_url=None):
    """Enhanced duplicate check using URL, title, and content signature."""
    # If we have a URL, check if it was already posted
    if check_url:
        for post in recent_posts:
            if check_url in post.get('message', ''):
                return True

    # Create a signature from title and summary
    signature = f"{title} {summary}".lower().strip()
    signature_words = set(re.findall(r'\b\w+\b', signature))  # word tokens
    signature_words = {w for w in signature_words if len(w) > 3}  # ignore short words

    for post in recent_posts:
        post_message = post.get('message', '').lower()
        post_words = set(re.findall(r'\b\w+\b', post_message))
        common = len(signature_words.intersection(post_words))
        total = len(signature_words.union(post_words))
        similarity = common / total if total > 0 else 0
        if similarity > 0.6:   # 60% word overlap
            logger.warning("⚠️ Potential duplicate detected: %s", title)
            return True
    return False

def is_valid_article(a):
    if not a["title"] or len(a["title"]) < 15:
        return False
    
    if not a["url"] or not a["url"].startswith("http"):
        return False
    
    # avoid junk titles
    bad_patterns = ["click here", "read more", "subscribe", "sign up"]
    if any(bp in a["title"].lower() for bp in bad_patterns):
        return False
    
    return True

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

def check_missing_media(articles):
    """Check for articles without images/videos and log warnings"""
    articles_without_media = []
    
    for article in articles:
        image_url = article.get('image_url')
        video_url = article.get('video_url')
        if (not image_url or image_url.strip() == '') and (not video_url or video_url.strip() == ''):
            articles_without_media.append({
                'title': article.get('title', 'No Title'),
                'url': article.get('url', 'No URL'),
                'source': article.get('source', 'Unknown Source')
            })
    
    return articles_without_media

# --------------------------------------------------------------------
# SCHEDULING LOGIC
# --------------------------------------------------------------------
def get_next_schedule_time():
    """Get the next schedule time (make sure it's timezone aware)"""
    now = datetime.now(timezone.utc)
    return (now + timedelta(minutes=15)).replace(second=0, microsecond=0)


def _parse_db_timestamp(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    return None


def acquire_schedule_lock(session, lock_name="schedule_posts_lock", timeout_minutes=60):
    """Acquire an advisory lock using a database table (works with SQLite/PostgreSQL)."""
    # Create the lock table if it doesn't exist
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS schedule_lock (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            locked BOOLEAN NOT NULL DEFAULT FALSE,
            locked_at TIMESTAMP
        )
    """))
    session.commit()
    
    # Detect database type
    db_dialect = session.get_bind().dialect.name if hasattr(session, 'get_bind') else 'sqlite'
    
    # Insert initial row using dialect-appropriate syntax
    if db_dialect == 'postgresql':
        session.execute(text("""
            INSERT INTO schedule_lock (id, locked) 
            VALUES (1, FALSE)
            ON CONFLICT (id) DO NOTHING
        """))
    else:  # SQLite
        session.execute(text("INSERT OR IGNORE INTO schedule_lock (id, locked) VALUES (1, FALSE)"))
    
    session.commit()

    # Try to acquire the lock
    res = session.execute(text("""
        UPDATE schedule_lock
        SET locked = TRUE, locked_at = CURRENT_TIMESTAMP
        WHERE id = 1 AND locked = FALSE
    """))
    session.commit()
    if res.rowcount == 1:
        return True

    # If there is an existing lock, check whether it is stale.
    row = session.execute(text("SELECT locked_at FROM schedule_lock WHERE id = 1")).fetchone()
    if row and row[0]:
        locked_at = _parse_db_timestamp(row[0])
        if locked_at:
            if locked_at.tzinfo is None:
                locked_at = locked_at.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now - locked_at > timedelta(minutes=timeout_minutes):
                logger.warning("Stale schedule lock detected (locked_at=%s). Reclaiming...", locked_at.isoformat())
                res = session.execute(text("""
                    UPDATE schedule_lock
                    SET locked = TRUE, locked_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                """))
                session.commit()
                return res.rowcount == 1

    return False


def release_schedule_lock(session):
    session.execute(text("UPDATE schedule_lock SET locked = FALSE, locked_at = NULL WHERE id = 1"))
    session.commit()

def schedule_new_posts(session, dry_run=False):
    """Schedule posts with consistent gap (POST_GAP_HOURS) and atomic commits."""
    if not dry_run:
        # Acquire lock to prevent concurrent scheduling
        if not acquire_schedule_lock(session):
            logger.warning("Another scheduling process is already running. Exiting.")
            return 0

    try:
        # Get unscheduled, non-posted articles (ordered by seq)
        unscheduled_posts = session.query(FootballNews).filter(
            FootballNews.posted == False,
            FootballNews.scheduled_time.is_(None)
        ).order_by(FootballNews.seq.asc()).all()

        if not unscheduled_posts:
            logger.info("No unscheduled posts found")
            return 0

        logger.info("Found %d unscheduled posts", len(unscheduled_posts))

        # Get recent Facebook posts for duplicate check
        recent_posts = get_recent_facebook_posts()

        # Find the latest scheduled_time (any post, not necessarily posted yet)
        last_scheduled = session.query(FootballNews.scheduled_time).filter(
            FootballNews.scheduled_time.isnot(None)
        ).order_by(FootballNews.scheduled_time.desc()).first()

        now_utc = datetime.now(timezone.utc)

        if last_scheduled:
            last_time = ensure_timezone_aware(last_scheduled[0])
            # Ensure at least POST_GAP_HOURS after the last scheduled post
            next_time = last_time + timedelta(hours=POST_GAP_HOURS)
            # If that time is already in the past, start from now + gap
            if next_time <= now_utc:
                next_time = now_utc + timedelta(hours=POST_GAP_HOURS)
        else:
            # No existing schedules: start from now + gap
            next_time = now_utc + timedelta(hours=POST_GAP_HOURS)

        # Round up to the nearest minute (optional, avoids millisecond collisions)
        next_time = next_time.replace(second=0, microsecond=0)

        scheduled_count = 0
        seen_titles_in_this_batch = set()

        for post in unscheduled_posts:
            # 1. Check duplicate within this batch (title similarity)
            current_title_lower = post.title.lower().strip()
            is_duplicate_in_batch = any(
                calculate_title_similarity(current_title_lower, seen_title) > 0.8
                for seen_title in seen_titles_in_this_batch
            )
            if is_duplicate_in_batch:
                logger.warning("⚠️ Skipping duplicate in same batch: %s", post.title[:50])
                continue

            # 2. Check against recent Facebook posts
            if is_duplicate_post(post.title, post.summary or "", recent_posts, post.url):
                logger.warning("Skipping final duplicate: %s", post.title)
                continue

            # 3. Check against already scheduled posts (including those scheduled in this run)
            if is_already_scheduled(session, post.title, post.url):
                logger.warning("Skipping already scheduled: %s", post.title)
                continue

            seen_titles_in_this_batch.add(current_title_lower)

            # Prepare hashtags and media
            hashtags = get_hashtags_for_source(post.source)

            if post.video_url:
                logger.info("🎥 Post has video: %s", post.title)
            elif not post.image_url:
                logger.warning("📸 Scheduling post WITHOUT MEDIA: %s", post.title)

            if not dry_run:
                # Schedule on Facebook
                result = post_to_facebook_scheduled(
                    title=post.title,
                    summary="",
                    hashtags=hashtags,
                    image_url=post.image_url,
                    video_url=post.video_url,
                    link=post.url,
                    scheduled_time=next_time
                )

                if "id" in result:
                    final_scheduled_timestamp = (
                        result.get("debug_info", {}).get("scheduled_time_final")
                        if isinstance(result, dict) else None
                    )
                    final_scheduled_time = (
                        datetime.fromtimestamp(final_scheduled_timestamp, tz=timezone.utc)
                        if final_scheduled_timestamp else next_time
                    )
                    # IMPORTANT: persist the scheduled_time immediately
                    post.scheduled_time = final_scheduled_time
                    session.commit()   # commit after each post to avoid race conditions
                    scheduled_count += 1
                    logger.info("✅ Scheduled %s: %s at %s",
                                "video" if post.video_url else "post",
                                post.title[:50], final_scheduled_time)
                else:
                    logger.error("❌ Failed to schedule: %s - %s",
                                 post.title[:50], result.get("error", "Unknown error"))
                    # Do NOT commit; this post remains unscheduled and will be retried later
            else:
                # Dry run: just log
                scheduled_count += 1
                logger.info("DRY: would schedule %s at %s", post.title[:50], next_time)

            # Advance to next time slot (ensure unique timestamps)
            next_time = next_time + timedelta(hours=POST_GAP_HOURS)

        logger.info("Scheduled %d posts", scheduled_count)
        return scheduled_count

    except Exception as e:
        logger.error("Error scheduling posts: %s", e, exc_info=True)
        if not dry_run:
            session.rollback()
        return 0
    finally:
        if not dry_run:
            release_schedule_lock(session)
                 
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

def ensure_timezone_aware(dt_obj):
    """Ensure datetime object is timezone aware (UTC)"""
    if dt_obj is None:
        return None
    if dt_obj.tzinfo is None:
        return dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj


def normalize_scheduled_time_for_facebook(scheduled_time):
    """Clamp scheduled publish times into Facebook's accepted UTC window."""
    if not scheduled_time:
        return None, None

    if isinstance(scheduled_time, str):
        scheduled_dt = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
    else:
        scheduled_dt = scheduled_time

    scheduled_dt = ensure_timezone_aware(scheduled_dt).astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)
    min_publish_time = now_utc + timedelta(minutes=11)
    max_publish_time = now_utc + timedelta(days=75) - timedelta(minutes=1)

    if scheduled_dt < min_publish_time:
        scheduled_dt = min_publish_time
    elif scheduled_dt > max_publish_time:
        scheduled_dt = max_publish_time

    scheduled_dt = scheduled_dt.replace(second=0, microsecond=0)
    return scheduled_dt, int(scheduled_dt.timestamp())
    

def is_probably_video_url(url: str) -> bool:
    """Heuristic to avoid treating image asset URLs as videos."""
    if not url or not isinstance(url, str):
        return False
    lower_url = url.lower()
    if any(lower_url.endswith(ext) for ext in ('.mp4', '.mov', '.webm', '.m3u8', '.flv', '.avi')):
        return True
    if 'youtube.com' in lower_url or 'youtu.be' in lower_url or 'vimeo.com' in lower_url:
        return True
    if 'facebook.com' in lower_url and '/videos/' in lower_url:
        return True
    return False

# --------------------------------------------------------------------
# FACEBOOK INTEGRATION - UPDATED FOR VIDEO SUPPORT
# --------------------------------------------------------------------
def post_to_facebook_scheduled(title, summary, hashtags, image_url=None, video_url=None, link=None, scheduled_time=None):
    """
    Posts to Facebook Page feed with rich media - image/video + text, not just link sharing.
    Can be scheduled or published immediately.
    """
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        return {"error": "Facebook credentials not configured"}

    # Combine message with title and description
    message = f"{title}\n\n{hashtags}".strip()

    # Prepare scheduled time
    scheduled_timestamp = None
    scheduled_timestamp_unix = None
    scheduled_dt = None
    if scheduled_time:
        try:
            scheduled_dt, scheduled_timestamp_unix = normalize_scheduled_time_for_facebook(scheduled_time)
            scheduled_timestamp = scheduled_timestamp_unix
        except Exception as e:
            return {"error": f"Invalid scheduled_time: {str(e)}"}

    # If we have a VIDEO URL, upload it as video (priority over image)
    if video_url and is_probably_video_url(video_url):
        try:
            logger.info(f"📹 Processing video from {video_url}")
            
            response = requests.get(video_url, timeout=30, stream=True)
            if response.status_code == 200:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                    temp_video_path = temp_file.name

                video_upload_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/videos"
                
                with open(temp_video_path, "rb") as video_file:
                    files = {"source": video_file}
                    params = {
                        "description": message,
                        "access_token": FACEBOOK_ACCESS_TOKEN,
                    }
                    
                    if scheduled_timestamp_unix:
                        params["published"] = "false"
                        params["scheduled_publish_time"] = scheduled_timestamp_unix
                    else:
                        params["published"] = "true"

                    response = requests.post(video_upload_url, params=params, files=files)
                
                os.unlink(temp_video_path)

                result = response.json()
                
                if "id" in result:
                    logger.info("✅ Successfully scheduled video post")
                    result["debug_info"] = {
                        "scheduled_time_final": scheduled_timestamp,
                        "scheduled_time_iso": scheduled_dt.isoformat() if scheduled_dt else None,
                        "message": message,
                        "published": params.get("published"),
                        "media_type": "video",
                        "video_url": video_url
                    }
                    return result
                else:
                    logger.warning(f"❌ Video upload failed: {result}")
                    if link:
                        message += f"\n\nWatch video: {link}"

            else:
                logger.warning(f"Failed to download video from {video_url}, falling back to image/text post")
                if link:
                    message += f"\n\nWatch video: {link}"

        except Exception as e:
            logger.warning(f"Video processing failed: {e}, falling back to image/text post")
            if link:
                message += f"\n\nWatch video: {link}"

    # If we have an IMAGE URL
    if image_url:
        try:
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    temp_file.write(response.content)
                    temp_image_path = temp_file.name

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

                os.unlink(temp_image_path)

                photo_data = photo_res.json()

                if "id" in photo_data:
                    post_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
                    payload = {
                        "message": message,
                        "access_token": FACEBOOK_ACCESS_TOKEN,
                        "attached_media": json.dumps([{"media_fbid": photo_data["id"]}])
                    }

                    # ✅ FIX: include link param if available
                    if link:
                        payload["link"] = link

                    if scheduled_timestamp_unix:
                        payload["published"] = "false"
                        payload["scheduled_publish_time"] = scheduled_timestamp_unix
                    else:
                        payload["published"] = "true"

                    response = requests.post(post_url, data=payload)
                    result = response.json()
                    
                    result["debug_info"] = {
                        "scheduled_time_final": scheduled_timestamp,
                        "scheduled_time_iso": scheduled_dt.isoformat() if scheduled_dt else None,
                        "message": message,
                        "published": payload.get("published"),
                        "media_type": "image"
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

    # Fallback: Proper text post with link parameter
    post_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
    payload = {
        "message": message,
        "access_token": FACEBOOK_ACCESS_TOKEN,
    }

    # ✅ FIX: use link param instead of appending to message
    if link:
        payload["link"] = link

    if scheduled_timestamp_unix:
        payload["published"] = "false"
        payload["scheduled_publish_time"] = scheduled_timestamp_unix
    else:
        payload["published"] = "true"

    response = requests.post(post_url, data=payload)
    try:
        data = response.json()
    except Exception:
        data = {"error": "Invalid JSON response", "raw": response.text}

    data["debug_info"] = {
        "scheduled_time_final": scheduled_timestamp,
        "scheduled_time_iso": scheduled_dt.isoformat() if scheduled_dt else None,
        "message": message,
        "published": payload.get("published"),
        "media_type": "text_only"
    }

    return data

# --------------------------------------------------------------------
# DB INSERTION - UPDATED FOR VIDEO SUPPORT
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
    
    if not isinstance(articles, list):
        logger.error(f"Scraper returned non-list: {type(articles)}")
        articles = []

    normalized = [normalize_article(a) for a in articles]
    filtered = [a for a in normalized if is_valid_article(a) and looks_like_football(a["title"], a["summary"], a["url"])]

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
            video_url=a["video_url"],
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
            "source": a["source"],
            "image_url": a["image_url"],
            "video_url": a["video_url"]
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
# MAIN RUNNER
# --------------------------------------------------------------------
def run_scraper(dry_run=False):
    logger.info("Starting football scraper (dry_run=%s)", dry_run)
    all_articles = []

    # Scrape all football sources
    try:
        # CHANGE THIS LINE ONLY - Use enhanced API + scraping
        results = scrape_premier_league_enhanced()  # <-- Changed here
        all_articles.extend(results)
        logger.info("Premier League: %d articles (API+Scraping)", len(results))
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

    # Enhanced missing media detection
    missing_media = check_missing_media(all_articles)
    if missing_media:
        for article in missing_media:
            logger.warning("   - %s: %s", article['title'], article['url'])

    with app.app_context():
        session = db.session
        db.create_all()

        # Get recent Facebook posts and scheduled posts for duplicate checking
        recent_posts = get_recent_facebook_posts()
        logger.info("Fetched %d recent Facebook posts for duplicate checking", len(recent_posts))

        # Filter out potential duplicates before insertion
        filtered_articles = []
        # ADD THIS LINE: Initialize the set for tracking titles in this batch
        seen_titles_in_this_batch = set()
        
        for article in all_articles:
            # ENHANCED: Check for near-duplicates in this batch
            current_title_lower = article['title'].lower().strip()
            is_duplicate_in_batch = False
            
            for seen_title in seen_titles_in_this_batch:
                # Check if titles are very similar (e.g., 80% similar)
                similarity = calculate_title_similarity(current_title_lower, seen_title)
                if similarity > 0.8:  # 80% similarity threshold
                    logger.warning("⚠️ Skipping duplicate in same batch: %s (similar to: %s)", 
                                 article['title'][:50], seen_title[:50])  # Fixed: article['title'] not article.title
                    is_duplicate_in_batch = True
                    break
            
            if is_duplicate_in_batch:
                continue
            
            # Check against recent Facebook posts
            if is_duplicate_post(article['title'], article.get('summary', ''), recent_posts, article.get('url')):
                logger.warning("Skipping potential duplicate: %s", article['title'])
                continue
            
            seen_titles_in_this_batch.add(current_title_lower)
            
            # Check against already scheduled posts
            if is_already_scheduled(session, article['title'], article['url']):
                continue
            
            filtered_articles.append(article)

        logger.info("After duplicate filtering: %d articles remaining", len(filtered_articles))

        # Insert new articles
        inserted = insert_articles(session, filtered_articles, dry_run=dry_run)
        logger.info("Inserted %d new records", len(inserted))

        # Schedule posts
        scheduled_count = schedule_new_posts(session, dry_run=dry_run)
        logger.info("Scheduled %d posts", scheduled_count)

        # Final report with media statistics
        video_count = len([p for p in inserted if p.get('video_url')])
        image_count = len([p for p in inserted if p.get('image_url') and not p.get('video_url')])
        no_media_count = len([p for p in inserted if not p.get('image_url') and not p.get('video_url')])
        
        logger.info("📊 Media Statistics:")
        logger.info("   - Videos: %d", video_count)
        logger.info("   - Images: %d", image_count)
        logger.info("   - No media: %d", no_media_count)

        if no_media_count > 0 and not dry_run:
            logger.warning("📋 ADMIN: %d new posts need media. Visit: /admin/posts-without-images", no_media_count)

        if dry_run:
            for i in inserted:
                media_type = "video" if i.get('video_url') else "image" if i.get('image_url') else "no media"
                logger.info("DRY: seq=%s title=%s url=%s media=%s", i["seq"], i["title"], i["url"], media_type)

    logger.info("Football scraper run complete.")

# ADD THIS HELPER FUNCTION for title similarity checking
def calculate_title_similarity(title1, title2):
    """
    Calculate similarity between two titles using word overlap.
    Returns a value between 0 (completely different) and 1 (identical).
    """
    # Split titles into words and remove common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    
    words1 = set(word.lower() for word in title1.split() if word.lower() not in stop_words and len(word) > 2)
    words2 = set(word.lower() for word in title2.split() if word.lower() not in stop_words and len(word) > 2)
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0
    
# --------------------------------------------------------------------
# WORKER FUNCTION
# --------------------------------------------------------------------
def run_worker(interval_hours=None):
    """
    Run scraper in continuous worker mode (2-hour intervals as requested)
    """
    
    if interval_hours is None:
        interval_hours = POST_GAP_HOURS
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
    parser.add_argument("--interval", type=int, default=POST_GAP_HOURS, help="Worker interval in hours (default: 2)")
    
    args = parser.parse_args()

    if args.worker:
        # Run as continuous worker
        run_worker(interval_hours=args.interval)
    else:
        # Run once
        run_scraper(dry_run=args.dry_run)
