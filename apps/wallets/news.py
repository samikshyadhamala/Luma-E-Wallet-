"""Small, database-free RSS client for the wallet dashboard."""

from datetime import datetime, timezone as datetime_timezone
from email.utils import parsedate_to_datetime
from html import unescape
import re
from urllib.error import URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from django.core.cache import cache
from django.utils.html import strip_tags

FEED_URL = "https://feeds.bbci.co.uk/news/business/rss.xml"
CACHE_KEY = "wallet_dashboard_business_news_v2"
STALE_CACHE_KEY = "wallet_dashboard_business_news_stale_v2"
CACHE_SECONDS = 5 * 60
STALE_SECONDS = 60 * 60
MAX_ITEMS = 10


def get_news():
    """Return cached news, refreshing it from BBC Business RSS when expired."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        request = Request(FEED_URL, headers={"User-Agent": "LumaWallet/1.0 RSS reader"})
        with urlopen(request, timeout=4) as response:
            xml_data = response.read(1_000_000)
        items = _parse_feed(xml_data)
        result = {
            "items": items,
            "updated_at": datetime.now(datetime_timezone.utc).isoformat(),
            "stale": False,
        }
        if items:
            cache.set(CACHE_KEY, result, CACHE_SECONDS)
            cache.set(STALE_CACHE_KEY, result, STALE_SECONDS)
            return result
    except (URLError, TimeoutError, OSError, ET.ParseError, ValueError):
        pass

    stale = cache.get(STALE_CACHE_KEY)
    if stale:
        return {**stale, "stale": True}
    return {"items": [], "updated_at": None, "stale": False}


def _parse_feed(xml_data):
    root = ET.fromstring(xml_data)
    parsed = []
    for item in root.findall("./channel/item"):
        title = _clean(item.findtext("title"))
        link = _clean(item.findtext("link"))
        if not title or not link or not link.startswith(("https://", "http://")):
            continue
        description = _clean(item.findtext("description"))
        category = _categorize(f"{title} {description}")
        parsed.append({
            "title": title,
            "link": link,
            "description": description,
            "published": _format_date(_clean(item.findtext("pubDate"))),
            "category": category,
        })

    # RSS feeds are normally newest-first; Python's stable sort retains that
    # ordering inside each priority group. Other business news fills any gaps.
    parsed.sort(key=lambda article: article["category"] == "Business")
    return parsed[:MAX_ITEMS]


def _categorize(text):
    text = text.lower()
    technology = re.search(
        r"\b(tech|technology|artificial intelligence|\bai\b|software|cyber(?:security)?|"
        r"semiconductor|chipmaker|data centre|data center|robotics?|digital|internet|apps?)\b",
        text,
    )
    finance = re.search(
        r"\b(finance|financial|bank(?:s|ing)?|stock market|shares?|stocks?|investment|investing|"
        r"inflation|interest rates?|currency|currencies|mortgages?|lending|fintech|crypto(?:currency)?|"
        r"econom(?:y|ic)|budget|tax(?:es)?|trading|retail sales|gdp)\b",
        text,
    )
    if technology and finance:
        return "Technology & Finance"
    if technology:
        return "Technology"
    if finance:
        return "Finance"
    return "Business"

def _clean(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", unescape(strip_tags(value))).strip()


def _format_date(value):
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, OverflowError):
        return value
