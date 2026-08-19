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
    return (
        "你是一位資深旅遊作家,剛結束一趟親身旅行,請以「" + city["city"] + "(" + city["city_en"] + "), " + city["country"] + "」為主題,\n"
        + "用「" + angle["zh"] + " / " + angle["en"] + "」這個切角(" + angle["prompt_hint"] + "),寫一篇雜誌等級的深度旅遊日誌。\n\n"
        + "嚴格要求:\n"
        + "- 這是長篇深度特輯,中文版與英文版內容對應但不是逐字翻譯,各自要讀起來像母語者寫的文章,各3000字以上,不能為了湊字數而空泛描述,每一段都要有具體資訊或細節\n"
        + "- 全文用第一人稱「我」的親身遊客視角寫,像是剛從那裡回來、迫不及待跟朋友分享的旅行日記,要有具體的時間軸感(例如「清晨六點我走出旅館」「傍晚時分」)、真實的心理轉折與感受,不要用「你可以...」這種導覽手冊式的第二人稱條列句\n"
        + "- 多用感官細節(氣味、聲音、觸感、味道、光線),讓讀者彷彿身歷其境,但避免濫用形容詞堆砌,要具體不要空泛\n"
        + "- 文章裡至少要包含以下三種元素各一段,而且要寫得夠深入(每個元素至少400字):\n"
        + "  1) 「怎麼玩」的實際體驗細節:挑一個具體景點或活動,寫出我實際怎麼去的、路線、花了多少時間、遇到什麼狀況、注意事項、大概費用,像是把自己走過的路完整記錄下來\n"
        + "  2) 具體美食體驗:寫出真實店名或攤位、我點了什麼、味道口感的具體描述、大概價位、當下的用餐情境與感受,讓讀者看了會想立刻去吃\n"
        + "  3) 風俗民情或節慶介紹:透過我親身觀察或與當地人互動的小故事,帶出當地人的生活習慣、禁忌、季節性節慶或儀式,幫助讀者理解在地文化脈絡,不要用條列式的百科全書寫法\n"
        + "- 必須是這個城市『這個角度』獨有的深度內容,包含具體地名、店名或路線,不要空泛的觀光介紹\n"
        + "- 文章要有 3-4 個小標題(h2),依照我的時間軸或行程邏輯排列,段落之間至少穿插兩段值得摘錄的金句(pull quote)\n"
        + "- 在文中三個最適合放照片的地方,各自獨立一行插入 [IMAGE_1]、[IMAGE_2]、[IMAGE_3] 作為佔位符(依序,只能用一次)\n"
        + "- 提供 3 個對應 [IMAGE_1][IMAGE_2][IMAGE_3] 的 Unsplash 英文搜尋關鍵字(3-5個字,要能搜到符合該段落內容的真實照片)。若該張照片適合出現人物,搜尋關鍵字務必指定當地人的樣貌與文化情境(例如日本用 \"Japanese woman kimono street\"、摩洛哥用 \"Moroccan man market\",不要用沒有地域特徵的泛用人物描述如 \"person walking\"),確保照片中出現的人物與文章描述的地方一致\n"
        + "- 提供封面照片的 Unsplash 英文搜尋關鍵字(cover_image_query),若涉及人物同樣要指定當地人特徵\n"
        + "- 提供 4-6 個文章標籤(中英皆可,短詞)\n"
        + "- 標題與摘要中英各一句\n\n"
        + '請「只」回傳以下 JSON 格式,不要加任何 markdown 符號或說明文字:\n'
        + "{\n"
        + '  "title_zh": "...",\n'
        + '  "title_en": "...",\n'
        + '  "excerpt_zh": "...(一句話摘要,40字內)",\n'
        + '  "excerpt_en": "...",\n'
        + '  "body_zh_html": "<p>...</p><h2>...</h2><p>...</p>...(內含 [IMAGE_1] [IMAGE_2] [IMAGE_3] 佔位符,以及至少兩個 pull-quote 金句)",\n'
        + '  "body_en_html": "<p>...</p>...(same structure, English)",\n'
        + '  "image_queries": {"cover_image_query": "...", "image_1": "...", "image_2": "...", "image_3": "..."},\n'
        + '  "tags": ["...", "..."],\n'
        + '  "reading_time": 12\n'
        + "}"
    )


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
            "max_tokens": 32000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=500,
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


