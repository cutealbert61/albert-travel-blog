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
import html
from html.parser import HTMLParser
from urllib.parse import urlparse
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

ALLOWED_ARTICLE_TAGS = {"p", "h2", "blockquote", "figure", "img", "figcaption", "a", "strong", "em", "ul", "ol", "li", "br"}


class ArticleHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.blocked_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "embed", "form"}:
            self.blocked_depth += 1
            return
        if self.blocked_depth or tag not in ALLOWED_ARTICLE_TAGS:
            return
        clean_attrs = []
        attrs_dict = dict(attrs)
        if tag == "blockquote" and attrs_dict.get("class") == "pull-quote":
            clean_attrs.append(("class", "pull-quote"))
        if tag == "a":
            href = safe_url(attrs_dict.get("href"))
            if href:
                clean_attrs.extend([("href", href), ("target", "_blank"), ("rel", "noopener noreferrer")])
        if tag == "img":
            src = safe_url(attrs_dict.get("src"))
            if src:
                clean_attrs.append(("src", src))
            clean_attrs.append(("alt", html.escape(attrs_dict.get("alt", ""), quote=True)))
            clean_attrs.append(("loading", "lazy"))
        attr_text = "".join(' ' + name + '="' + value + '"' for name, value in clean_attrs)
        self.parts.append("<" + tag + attr_text + ">")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "embed", "form"}:
            if self.blocked_depth:
                self.blocked_depth -= 1
            return
        if not self.blocked_depth and tag in ALLOWED_ARTICLE_TAGS and tag not in {"img", "br"}:
            self.parts.append("</" + tag + ">")

    def handle_data(self, data):
        if not self.blocked_depth:
            self.parts.append(html.escape(data))

    def get_html(self):
        return "".join(self.parts)


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


def sanitize_article_html(value):
    sanitizer = ArticleHTMLSanitizer()
    sanitizer.feed(str(value or ""))
    sanitizer.close()
    return sanitizer.get_html()


def pick_from_week_plan(locations):
    path = os.path.join(DATA_DIR, "week_plan.json")
    if not os.path.exists(path):
        return None
    plan = load_json(path)
    today = datetime.date.today().isoformat()
    for item in plan:
        if item.get("status") == "pending" and item.get("date") <= today:
            city = None
            for c in locations["cities"]:
                if c["city_en"] == item["city_en"]:
                    city = c
                    break
            angle = None
            for a in locations["angles"]:
                if a["key"] == item["angle_key"]:
                    angle = a
                    break
            if city and angle:
                item["status"] = "done"
                save_json(path, plan)
                return city, angle
    return None


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

    from_plan = pick_from_week_plan(locations)
    if from_plan:
        return from_plan

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
        "你是一位嚴謹的旅遊資料編輯,請以「" + city["city"] + "(" + city["city_en"] + "), " + city["country"] + "」為主題,\n"
        + "用「" + angle["zh"] + " / " + angle["en"] + "」這個切角(" + angle["prompt_hint"] + "),寫一篇雜誌等級的深度旅遊資料特輯。\n\n"
        + "嚴格要求:\n"
        + "- 這是長篇深度特輯,中文版與英文版內容對應但不是逐字翻譯,各自要讀起來像母語者寫的文章,各3000字以上,不能為了湊字數而空泛描述,每一段都要有具體資訊或細節\n"
        + "- 這是『旅遊資料整理』而非親身遊記。禁止虛構作者去過、住過、吃過、實測或與當地人互動;不得使用『我走進』『我住在』『我實測』『我親眼看到』『最後一晚』等第一人稱親歷敘述\n"
        + "- 採第三人稱編輯觀察或中性敘述,可以用具體時間軸提出『建議行程』,但必須清楚寫成規劃建議,不能假裝已實際發生\n"
        + "- 多用可查證的感官與場景細節,讓讀者理解環境,但避免把推測寫成事實,不要捏造人物、對話、店家歷史、價格或法規\n"
        + "- 文章裡至少要包含以下三種元素各一段,而且要寫得夠深入(每個元素至少400字):\n"
        + "  1) 『怎麼玩』的行程建議:挑一個具體景點或活動,說明交通、路線、時間、注意事項與費用區間,並提醒讀者出發前查證官方公告\n"
        + "  2) 具體美食文化:可以介紹可查證的市場、代表性料理或店家,說明味道、價位區間與點餐注意事項,不得聲稱作者親自用餐\n"
        + "  3) 風俗民情或節慶介紹:說明生活習慣、禁忌、季節性節慶或儀式與文化脈絡,不得虛構訪談或互動故事\n"
        + "- 必須是這個城市『這個角度』獨有的深度內容,包含具體地名、店名或路線,不要空泛的觀光介紹\n"
        + "- 文章要有 3-4 個小標題(h2),依照建議時間軸或行程邏輯排列,段落之間至少穿插兩段值得摘錄的金句(pull quote)\n"
        + "- 在文中三個最適合放照片的地方,各自獨立一行插入 [IMAGE_1]、[IMAGE_2]、[IMAGE_3] 作為佔位符(依序,只能用一次)\n"
        + "- 非常重要的格式規則:body_zh_html 與 body_en_html 這兩個欄位裡的所有 HTML 標籤屬性(例如 class、href、src、target、rel)一律使用單引號,例如 <blockquote class='pull-quote'>,絕對不要在 HTML 屬性裡使用雙引號,因為這會破壞外層的 JSON 格式導致無法解析\n"
        + "- 提供 3 個對應 [IMAGE_1][IMAGE_2][IMAGE_3] 的 Unsplash 英文搜尋關鍵字(3-5個字,要能搜到符合該段落內容的真實照片)。若該張照片適合出現人物,搜尋關鍵字務必指定當地人的樣貌與文化情境(例如日本用 \"Japanese woman kimono street\"、摩洛哥用 \"Moroccan man market\",不要用沒有地域特徵的泛用人物描述如 \"person walking\"),確保照片中出現的人物與文章描述的地方一致\n"
        + "- 提供封面照片的 Unsplash 英文搜尋關鍵字(cover_image_query),若涉及人物同樣要指定當地人特徵\n"
        + "- 提供 4-6 個文章標籤(中英皆可,短詞)\n"
        + "- 標題與摘要中英各一句\n\n"
        + "- 提供實用資訊:最佳季節、建議停留天數、預算級別、主要交通、步行程度;不確定時寫『請依官方公告』\n"
        + "- 提供2-4個參考來源,只列政府觀光局、交通營運方、景點或節慶主辦單位等官方網站首頁;不能確定網址時不要編造,該筆以空字串回傳\n\n"
        + '請「只」回傳以下 JSON 格式,不要加任何 markdown 符號或說明文字:\n'
        + "{\n"
        + '  "title_zh": "...",\n'
        + '  "title_en": "...",\n'
        + '  "excerpt_zh": "...(一句話摘要,40字內)",\n'
        + '  "excerpt_en": "...",\n'
        + "  \"body_zh_html\": \"<p>...</p><h2>...</h2><p>...</p>...(內含 [IMAGE_1] [IMAGE_2] [IMAGE_3] 佔位符,以及至少兩個 <blockquote class='pull-quote'>金句</blockquote>,注意 HTML 屬性一律用單引號)\",\n"
        + '  "body_en_html": "<p>...</p>...(same structure, English, single quotes for HTML attributes)",\n'
        + '  "image_queries": {"cover_image_query": "...", "image_1": "...", "image_2": "...", "image_3": "..."},\n'
        + '  "tags": ["...", "..."],\n'
        + '  "practical_info": {"best_season": "...", "recommended_days": "...", "budget_level": "...", "transport": "...", "walking_level": "..."},\n'
        + '  "sources": [{"name": "官方來源名稱", "url": "https://..."}],\n'
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


