# -*- coding: utf-8 -*-
"""
Ядро пересчёта координат (замена клиентского proj4js + transformCtrl GeoBridge).

- База проекций: data/projections.json (543 СК из базы GeoBridge + WGS84).
- Пересчёт: pyproj (PROJ) с always_xy=True — на входе всегда (E, N),
  как в исходном сервисе: строка ввода "N,E" -> Point(E, N).
- Парсеры ввода: текст "N,E", Excel (таб -> запятая), AutoCAD _list (X=.. Y=..).
"""
from __future__ import annotations

import json
import os
import re
import threading

from pyproj import CRS, Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "data", "projections.json")

_lock = threading.Lock()
_db: dict[str, dict] | None = None
_transformers: dict[tuple[str, str], Transformer] = {}


def load_db(force: bool = False) -> dict[str, dict]:
    """Ленивая загрузка базы проекций: pkey -> запись."""
    global _db
    with _lock:
        if _db is None or force:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                items = json.load(f)
            _db = {p["pkey"]: p for p in items if p.get("valid")}
        return _db


def get_transformer(src_key: str, dst_key: str) -> Transformer:
    """Кэшированный трансформер PROJ между двумя проекциями из базы."""
    db = load_db()
    if src_key not in db:
        raise KeyError(f"Неизвестная проекция-источник: {src_key}")
    if dst_key not in db:
        raise KeyError(f"Неизвестная проекция-приёмник: {dst_key}")
    key = (src_key, dst_key)
    tr = _transformers.get(key)
    if tr is None:
        src = CRS.from_proj4(db[src_key]["proj4"])
        dst = CRS.from_proj4(db[dst_key]["proj4"])
        tr = Transformer.from_crs(src, dst, always_xy=True)
        _transformers[key] = tr
    return tr


def transform_points(src_key: str, dst_key: str, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Пересчёт списка точек. points: [(N, E), ...] -> [(N, E), ...]."""
    tr = get_transformer(src_key, dst_key)
    out = []
    for n, e in points:
        # always_xy -> вход (x=E, y=N), выход (E, N)
        e2, n2 = tr.transform(e, n)
        out.append((n2, e2))
    return out


# ---------------------------------------------------------------------------
# Парсеры ввода
# ---------------------------------------------------------------------------

AC_RE = re.compile(r"X=\s*([-\d.eE+]+)\s+Y=\s*([-\d.eE+]+)")


def parse_points(text: str, fmt: str = "gg", reverse: bool = False) -> list[tuple[float, float]]:
    """
    Разобрать текст в точки [(N, E), ...].

    Поддерживаемые форматы строк:
      - "N,E" / "N;E" / "N<TAB>E" (Excel);
      - градусы-минуты-секунды: 59°56'33.6",30°18'40.9" (fmt="gms");
      - AutoCAD _list: "... X= 123.4 Y= 567.8 Z= 0 ..." (X=север, Y=восток).
    reverse=True — поменять N,E местами перед разбором (реверс колонок).
    """
    if fmt == "gms":
        return _parse_gms(text, reverse)
    return _parse_gg(text, reverse)


def _fmt_coord(tok: str) -> float:
    """'59,56,33.6' -> 59.942666 (гг); поддержка ° ' " и ʺ ′ ″."""
    t = (tok.strip()
         .replace("″", '"').replace("ʺ", '"')
         .replace("′", "'").replace("ʹ", "'")
         .replace("º", "°").replace("N", "").replace("E", "").strip())
    if "°" not in t:
        return float(t.replace(",", "."))
    parts = t.split("°")
    g = float(parts[0])
    rest = parts[1]
    m_part = rest.split("'")
    m = float(m_part[0]) if m_part[0] else 0.0
    s = 0.0
    if len(m_part) > 1 and m_part[1].strip('" '):
        s = float(m_part[1].strip('" '))
    val = g + m / 60.0 + s / 3600.0
    return -val if g < 0 else val


def _fmt_gms(deg: float, nd: int = 3) -> str:
    """59.942666 -> 59°56'33.600\""""
    sign = "-" if deg < 0 else ""
    deg = abs(deg)
    g = int(deg)
    m0 = (deg - g) * 60
    m = int(m0)
    s = (m0 - m) * 60
    return f"{sign}{g}°{m}'{s:.{nd}f}\""


def _split_rows(text: str) -> list[str]:
    return [r for r in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if r.strip()]


def _parse_gg(text: str, reverse: bool) -> list[tuple[float, float]]:
    points = []
    for row in _split_rows(text):
        if AC_RE.search(row):
            m = AC_RE.search(row)
            n, e = float(m.group(1)), float(m.group(2))
            points.append((e, n) if reverse else (n, e))
            continue
        if not row.strip():
            continue
        t = row.replace("\t", ",").replace(";", ",").strip()
        # разделитель — запятая (возможны пустые поля у двойных разделителей)
        parts = [p.strip() for p in t.split(",") if p.strip() != ""]
        if len(parts) < 2:
            parts = re.split(r"\s{2,}", t, maxsplit=1)
            parts = [p.strip() for p in parts if p.strip()]
        if len(parts) < 2:
            continue
        if len(parts) > 2:
            # сквозная нумерация / лишняя колонка в начале строки
            parts = parts[1:]
        n = float(parts[0].replace(",", "."))
        e = float(parts[1].replace(",", "."))
        points.append((e, n) if reverse else (n, e))
    return points


def _parse_gms(text: str, reverse: bool) -> list[tuple[float, float]]:
    points = []
    for row in _split_rows(text):
        if AC_RE.search(row):
            m = AC_RE.search(row)
            n, e = float(m.group(1)), float(m.group(2))
            points.append((e, n) if reverse else (n, e))
            continue
        t = row.replace("\t", ",").replace(";", ",").strip()
        parts = [p.strip() for p in t.split(",") if p.strip()]
        if len(parts) < 2:
            continue
        n = _fmt_coord(parts[0])
        e = _fmt_coord(parts[1])
        points.append((e, n) if reverse else (n, e))
    return points


def gg_to_gms(text: str) -> str:
    """Пакетный перевод гг -> г°м'с\" по двум колонкам."""
    return "\n".join(f"{_fmt_gms(n)},{_fmt_gms(e)}" for n, e in parse_points(text, "gg"))


def gms_to_gg(text: str) -> str:
    """Пакетный перевод г°м'с\" -> гг по двум колонкам."""
    return "\n".join(f"{n:.9f},{e:.9f}" for n, e in parse_points(text, "gms"))