def insert_images(body_html, image_infos):
    for i, info in enumerate(image_infos, start=1):
        url = info["url"]
        credit_link = info["credit_link"]
        credit_name = info["credit_name"]
        figure = '<figure><img src="' + url + '" alt="" loading="lazy">'
        figure = figure + '<figcaption>Photo by <a href="' + credit_link + '" target="_blank" rel="noopener">'
        figure = figure + credit_name + '</a> on <a href="https://unsplash.com" target="_blank" rel="noopener">Unsplash</a></figcaption></figure>'
        body_html = body_html.replace("[IMAGE_" + str(i) + "]", figure)
    return body_html


def render_post_html(context):
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
    print("今日主題: " + city["city"] + " (" + city["city_en"] + ") x " + angle["zh"])

    article = call_claude(build_prompt(city, angle))

    cover = unsplash_search(article["image_queries"]["cover_image_query"] + " " + city["city_en"])
    img1 = unsplash_search(article["image_queries"]["image_1"])
    img2 = unsplash_search(article["image_queries"]["image_2"])
    img3 = unsplash_search(article["image_queries"]["image_3"])

    body_zh = insert_images(article["body_zh_html"], [img1, img2, img3])
    body_en = insert_images(article["body_en_html"], [img1, img2, img3])

    today = datetime.date.today().isoformat()
    slug = today + "-" + slugify(city["city_en"]) + "-" + angle["key"] + "-" + datetime.datetime.now().strftime("%H%M")
    country_code = COUNTRY_CODE_MAP.get(city["country_en"], city["country_en"][:3].upper())

    tags_html = ""
    for t in article["tags"]:
        tags_html = tags_html + '<span class="tag">' + t + "</span>"

    context = {
        "TITLE_ZH": article["title_zh"], "TITLE_EN": article["title_en"],
        "EXCERPT_ZH": article["excerpt_zh"],
        "COVER_IMAGE": cover["url"], "CITY_EN": city["city_en"],
        "COUNTRY_CODE": country_code, "DATE": today,
        "REGION": city["region"], "ANGLE_ZH": angle["zh"], "ANGLE_EN": angle["en"],
        "CITY_ZH": city["city"], "COUNTRY_ZH": city["country"],
        "READING_TIME": article.get("reading_time", 12),
        "BODY_ZH": body_zh, "BODY_EN": body_en,
        "TAGS_HTML": tags_html,
    }

    os.makedirs(POSTS_DIR, exist_ok=True)
    with open(os.path.join(POSTS_DIR, slug + ".html"), "w", encoding="utf-8") as f:
        f.write(render_post_html(context))

    posts.append({
        "slug": slug, "date": today, "status": "published",
        "title_zh": article["title_zh"], "title_en": article["title_en"],
        "excerpt_zh": article["excerpt_zh"], "excerpt_en": article["excerpt_en"],
        "cover_image": cover["url"], "region": city["region"],
        "city_en": city["city_en"], "city_zh": city["city"],
        "country_code": country_code, "country_zh": city["country"], "country_en": city["country_en"],
        "angle_key": angle["key"], "angle_en": angle["en"], "tags": article["tags"],
    })
    history["used_combinations"].append({"city_en": city["city_en"], "angle_key": angle["key"], "date": today})

    save_json(os.path.join(DATA_DIR, "posts.json"), posts)
    save_json(os.path.join(DATA_DIR, "history.json"), history)
    save_json(os.path.join(SITE_DIR, "data", "posts.json"), posts)

    print("完成: docs/posts/" + slug + ".html")


if __name__ == "__main__":
    main()
