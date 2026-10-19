# -*- coding: utf-8 -*-
"""
GeoConvert — локальный сервис пересчёта координат (МСК, СК-63, СК-42, ПЗ-90, WGS 84).

Локальная замена geobridge.ru/proj: база из 543 проекций + pyproj/PROJ.
Запуск:  python app.py   ->  http://127.0.0.1:5050
Для сетевого доступа задайте GEOCONVERT_HOST=0.0.0.0 (и GEOCONVERT_PORT при необходимости).
"""
import os

from flask import Flask, jsonify, render_template, request

import transform

APP_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

GROUP_ORDER = ["WGS84", "ПЗ-90", "СК-42", "СК-63", "МСК", "Прочее"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/projections")
def api_projections():
    db = transform.load_db()
    items = [
        {"pkey": p["pkey"], "title": p["title"], "group": p["group"]}
        for p in sorted(db.values(), key=lambda x: (GROUP_ORDER.index(x["group"]) if x["group"] in GROUP_ORDER else 99, x["title"]))
    ]
    return jsonify(items)


@app.route("/api/transform", methods=["POST"])
def api_transform():
    """
    body: {source: pkey, target: pkey, text: "N,E\\n...", fmt: "gg"|"gms", reverse: bool}
    -> {results: [{n_src, e_src, n_tgt, e_tgt}], count, error?}
    """
    body = request.get_json(force=True, silent=True) or {}
    src = body.get("source", "")
    dst = body.get("target", "")
    text = body.get("text", "")
    fmt = body.get("fmt", "gg")
    reverse = bool(body.get("reverse", False))

    try:
        points = transform.parse_points(text, fmt=fmt, reverse=reverse)
    except ValueError as e:
        return jsonify({"results": [], "count": 0, "error": f"Ошибка разбора ввода: {e}"}), 400

    if not points:
        return jsonify({"results": [], "count": 0, "error": None})

    try:
        converted = transform.transform_points(src, dst, points)
    except KeyError as e:
        return jsonify({"results": [], "count": 0, "error": str(e)}), 400
    except Exception as e:  # noqa: BLE001 — ошибки PROJ отдаем текстом
        return jsonify({"results": [], "count": 0, "error": f"Ошибка пересчёта: {e}"}), 400

    # WGS84-координаты исходных точек — для KML/отображения
    try:
        wgs = transform.transform_points(src, "WGS84", points)
    except Exception:  # noqa: BLE001
        wgs = [(None, None)] * len(points)

    results = []
    for (n_s, e_s), (n_t, e_t), (lat, lon) in zip(points, converted, wgs):
        results.append({"n_src": n_s, "e_src": e_s, "n_tgt": n_t, "e_tgt": e_t, "lat": lat, "lon": lon})
    return jsonify({"results": results, "count": len(results), "error": None})


@app.route("/api/convert_fmt", methods=["POST"])
def api_convert_fmt():
    """Пакетный перевод формата гг <-> г°м'с\" : {text, to: "gg"|"gms"} -> {text}"""
    body = request.get_json(force=True, silent=True) or {}
    text = body.get("text", "")
    to = body.get("to", "gms")
    try:
        if to == "gms":
            return jsonify({"text": transform.gg_to_gms(text)})
        return jsonify({"text": transform.gms_to_gg(text)})
    except ValueError as e:
        return jsonify({"text": "", "error": f"Ошибка перевода формата: {e}"}), 400


if __name__ == "__main__":
    transform.load_db(force=True)  # прогрев + ранняя диагностика базы
    print(f"База проекций загружена: {len(transform.load_db())} шт.")
    host = os.environ.get("GEOCONVERT_HOST", "127.0.0.1")
    port = int(os.environ.get("GEOCONVERT_PORT", "5050"))
    print(f"Сервер: http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
