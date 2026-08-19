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
        + "-
