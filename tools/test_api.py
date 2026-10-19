# -*- coding: utf-8 -*-
"""Интеграционный тест API: сам запускает app.py, гоняет HTTP-запросы, гасит сервер.
python tools/test_api.py
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = "http://127.0.0.1:5050"


def wait_port(host: str, port: int, timeout: float = 15.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def req(path: str, body: dict | None = None) -> tuple[int, dict | list]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(BASE + path, data=data,
                               headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def main():
    proc = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert wait_port("127.0.0.1", 5050), "сервер не поднялся за 15с"

        # страница
        with urllib.request.urlopen(BASE + "/", timeout=10) as r:
            html = r.read().decode("utf-8")
        assert r.status == 200 and "GeoConvert" in html, "страница / не отдаётся"

        # список проекций
        status, pr = req("/api/projections")
        assert status == 200 and len(pr) >= 543, f"projections: {status} {len(pr)}"

        # СК-42 з6 -> WGS84 (Эрмитаж)
        status, tr = req("/api/transform", {
            "source": "EPSG:28406", "target": "WGS84",
            "text": "6650398.84,6350117.90\n6650498.84,6350217.90", "fmt": "gg"})
        assert status == 200 and tr["error"] is None and tr["count"] == 2, f"transform: {status} {tr}"
        p0 = tr["results"][0]
        assert abs(p0["n_tgt"] - 59.9387) < 0.001 and abs(p0["e_tgt"] - 30.3162) < 0.001, p0
        assert abs(p0["lat"] - 59.9387) < 0.001, p0  # lat/lon (WGS) для KML

        # ввод из AutoCAD (_list), МСК СБ -> СК-42 з6
        status, ac = req("/api/transform", {
            "source": "GB:2138", "target": "EPSG:28406",
            "text": "Точка X= 24333.42 Y= 32213.55 Z= 0.0", "fmt": "gg"})
        assert status == 200 and ac["error"] is None and ac["count"] == 1, f"autocad: {status} {ac}"
        # (59.90, 29.10) -> СК-42 з6: эталон N=6649474.3, E=6281930.8
        assert abs(ac["results"][0]["n_tgt"] - 6649474.3) < 500, ac["results"][0]
        assert abs(ac["results"][0]["e_tgt"] - 6281930.8) < 500, ac["results"][0]

        # гг -> г°м'с"
        status, fm = req("/api/convert_fmt", {"text": "59.942666667,30.311361111", "to": "gms"})
        assert status == 200 and "59°56'33.600" in fm["text"], f"fmt: {status} {fm}"

        # ошибка: неизвестная проекция -> 400
        status, er = req("/api/transform", {"source": "NOPE:1", "target": "WGS84", "text": "1,2"})
        assert status == 400 and er["error"], f"err handling: {status} {er}"

        print("ВСЕ API-ПРОВЕРКИ ПРОЙДЕНЫ")
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
