import feedparser, yaml, re
from typing import List, Dict, Optional

def load_config(path: str="sources.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _extract_thumb(entry) -> Optional[str]:
    # Try standard media:thumbnail / media:content
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url')
    if hasattr(entry, 'media_content') and entry.media_content:
        return entry.media_content[0].get('url')
    # enclosure link
    for l in getattr(entry, 'links', []):
        if l.get('rel') == 'enclosure' and l.get('type', '').startswith('image/'):
            return l.get('href')
    # youtube thumbnail
    if hasattr(entry, 'id') and 'youtube.com' in entry.id:
        # YouTube often has media_thumbnail too, but fallback to HQ default pattern by video id
        vid = entry.id.split(':')[-1]
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    # generic
    return None

def parse_rss(url: str) -> List[Dict]:
    d = feedparser.parse(url)
    items = []
    for e in d.entries:
        title = getattr(e, "title", "")
        link = getattr(e, "link", "")
        summary = getattr(e, "summary", getattr(e, "description", ""))
        thumb = _extract_thumb(e)
        items.append({
            "title": title,
            "url": link,
            "summary": summary,
            "image_url": thumb
        })
    return items

def youtube_channel_feed(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

def filter_highlights(items: List[Dict], keywords: List[str]) -> List[Dict]:
    patt = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
    return [it for it in items if patt.search(it["title"])]
