import feedparser
from datetime import datetime

# Free RSS feeds from top Indian financial news sources
# No API key needed - completely free!
NEWS_FEEDS = {
    "moneycontrol": "https://www.moneycontrol.com/rss/latestnews.xml",
    "economic_times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "livemint": "https://www.livemint.com/rss/markets",
    "business_standard": "https://www.business-standard.com/rss/markets-106.rss",
}

# Keywords that affect NIFTY/BANKNIFTY directly
# If news contains these words → mark as HIGH impact
HIGH_IMPACT_KEYWORDS = [
    "RBI", "repo rate", "interest rate", "inflation",
    "GDP", "budget", "federal reserve", "Fed", "CPI",
    "FII", "crude oil", "rupee", "SEBI", "ban",
    "war", "election", "Modi", "recession"
]

# Keywords for medium impact news
MEDIUM_IMPACT_KEYWORDS = [
    "NIFTY", "BANKNIFTY", "Sensex", "BSE", "NSE",
    "earnings", "results", "quarterly", "profit", "loss",
    "merger", "acquisition", "IPO", "dividend"
]

def get_impact_level(title, description):
    # Check if news is high, medium or low impact
    # Based on keywords in title and description
    text = (title + " " + description).upper()

    # Check high impact keywords
    for keyword in HIGH_IMPACT_KEYWORDS:
        if keyword.upper() in text:
            return "HIGH"

    # Check medium impact keywords
    for keyword in MEDIUM_IMPACT_KEYWORDS:
        if keyword.upper() in text:
            return "MEDIUM"

    # Default low impact
    return "LOW"

def get_impact_emoji(impact):
    # Visual indicator for impact level
    # Makes it easy to spot important news quickly
    if impact == "HIGH":
        return "🔴"
    elif impact == "MEDIUM":
        return "🟡"
    else:
        return "🟢"

def fetch_news():
    try:
        all_news = []

        # Loop through each news source
        for source_name, feed_url in NEWS_FEEDS.items():
            try:
                # Parse the RSS feed
                feed = feedparser.parse(feed_url)

                # Get latest 5 news from each source
                for entry in feed.entries[:5]:
                    title = entry.get("title", "No title")
                    description = entry.get("summary", "")
                    link = entry.get("link", "")
                    published = entry.get("published", "")

                    # Calculate impact level
                    impact = get_impact_level(title, description)
                    emoji = get_impact_emoji(impact)

                    all_news.append({
                        "source": source_name,
                        "title": title,
                        "description": description[:200],
                        "link": link,
                        "published": published,
                        "impact": impact,
                        "emoji": emoji,
                    })

            except Exception as e:
                # If one source fails don't stop others
                print(f"Error fetching {source_name}: {str(e)}")
                continue

        # Sort news by impact level
        # HIGH impact news appears first
        impact_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        all_news.sort(key=lambda x: impact_order[x["impact"]])

        return {
            "status": "success",
            "count": len(all_news),
            "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p"),
            "news": all_news
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "news": []
        }
 
"""Save with **Ctrl + S**

**What this does:**
```
1. Fetches RSS feeds from 4 top Indian news sources
2. Gets latest 5 news from each = 20 news total
3. Scans each headline for important keywords
4. Labels them:
   🔴 HIGH   → RBI, Fed, repo rate, war, election
   🟡 MEDIUM → NIFTY, earnings, results, IPO
   🟢 LOW    → General market news
5. Sorts HIGH impact news to the top
6. Returns everything cleanly packaged"""