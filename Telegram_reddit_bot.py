import requests
import time
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# Scopes and match styles
INCLUDE_SCOPE = "title_body"       # "title_body" or "body_only" or "title_only"
EXCLUDE_SCOPE = "title_body"       # usually "title_body" or "body_only"
WHOLE_WORD_MATCH = True            # set False for simple substring matching (no boundaries)


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Telegram error: {e}")


def load_feeds_config(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_search_text(post_data, scope: str) -> str:
    title = post_data.get("title", "") or ""
    body = post_data.get("selftext", "") or ""
    if scope == "title_body":
        return f"{title}\n{body}"
    elif scope == "body_only":
        return body
    elif scope == "title_only":
        return title
    return f"{title}\n{body}"


def contains_any_keyword(text: str, words, whole_word: bool = True) -> bool:
    """
    - whole_word=True: match only when surrounded by non [0-9A-Za-z_]
      Uses fixed-length lookarounds: (?<![0-9A-Za-z_]) ... (?![0-9A-Za-z_])
      This avoids \b pitfalls with punctuation like 'C++' or '#topic'.
    - whole_word=False: case-insensitive substring search.
    """
    if not words:
        return False
    if text is None:
        text = ""
    for w in words:
        if not w:
            continue
        w = w.strip()
        if not w:
            continue

        if whole_word:
            # Compile a safe pattern with explicit ASCII "word" boundaries.
            # We don't lower() the pattern; IGNORECASE handles it.
            pattern = rf"(?<![0-9A-Za-z_]){re.escape(w)}(?![0-9A-Za-z_])"
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        else:
            if w.lower() in text.lower():
                return True
    return False


def monitor_feeds(config_path):
    feeds = load_feeds_config(config_path)
    seen_post_ids = {feed["url"]: set() for feed in feeds}

    while True:
        try:
            for feed in feeds:
                url = feed["url"]
                include_keywords = feed.get("keywords", []) or []
                exclude_keywords = feed.get("exclude_keywords", []) or []
                name = feed["name"]
                seen = seen_post_ids[url]

                resp = requests.get(url, headers=HEADERS, timeout=20)
                resp.raise_for_status()
                data = resp.json()
                posts = data.get("data", {}).get("children", [])

                for post in posts:
                    post_data = post.get("data", {})
                    post_id = post_data.get("id")
                    if not post_id or post_id in seen:
                        continue

                    include_text = build_search_text(post_data, INCLUDE_SCOPE)

                    # Build exclude text according to EXCLUDE_SCOPE
                    if EXCLUDE_SCOPE == "body_only":
                        exclude_text = build_search_text(post_data, "body_only")
                    elif EXCLUDE_SCOPE == "title_only":
                        exclude_text = build_search_text(post_data, "title_only")
                    else:
                        exclude_text = build_search_text(post_data, "title_body")

                    include_hit = contains_any_keyword(include_text, include_keywords, WHOLE_WORD_MATCH)
                    exclude_hit = contains_any_keyword(exclude_text, exclude_keywords, WHOLE_WORD_MATCH)

                    # Notify only if include matches and exclude does NOT
                    if include_hit and not exclude_hit:
                        permalink = post_data.get("permalink", "")
                        post_url = "https://www.reddit.com" + permalink if permalink else url
                        title = post_data.get("title", "(no title)")
                        message = f"📢 [{name}] New post:\n\n{title}\n\n🔗 {post_url}"
                        send_telegram_message(message)
                        seen.add(post_id)
                    else:
                        # If it matched include but was excluded, mark seen to avoid repeat checks.
                        if include_hit:
                            seen.add(post_id)

            time.sleep(600)

        except Exception as e:
            send_telegram_message(f"⚠️ Error: {e}")
            time.sleep(600)


if __name__ == "__main__":
    monitor_feeds("feeds.json")
