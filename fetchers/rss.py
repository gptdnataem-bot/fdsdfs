import feedparser, yaml, re
from typing import List, Dict, Optional

def load_config(path: str="sources.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _extract_thumb(entry) -> Optional[str]:
    # Standard media fields
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get('url')
        if url: return url
    if hasattr(entry, 'media_content') and entry.media_content:
        url = entry.media_content[0].get('url')
        if url: return url
    # Enclosure
    for l in getattr(entry, 'links', []):
        if l.get('rel') == 'enclosure' and str(l.get('type','')).startswith('image/'):
            return l.get('href')
    # <img> inside summary html
    summary = getattr(entry, 'summary', '') or ''
    if '<img' in summary:
        try:
            import re as _re
            m = _re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary, _re.I)
            if m: return m.group(1)
        except Exception:
            pass
    # YouTube id -> thumbnail
    link = getattr(entry, 'link', '') or getattr(entry, 'id', '')
    vid = None
    if 'youtube.com/watch?v=' in link:
        import urllib.parse as up
        vid = dict(up.parse_qsl(up.urlparse(link).query)).get('v')
    elif 'youtu.be/' in link:
        vid = link.split('youtu.be/')[-1].split('?')[0]
    if vid:
        # try maxres; falls back to hq in Telegram anyway
        return f'https://i.ytimg.com/vi/{vid}/maxresdefault.jpg'
    return None

def youtube_channel_feed(channel_id: str) -> str:
(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

def filter_highlights(items: List[Dict], keywords: List[str]) -> List[Dict]:
    patt = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
    return [it for it in items if patt.search(it["title"])]
