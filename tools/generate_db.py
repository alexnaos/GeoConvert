# -*- coding: utf-8 -*-
"""
Генератор data/projections.json из дампа /proj/api сервиса GeoBridge.
Вход:  proj_api_decoded.json  {"data": [ {pkey, title, str, proj, ...}, ... ], "ellipses": [...]}
Выход: data/projections.json  [ {pkey, title, proj4, group, valid, error} ... ]

+title= (кириллица, пробелы) вычищается из proj4-строки — pyproj/PROJ его
не любит; название остаётся в поле title. Каждая проекция проверяется
через pyproj.CRS.from_proj4, битые помечаются valid=false.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(os.environ.get("GEODUMP", r"C:\Temp\geobridge"), "proj_api_decoded.json")
DST = os.path.join(ROOT, "data", "projections.json")

TITLE_RE = re.compile(r"\+title=.*?(?=\s*\+[A-Za-z0-9_]+=|\s*$)", re.S)


def clean_proj4(s: str) -> str:
    """Убрать +title=... из proj4-строки, нормализовать пробелы."""
    s = TITLE_RE.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def classify(title: str, pkey: str) -> str:
    t = title.upper()
    if "WGS" in t:
        return "WGS84"
    if "ПЗ" in t or "PZ" in t:
        return "ПЗ-90"
    if "СК-1963" in title or "СК-63" in title or "СК 63" in title:
        return "СК-63"
    if "ПУЛКОВО 1942" in t or "СК-1942" in title or "СК-42" in title or "СК 42" in title:
        return "СК-42"
    if "МСК" in title or "МСК" in t:
        return "МСК"
    return "Прочее"


def main():
    if not os.path.exists(SRC):
        sys.exit(f"Нет входного файла: {SRC}")

    with open(SRC, "r", encoding="utf-8-sig") as f:
        dump = json.load(f)

    # поздний импорт — чтобы ошибка «нет pyproj» была понятной
    from pyproj import CRS

    # WGS84 в API отсутствует — GeoBridge подставляет его на клиенте руками
    dump.setdefault("data", []).append({
        "pkey": "WGS84",
        "title": "WGS 84",
        "str": "+proj=longlat +datum=WGS84 +no_defs",
    })

    out = []
    seen = set()
    n_bad = 0
    for item in dump.get("data", []):
        pkey = item.get("pkey", "").strip()
        title = (item.get("title") or pkey).strip()
        str_ = (item.get("str") or "").strip()
        if not pkey or not str_ or pkey in seen:
            continue
        seen.add(pkey)

        proj4 = clean_proj4(str_)
        valid, err = True, None
        try:
            CRS.from_proj4(proj4)
        except Exception as e:  # noqa: BLE001 — фиксируем любую ошибку PROJ
            valid, err = False, str(e).splitlines()[0][:200]
            n_bad += 1

        out.append({
            "pkey": pkey,
            "title": title,
            "proj4": proj4,
            "group": classify(title, pkey),
            "valid": valid,
            "error": err,
        })

    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    groups = {}
    for p in out:
        groups[p["group"]] = groups.get(p["group"], 0) + 1
    print(f"OK: {len(out)} проекций -> {DST}")
    print(f"битых (не собрался pyproj): {n_bad}")
    for g, c in sorted(groups.items()):
        print(f"  {g}: {c}")


if __name__ == "__main__":
    main()
