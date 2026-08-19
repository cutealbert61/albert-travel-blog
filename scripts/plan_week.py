#!/usr/bin/env python3
"""
每週六自動規劃下週 7 天(每天 3 篇)的旅遊文章主題,並產生 email 通知內文。
"""

import os
import json
import random
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

SLOT_TIMES = ["07:00", "12:00", "19:00"]
DAYS_AHEAD = 7


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_for_slot(locations, used_set, focus_region, focus_until, slot_date):
    cities = locations["cities"]
    if focus_region and focus_until and slot_date <= focus_until:
        focused = [c for c in cities if c["region"] == focus_region]
        if focused:
            cities = focused

    all_combos = [(c, a) for c in cities for a in locations["angles"]]
    unused = [(c, a) for c, a in all_combos if (c["city_en"], a["key"]) not in used_set]
    if unused:
        city, angle = random.choice(unused)
    else:
        city = random.choice(cities)
        angle = random.choice(locations["angles"])
    used_set.add((city["city_en"], angle["key"]))
    return city, angle


def main():
    locations = load_json(os.path.join(DATA_DIR, "locations.json"))
    history = load_json(os.path.join(DATA_DIR, "history.json"))

    used_set = set()
    for u in history.get("used_combinations", []):
        used_set.add((u["city_en"], u["angle_key"]))

    focus_region = history.get("focus_region")
    focus_until = history.get("focus_until")

    plan = []
    today = datetime.date.today()
    for d in range(1, DAYS_AHEAD + 1):
        slot_date = (today + datetime.timedelta(days=d)).isoformat()
        for t in SLOT_TIMES:
            city, angle = pick_for_slot(locations, used_set, focus_region, focus_until, slot_date)
            plan.append({
                "date": slot_date,
                "time": t,
                "city_en": city["city_en"],
                "city_zh": city["city"],
                "country_zh": city["country"],
                "region": city["region"],
                "angle_key": angle["key"],
                "angle_zh": angle["zh"],
                "status": "pending",
            })

    save_json(os.path.join(DATA_DIR, "week_plan.json"), plan)

    lines = []
    lines.append("亞伯特的生活旅遊日誌 —— 下週文章規劃")
    lines.append("")
    start_date = today + datetime.timedelta(days=1)
    end_date = today + datetime.timedelta(days=DAYS_AHEAD)
    lines.append(str(start_date) + " 至 " + str(end_date))

    current_date = None
    for item in plan:
        if item["date"] != current_date:
            current_date = item["date"]
            lines.append("")
            lines.append("【" + current_date + "】")
        lines.append("  " + item["time"] + "  " + item["country_zh"] + " " + item["city_zh"] + "  -  " + item["angle_zh"])

    lines.append("")
    lines.append("---")
    lines.append("此信件由系統自動產生。網站: https://cutealbert61.github.io/albert-travel-blog/")

    body = "\n".join(lines)
    with open(os.path.join(ROOT, "week_plan_email.txt"), "w", encoding="utf-8") as f:
        f.write(body)

    print(body)


if __name__ == "__main__":
    main()
