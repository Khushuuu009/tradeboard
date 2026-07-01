import feedparser
import requests
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# Working RSS feeds for Indian financial news
NEWS_FEEDS = {
    "economictimes": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "moneycontrol": "https://www.moneycontrol.com/rss/latestnews.xml",
    "business_standard": "https://www.business-standard.com/rss/markets-106.rss",
    "cnbc_tv18": "https://www.cnbctv18.com/feed/rss/",
    "financial_express": "https://www.financialexpress.com/feed/",
}

# Alternative: Google News RSS for Indian markets (most reliable)
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q=NIFTY+stock+market+India&hl=en-IN&gl=IN&ceid=IN:en"

# Keywords for impact analysis
HIGH_IMPACT_KEYWORDS = [
    "RBI", "repo rate", "interest rate", "inflation", "GDP", "budget", 
    "federal reserve", "Fed", "CPI", "FII", "DII", "crude oil", 
    "rupee", "SEBI", "election", "Modi", "recession", "crisis",
    "emergency", "war", "trade war", "tariff", "sanctions"
]

MEDIUM_IMPACT_KEYWORDS = [
    "NIFTY", "BANKNIFTY", "Sensex", "BSE", "NSE", "earnings", 
    "results", "quarterly", "profit", "loss", "merger", 
    "acquisition", "IPO", "dividend", "bonus", "split"
]

def get_impact_level(title, description):
    """Determine impact level based on keywords"""
    text = (title + " " + description).upper()
    
    for keyword in HIGH_IMPACT_KEYWORDS:
        if keyword.upper() in text:
            return "HIGH"
    
    for keyword in MEDIUM_IMPACT_KEYWORDS:
        if keyword.upper() in text:
            return "MEDIUM"
    
    return "LOW"

def get_impact_emoji(impact):
    """Get emoji for impact level"""
    if impact == "HIGH":
        return "🔴"
    elif impact == "MEDIUM":
        return "🟡"
    else:
        return "🟢"

def fetch_news():
    """Fetch live news from multiple sources"""
    try:
        all_news = []
        
        # First, try Google News RSS (most reliable)
        try:
            google_feed = feedparser.parse(GOOGLE_NEWS_RSS)
            for entry in google_feed.entries[:8]:
                title = entry.get("title", "No title")
                description = entry.get("summary", "")
                link = entry.get("link", "")
                published = entry.get("published", "")
                
                impact = get_impact_level(title, description)
                emoji = get_impact_emoji(impact)
                
                all_news.append({
                    "source": "Google News",
                    "title": title,
                    "description": description[:200] if description else title[:200],
                    "link": link,
                    "published": published,
                    "impact": impact,
                    "emoji": emoji,
                })
        except Exception as e:
            logger.error(f"Google News fetch error: {e}")
        
        # Then try individual RSS feeds
        for source_name, feed_url in NEWS_FEEDS.items():
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:3]:  # Get top 3 from each source
                    title = entry.get("title", "No title")
                    description = entry.get("summary", entry.get("description", ""))
                    link = entry.get("link", "")
                    published = entry.get("published", entry.get("pubDate", ""))
                    
                    impact = get_impact_level(title, description)
                    emoji = get_impact_emoji(impact)
                    
                    all_news.append({
                        "source": source_name.replace("_", " ").title(),
                        "title": title,
                        "description": description[:200] if description else title[:200],
                        "link": link,
                        "published": published,
                        "impact": impact,
                        "emoji": emoji,
                    })
                    
            except Exception as e:
                logger.error(f"Error fetching {source_name}: {e}")
                continue
        
        # Remove duplicates based on title
        seen_titles = set()
        unique_news = []
        for news in all_news:
            if news["title"] not in seen_titles:
                seen_titles.add(news["title"])
                unique_news.append(news)
        
        # Sort by impact (HIGH first) then by recency
        impact_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        unique_news.sort(key=lambda x: (impact_order[x["impact"]], x["published"]), reverse=False)
        
        # If no news was fetched, return mock data with error message
        if not unique_news:
            return {
                "status": "error",
                "message": "Unable to fetch live news. Please check your internet connection.",
                "count": 0,
                "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p"),
                "news": []
            }
        
        return {
            "status": "success",
            "count": len(unique_news),
            "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p"),
            "news": unique_news[:20]  # Limit to 20 news items
        }
        
    except Exception as e:
        logger.error(f"News fetch error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "count": 0,
            "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p"),
            "news": []
        }