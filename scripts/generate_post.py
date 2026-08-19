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
    os.makedirs(os.path.dirname(path), exist_ok=True)
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

    cities = locations["cities"]
    focus_region = history.get("focus_region")
    focus_until = history.get("focus_until")
    if focus_region and focus_until:
        today_str = datetime.date.today().isoformat()
        if today_str <= focus_until:
            focused = [c for c in cities if c["region"] == focus_region]
            if focused:
                cities = focused

    used = {(u["city_en"], u["angle_key"]) for u in history["used_combinations"]}
    all_combos = [(c, a) for c in cities for a in locations["angles"]]
    unused = [(c, a) for c, a in all_combos if (c["city_en"], a["key"]) not in used]

    if unused:
        city, angle = random.choice(unused)
    else:
        city = random.choice(cities)
        angle = random.choice(locations["angles"])
    return city, angle


def build_prompt(city, angle):
    return f"""你是一位資深旅遊作家,請以「{city['city']}({city['city_en']}), {city['country']}」為主題,
用「{angle['zh']} / {angle['en']}」這個切角({angle['prompt_hint']}),寫一篇雜誌等級的深度旅遊日誌。

嚴格要求:
- 中文版與英文版內容對應但不是逐字翻譯,各自要讀起來像母語者寫的文章,各1500字以上
- 不要只停留在風景描寫,要更生活化、更立體。文章裡至少要包含以下三種元素各一段:
  1) 「怎麼玩」的實際體驗細節:挑一個具體景點或活動,寫出實際步驟、路線、注意事項、大概要花多少時間或費用,像是在教讀者親自去做
  2) 具體美食推薦:寫出真實店名或攤位、必點菜色、味道口感描述、大概價位,讓讀者看了會想立刻去吃
  3) 風俗民情或節慶介紹:當地人的生活習慣、禁忌、季節性節慶或儀式,幫助讀者理解在地文化脈絡
- 用第一人稱旅人視角寫,多用感官細節(氣味、聲音、觸感、味道),避免像導覽手冊一樣條列式的空泛敘述
- 必須是這個城市『這個角度』獨有的深度內容,包含具體地名、店名或路線,不要空泛的觀光介紹
- 文章要有 2-3 個小標題(h2),段落之間可以穿插一段值得摘錄的金句(pull quote)
- 在文中三個最適合放照片的地方,各自獨立一行插入 [IMAGE_1]、[IMAGE_2]、[IMAGE_3] 作為佔位符(依序,只能用一次)
- 提供 3 個對應 [IMAGE_1][IMAGE_2][IMAGE_3] 的 Unsplash 英文搜尋關鍵字(3-5個字,要能搜到符合該段落內容的真實照片)。若該張照片適合出現人物,搜尋關鍵字務必指定當地人的樣貌與文化情境(例如日本用 "Japanese woman kimono street"、摩洛哥用 "Moroccan man market",不要用沒有地域特徵的泛用人物描述如 "person walking"),確保照片中出現的人物與文章描述的地方一致
- 提供封面照片的 Unsplash 英文搜尋關鍵字(cover_image_query),若涉及人物同樣要指定當地人特徵
- 提供 4-6 個文章標籤(中英皆可,短詞)
- 標題與摘要中英各一句

請「只」回傳以下 JSON 格式,不要加任何 markdown 符號或說明文字:
{{
  "title_zh": "...",
  "title_en": "...",
  "excerpt_zh": "...(一句話摘要,40字內)",
  "excerpt_en": "...",
  "body_zh_html": "<p>...</p><h2>...</h2><p>...</p>...(內含 [IMAGE_1] [IMAGE_2] [IMAGE_3] 佔位符,以及一個 <blockquote class=\\"pull-quote\\">金句</blockquote>)",
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
            "max_tokens": 16000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=180,
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
            f'<figcaption>Photo by <a href="{info