def call_claude_with_retry(city, angle, max_attempts=3):
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            print("嘗試產生文章 (第 " + str(attempt) + " 次)...")
            return call_claude(build_prompt(city, angle))
        except json.JSONDecodeError as e:
            last_error = e
            print("JSON 解析失敗 (第 " + str(attempt) + " 次): " + str(e))
    raise SystemExit("多次嘗試後仍無法取得有效的文章 JSON: " + str(last_error))


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
        url = safe_url(info["url"])
        credit_link = safe_url(info["credit_link"])
        credit_name = safe_text(info["credit_name"], "Unsplash")
        if not url:
            body_html = body_html.replace("[IMAGE_" + str(i) + "]", "")
            continue
        figure = '<figure><img src="' + url + '" alt="" loading="lazy">'
        if credit_link:
            figure = figure + '<figcaption>Photo by <a href="' + credit_link + '" target="_blank" rel="noopener noreferrer">'
            figure = figure + credit_name + '</a> on <a href="https://unsplash.com" target="_blank" rel="noopener noreferrer">Unsplash</a></figcaption>'
        figure = figure + '</figure>'
        body_html = body_html.replace("[IMAGE_" + str(i) + "]", figure)
    return body_html


def safe_text(value, default="待補充"):
    text_value = str(value or "").strip()
    return html.escape(text_value or default, quote=True)


def safe_url(value):
    try:
        parsed = urlparse(str(value or ""))
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return html.escape(str(value), quote=True)
    except ValueError:
        pass
    return ""


def render_sources(sources):
    items = []
    for source in sources or []:
        name = safe_text(source.get("name"), "官方資訊")
        url = safe_url(source.get("url"))
        if url:
            items.append('<li><a href="' + url + '" target="_blank" rel="noopener noreferrer">' + name + '</a></li>')
    if not items:
        return "<p>本篇尚未附上可驗證的官方連結，請以目的地政府觀光與交通單位最新公告為準。</p>"
    return "<ul>" + "".join(items) + "</ul>"


