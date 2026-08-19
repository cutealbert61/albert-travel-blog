#!/usr/bin/env python3
"""
亞伯特的生活旅遊日誌 — 每日文章自動產生腳本
"""

import os
import re
import json
import random
import datetime
import unicodedata
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SITE_DIR = os.path.join(ROOT, "docs")
POSTS_DIR = os.path.join(SITE_DIR, "posts")
TEMPLATE_PATH = os.path.join(ROOT, "scripts", "post_template.html")

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")

COUNTRY_CODE_MAP = {
    "Japan": "JPN", "Thailand": "THA", "South Korea": "KOR", "Indonesia": "IDN",
    "Vietnam": "VNM", "Turkey": "TUR", "France": "FRA", "Portugal": "PRT",
    "Czech Republic": "CZE", "Greece": "GRC", "Iceland": "ISL", "Spain": "ESP",
    "South Africa": "ZAF", "Morocco": "MAR", "Tanzania": "TZA", "USA": "USA",
    "Mexico": "MEX", "Peru": "PER", "Argentina": "ARG", "Canada": "CAN",
    "New Zealand": "NZL", "Australia": "AUS", "Fiji": "FJI",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_next_topic(locations, history):
    if history["priority_queue"]:
        item = history["priority_queue"].pop(0)
        city = next(c for c in locations["cities"] if c["city_en"] == item["city_en"])
        if item.get("angle_key"):
            angle = next(a for a in locations["angles"] if a["key"] == item["angle_key"])
        else:
            avoid = item.get("avoid_angle_key")
            candidates = [a for a in locations["angles"] if a["key"] != avoid]
            angle = random.choice(candidates or locations["angles"])
        return city, angle

    used = {(u["city_en"], u["angle_key"]) for u in history["used_combinations"]}
    all_combos = [(c, a) for c in locations["cities"] for a in locations["angles"]]
    unused = [(c, a) for c, a in all_combos if (c["city_en"], a["key"]) not in used]

    if unused:
        city, angle = random.choice(unused)
    else:
        city = random.choice(locations["cities"])
        angle = random.choice(locations["angles"])
    return city, angle


def build_prompt(city, angle):
    return f"""你是一位資深旅遊作家,請以「{city['city']}({city['city_en']}), {city['country']}」為主題,
用「{angle['zh']} / {angle['en']}」這個切角({angle['prompt_hint']}),寫一篇雜誌等級的深度旅遊日誌。

嚴格要求:
- 中文版與英文版內容對應但不是逐字翻譯,各自要讀起來像母語者寫的文章,各1500字以上
- 必須是這個城市『這個角度』獨有的深度內容,包含具體地名、店名或路線,不要空泛的觀光介紹
- 文章要有 2-3 個小標題(h2),段落之間可以穿插一段值得摘錄的金句(pull quote)
- 在文中三個最適合放照片的地方,各自獨立一行插入 [IMAGE_1]、[IMAGE_2]、[IMAGE_3] 作為佔位符(依序,只能用一次)
- 提供 3 個對應 [IMAGE_1][IMAGE_2][IMAGE_3] 的 Unsplash 英文搜尋關鍵字(3-5個字,要能搜到符合該段落內容的真實照片)
- 提供封面照片的 Unsplash 英文搜尋關鍵字(cover_image_query)
- 提供 4-6 個文章標籤(中英皆可,短詞)
- 標題與摘要中英各一句

請「只」回傳以下 JSON 格式,不要加任何 markdown 符號或說明文字:
{{
  "title_zh": "...",
  "title_en": "...",
  "excerpt_zh": "...(一句話摘要,40字內)",
  "excerpt_en": "...",
  "body_zh_html": "<p>...</p><h2>...</h2><p>...</p>...(內含 [IMAGE_1] [IMAGE_2] [IMAGE_3] 佔位符,以及一個 <blockquote class=\"pull-quote\">金句</blockquote>)",
  "body_en_html": "<p>...</p>...(same structure, English)",
  "image_queries": {{"cover_image_query": "...", "image_1": "...", "image_2": "...", "image_3": "..."}},
  "tags": ["...", "..."],
  "reading_time": 6
}}
"""


def call_claude(prompt: str) -> dict:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    if resp.status_code >= 400:
        print("Anthropic API error status:", resp.status_code)
        print("Anthropic API error body:", resp.text)
    resp.raise_for_status()
    data = resp.json()
    text = "".join(block["text"] for block in data["content"] if block["type"] == "text")
    text = text.strip()
    text = re.sub(r"^```json\s*|\s*```$", "", text.strip())
    return json.loads(text)


def unsplash_search(query: str) -> dict:
    if not UNSPLASH_ACCESS_KEY:
        return {"url": "https://source.unsplash.com/1600x900/?" + requests.utils.quote(query),
                "credit_name": "Unsplash", "credit_link": "https://unsplash.com"}
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=30,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            raise ValueError("no results")
        photo = results[0]
        return {
            "url": photo["urls"]["regular"],
            "credit_name": photo["user"]["name"],
            "credit_link": photo["user"]["links"]["html"] + "?utm_source=albert_travel_journal&utm_medium=referral",
        }
    except Exception as e:
        print("Unsplash search failed, falling back:", e)
        return {"url": "https://source.unsplash.com/1600x900/?" + requests.utils.quote(query),
                "credit_name": "Unsplash", "credit_link": "https://unsplash.com"}


def insert_images(body_html: str, image_infos: list) -> str:
    for i, info in enumerate(image_infos, start=1):
        figure = (
            f'<figure><img src="{info["url"]}" alt="" loading="lazy">'
            f'<figcaption>Photo by <a href="{info["credit_link"]}" target="_blank" rel="noopener">'
            f'{info["credit_name"]}</a> on <a href="https://unsplash.com" target="_blank" rel="noopener">Unsplash</a></figcaption></figure>'
        )
        body_html = body_html.replace(f"[IMAGE_{i}]", figure)
    return body_html


def render_post_html(context: dict) -> str:
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    for key, value in context.items():
        html = html.replace("{{" + key + "}}", str(value))
    return html


def main():
    if not ANTHROPIC_API_KEY:
        raise SystemExit("缺少 ANTHROPIC_API_KEY 環境變數")

    locations = load_json(os.path.join(DATA_DIR, "locations.json"))
    history = load_json(os.path.join(DATA_DIR, "history.json"))
    posts = load_json(os.path.join(DATA_DIR, "posts.json"))

    city, angle = pick_next_topic(locations, history)
    print(f"今日主題: {city['city']} ({city['city_en']}) × {angle['zh']}")

    article = call_claude(build_prompt(city, angle))

    cover = unsplash_search(article["image_queries"]["cover_image_query"] + " " + city["city_en"])
    img1 = unsplash_search(article["image_queries"]["image_1"])
    img2 = unsplash_search(article["image_queries"]["image_2"])
    img3 = unsplash_search(article["image_queries"]["image_3"])

    body_zh = insert_images(article["body_zh_html"], [img1, img2, img3])
    body_en = insert_images(article["body_en_html"], [img1, img2, img3])

    today = datetime.date.today().isoformat()
    slug = f"{today}-{slugify(city['city_en'])}-{angle['key']}"
    country_code = COUNTRY_CODE_MAP.get(city["country_en"], city["country_en"][:3].upper())

    tags_html = "".join(f'<span class="tag">{t}</span>' for t in article["tags"])

    context = {
        "TITLE_ZH": article["title_zh"], "TITLE_EN": article["title_en"],
        "EXCERPT_ZH": article["excerpt_zh"],
        "COVER_IMAGE": cover["url"], "CITY_EN": city["city_en"],
        "COUNTRY_CODE": country_code, "DATE": today,
        "REGION": city["region"], "ANGLE_ZH": angle["zh"], "ANGLE_EN": angle["en"],
        "CITY_ZH": city["city"], "COUNTRY_ZH": city["country"],
        "READING_TIME": article.get("reading_time", 6),
        "BODY_ZH": body_zh, "BODY_EN": body_en,
        "TAGS_HTML": tags_html,
    }

    os.makedirs(POSTS_DIR, exist_ok=True)
    with open(os.path.join(POSTS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(render_post_html(context))

    posts.append({
        "slug": slug, "date": today, "status": "published",
        "title_zh": article["title_zh"], "title_en": article["title_en"],
        "excerpt_zh": article["excerpt_zh"], "excerpt_en": article["excerpt_en"],
        "cover_image": cover["url"], "region": city["region"],
        "city_en": city["city_en"], "country_code": country_code,
        "angle_key": angle["key"], "angle_en": angle["en"], "tags": article["tags"],
    })
    history["used_combinations"].append({"city_en": city["city_en"], "angle_key": angle["key"], "date": today})

    save_json(os.path.join(DATA_DIR, "posts.json"), posts)
    save_json(os.path.join(DATA_DIR, "history.json"), history)

    print(f"完成: docs/posts/{slug}.html")


if __name__ == "__main__":
    main()
