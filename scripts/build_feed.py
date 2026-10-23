"""Fetch the space news feeds and write feed.json. Runs hourly on GitHub Actions. Standard library only."""
import email.utils
import datetime
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

SPACE_RE = re.compile(r"space|rocket|satellite|ISRO|IN-SPACe|INSPACe|NSIL|Sriharikota|launch|orbit|Gaganyaan|Aditya|Guild|payload", re.I)
MAX_PER_SOURCE = 8
OUT = "feed.json"

# Public RSS feeds. "only" keeps just the space stories from general outlets.
FEEDS = [
    {"name": "NASA", "url": "https://www.nasa.gov/feed/"},
    {"name": "Spaceflight Now", "url": "https://spaceflightnow.com/feed/"},
    {"name": "Space.com", "url": "https://www.space.com/feeds/all"},
    {"name": "ISRO news", "url": "https://news.google.com/rss/search?q=ISRO&hl=en-IN&gl=IN&ceid=IN:en"},
    {"name": "The Hindu (Science)", "url": "https://www.thehindu.com/sci-tech/science/feeder/default.rss", "only": True},
    {"name": "The Hindu (Industry)", "url": "https://www.thehindu.com/business/Industry/feeder/default.rss", "only": True},
    {"name": "Times of India (Science)", "url": "https://timesofindia.indiatimes.com/rssfeeds/-2128672765.cms", "only": True},
    {"name": "SpaceNews", "url": "https://spacenews.com/feed/"},
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (CelestKart feed builder)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def plain(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:220]


def image_for(item, desc):
    for el in item.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("content", "thumbnail") and el.get("url"):
            return el.get("url")
        if tag == "enclosure" and (el.get("type") or "").startswith("image") and el.get("url"):
            return el.get("url")
    m = re.search(r"<img[^>]+src=[\"']([^\"']+)", desc or "")
    return m.group(1) if m else ""


def parse(feed, data):
    root = ET.fromstring(data)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = item.findtext("description") or ""
        if not title or not link:
            continue
        summary = plain(desc)
        if feed.get("only") and not SPACE_RE.search(title + " " + summary):
            continue
        try:
            dt = email.utils.parsedate_to_datetime(item.findtext("pubDate") or "")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            date = dt.astimezone(datetime.timezone.utc).isoformat()
        except (TypeError, ValueError):
            date = datetime.datetime.now(datetime.timezone.utc).isoformat()
        out.append({"title": title, "link": link, "summary": summary,
                    "image": image_for(item, desc), "date": date, "source": feed["name"]})
        if len(out) >= MAX_PER_SOURCE:
            break
    return out


def main():
    items, errors = [], []
    for feed in FEEDS:
        try:
            items += parse(feed, fetch(feed["url"]))
        except Exception as e:  # keep going; one bad feed must not stop the others
            errors.append(feed["name"] + ": " + str(e))
    if not items:
        print("No stories fetched; keeping the previous feed.json", file=sys.stderr)
        sys.exit(0)
    data = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "errors": errors, "items": items}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("Wrote", len(items), "stories;", len(errors), "feed errors")


if __name__ == "__main__":
    main()