def update_discovery_files(posts):
    base_url = "https://cutealbert61.github.io/albert-travel-blog/"
    published = [post for post in posts if post.get("status") == "published"]
    sitemap_urls = [base_url] + [base_url + "posts/" + post["slug"] + ".html" for post in published]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for index, url in enumerate(sitemap_urls):
        last_modified = published[index - 1].get("date") if index else datetime.date.today().isoformat()
        sitemap += "  <url><loc>" + html.escape(url) + "</loc><lastmod>" + html.escape(last_modified) + "</lastmod></url>\n"
    sitemap += "</urlset>\n"
    with open(os.path.join(SITE_DIR, "sitemap.xml"), "w", encoding="utf-8") as file:
        file.write(sitemap)

    rss = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>\n'
    rss += "<title>亞伯特的生活旅遊日誌</title><link>" + base_url + "</link><description>亞伯特的世界旅遊資料整理與靈感收藏</description>\n"
    for post in sorted(published, key=lambda item: item.get("date", ""), reverse=True)[:20]:
        url = base_url + "posts/" + post["slug"] + ".html"
        rss += "<item><title>" + html.escape(post.get("title_zh", "旅遊文章")) + "</title><link>" + html.escape(url) + "</link>"
        rss += "<guid>" + html.escape(url) + "</guid><pubDate>" + html.escape(post.get("date", "")) + "</pubDate>"
        rss += "<description>" + html.escape(post.get("excerpt_zh", "")) + "</description></item>\n"
    rss += "</channel></rss>\n"
    with open(os.path.join(SITE_DIR, "feed.xml"), "w", encoding="utf-8") as file:
        file.write(rss)


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

    article = call_claude_with_retry(city, angle)

    cover = unsplash_search(article["image_queries"]["cover_image_query"] + " " + city["city_en"])
    img1 = unsplash_search(article["image_queries"]["image_1"])
    img2 = unsplash_search(article["image_queries"]["image_2"])
    img3 = unsplash_search(article["image_queries"]["image_3"])

    body_zh = insert_images(sanitize_article_html(article["body_zh_html"]), [img1, img2, img3])
    body_en = insert_images(sanitize_article_html(article["body_en_html"]), [img1, img2, img3])

    today = datetime.date.today().isoformat()
    slug = today + "-" + slugify(city["city_en"]) + "-" + angle["key"] + "-" + datetime.datetime.now().strftime("%H%M")
    country_code = COUNTRY_CODE_MAP.get(city["country_en"], city["country_en"][:3].upper())

    tags_html = ""
    for t in article["tags"]:
        tags_html = tags_html + '<span class="tag">' + safe_text(t, "旅遊") + "</span>"

    practical = article.get("practical_info") or {}
    canonical_url = "https://cutealbert61.github.io/albert-travel-blog/posts/" + slug + ".html"

    context = {
        "TITLE_ZH": safe_text(article["title_zh"]), "TITLE_EN": safe_text(article["title_en"]),
        "EXCERPT_ZH": safe_text(article["excerpt_zh"]),
        "COVER_IMAGE": safe_url(cover["url"]), "CITY_EN": safe_text(city["city_en"]),
        "COUNTRY_CODE": country_code, "DATE": today,
        "REGION": safe_text(city["region"]), "ANGLE_ZH": safe_text(angle["zh"]), "ANGLE_EN": safe_text(angle["en"]),
        "CITY_ZH": safe_text(city["city"]), "COUNTRY_ZH": safe_text(city["country"]),
        "READING_TIME": article.get("reading_time", 12),
        "BODY_ZH": body_zh, "BODY_EN": body_en,
        "TAGS_HTML": tags_html,
        "CANONICAL_URL": canonical_url,
        "CONTENT_TYPE_LABEL": "旅遊資料整理", "TRAVEL_STATUS_LABEL": "靈感收藏",
        "FACT_CHECKED_AT": today,
        "BEST_SEASON": safe_text(practical.get("best_season")),
        "RECOMMENDED_DAYS": safe_text(practical.get("recommended_days")),
        "BUDGET_LEVEL": safe_text(practical.get("budget_level")),
        "TRANSPORT": safe_text(practical.get("transport")),
        "WALKING_LEVEL": safe_text(practical.get("walking_level")),
        "SOURCES_HTML": render_sources(article.get("sources")),
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
        "content_type": "research", "travel_status": "inspiration", "fact_checked_at": today,
        "practical_info": practical, "sources": article.get("sources") or [],
    })
    history["used_combinations"].append({"city_en": city["city_en"], "angle_key": angle["key"], "date": today})

    save_json(os.path.join(DATA_DIR, "posts.json"), posts)
    save_json(os.path.join(DATA_DIR, "history.json"), history)
    save_json(os.path.join(SITE_DIR, "data", "posts.json"), posts)
    update_discovery_files(posts)

    print("完成: docs/posts/" + slug + ".html")


if __name__ == "__main__":
    main()
