import requests
import time
import os
import json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HEADERS = {"User-Agent": "Mozilla/5.0"}


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)


def load_feeds_config(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)


def monitor_feeds(config_path):
    feeds = load_feeds_config(config_path)
    seen_post_ids = {}

    for feed in feeds:
        seen_post_ids[feed["url"]] = set()

    while True:
        try:
            for feed in feeds:
                url = feed["url"]
                keywords = feed["keywords"]
                name = feed["name"]
                seen = seen_post_ids[url]

                response = requests.get(url, headers=HEADERS)
                posts = response.json()["data"]["children"]

                for post in posts:
                    post_data = post["data"]
                    post_id = post_data["id"]
                    title = post_data["title"]

                    if post_id not in seen and any(keyword.lower() in title.lower() for keyword in keywords):
                        post_url = "https://www.reddit.com" + post_data["permalink"]
                        message = f"📢 [{name}] New post:\n\n{title}\n\n🔗 {post_url}"
                        send_telegram_message(message)
                        seen.add(post_id)

            time.sleep(300)

        except Exception as e:
            send_telegram_message(f"⚠️ Error: {e}")
            time.sleep(300)


if __name__ == "__main__":
    monitor_feeds("feeds.json")
