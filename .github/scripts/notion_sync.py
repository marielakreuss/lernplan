#!/usr/bin/env python3
"""
notion_sync.py – GitHub Actions Version
Liest Fälle aus Notion, erzeugt notion-data.js (ohne Anki).
"""

import json
import os
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import date, datetime

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID  = "268539e733aa806e856cec92f278d2b9"
PLAN_START   = date(2025, 9, 29)

ANKI_FOKUS_ZYKLUS = [
    ["StrafR BT",     "KommunalR"],
    ["StrafR AT",     "HandelsR"],
    ["Staatsrecht",   "StaatshaftungsR"],
    ["ZPO I",         "VerwaltungsR AT"],
    ["SachenR",       "Erbrecht"],
    ["ArbeitsR",      "ZPO II"],
    ["BGB AT",        "SchuldR BT"],
    ["EuropaR",       "GesellschaftsR"],
    ["Familienrecht", "PolizeiR"],
    ["Grundrechte",   "SchuldR AT"],
]


def get_week(d: date) -> int:
    return max(1, (d - PLAN_START).days // 7 + 1)


def notion_query(cursor=None) -> dict:
    url  = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    body = {"page_size": 100}
    if cursor:
        body["start_cursor"] = cursor
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization":  f"Bearer {NOTION_TOKEN}",
            "Content-Type":   "application/json",
            "Notion-Version": "2022-06-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def extract_cases() -> list:
    cases, cursor = [], None
    while True:
        data = notion_query(cursor)
        for page in data.get("results", []):
            props = page.get("properties", {})

            title_arr = props.get("Klausur", {}).get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_arr).strip()
            if not title:
                continue

            status_obj = (props.get("Status", {}).get("status") or {})
            status = status_obj.get("name", "Nicht nachbereitet")

            datum_obj = (props.get("Datum", {}).get("date") or {})
            datum_str = datum_obj.get("start", "")
            woche = None
            if datum_str:
                try:
                    woche = get_week(date.fromisoformat(datum_str[:10]))
                except ValueError:
                    pass

            rg_arr = props.get("Rechtsgebiet", {}).get("multi_select", [])
            rechtsgebiet = [r["name"] for r in rg_arr]

            fach_obj = (props.get("Fach", {}).get("select") or {})
            fach = fach_obj.get("name", "")

            typ_obj = (props.get("Typ", {}).get("status") or {})
            typ = typ_obj.get("name", "")

            bewertung = props.get("Bewertung", {}).get("number")
            abgegeben = bool(props.get("Abgegeben", {}).get("checkbox", False))

            cases.append({
                "title":        title,
                "status":       status,
                "woche":        woche,
                "datum":        datum_str[:10] if datum_str else None,
                "rechtsgebiet": rechtsgebiet,
                "fach":         fach,
                "typ":          typ,
                "bewertung":    bewertung,
                "abgegeben":    abgegeben,
                "url":          page.get("url", ""),
            })

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return cases


def main():
    print("Lade Fälle von Notion …")
    cases = extract_cases()

    nachbereitet   = sum(1 for c in cases if c["status"] == "Nachbereitet")
    in_bearbeitung = sum(1 for c in cases if c["status"] == "In Bearbeitung")
    klk_gesamt     = sum(1 for c in cases if c["typ"] == "Klausurenkurs")
    klk_abgegeben  = sum(1 for c in cases if c["typ"] == "Klausurenkurs" and c["abgegeben"])
    nachbereitet_hk = sum(1 for c in cases if c["typ"] == "Hauptkurs" and c["status"] == "Nachbereitet")

    anki_fokus = {}
    for w in range(36, 85):
        anki_fokus[str(w)] = ANKI_FOKUS_ZYKLUS[(w - 36) % len(ANKI_FOKUS_ZYKLUS)]

    # Alte Anki-Daten aus der aktuellen notion-data.js lesen und behalten
    old_anki = None
    try:
        with open("notion-data.js", "r", encoding="utf-8") as f:
            content = f.read()
        json_str = content.replace("// Automatisch generiert von GitHub Actions\n", "").replace("window.NOTION_DATA = ", "").rstrip(";\n")
        old_anki = json.loads(json_str).get("anki")
    except Exception:
        pass

    payload = {
        "lastSync":    datetime.now().strftime("%d.%m.%Y %H:%M"),
        "anki":        old_anki,
        "ankiFokus":   anki_fokus,
        "rhythmCheck": {"currentWeek": get_week(date.today()), "nachbereitet": nachbereitet_hk},
        "cases":       cases,
        "stats": {
            "nachbereitet":  nachbereitet,
            "inBearbeitung": in_bearbeitung,
            "total":         len(cases),
            "klkGesamt":     klk_gesamt,
            "klkAbgegeben":  klk_abgegeben,
        },
    }

    content = ("// Automatisch generiert von GitHub Actions\n"
               f"window.NOTION_DATA = {json.dumps(payload, ensure_ascii=False, indent=2)};\n")

    with open("notion-data.js", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✓ {len(cases)} Fälle · Nachbereitet: {nachbereitet} · In Bearbeitung: {in_bearbeitung}")


if __name__ == "__main__":
    main()
