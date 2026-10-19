# -*- coding: utf-8 -*-
"""Быстрые проверки ядра GeoConvert: python tools/test_transform.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import transform  # noqa: E402


def approx(a, b, tol):
    assert abs(a - b) <= tol, f"{a} != {b} (tol {tol})"


def main():
    transform.load_db(force=True)

    # --- парсер: чистый текст N,E
    assert transform.parse_points("6659990.5,3332000.2") == [(6659990.5, 3332000.2)]

    # --- Excel: табуляция
    assert transform.parse_points("6659990\t3332000") == [(6659990, 3332000)]

    # --- нумерованные строки
    assert transform.parse_points("1\t6659990\t3332000\n2\t6660000\t3333000") == [
        (6659990, 3332000), (6660000, 3333000)]

    # --- AutoCAD _list: X=N, Y=E (как в GeoBridge)
    assert transform.parse_points("Точка X= 6659990 Y= 3332000 Z= 0.0") == [(6659990, 3332000)]

    # --- реверс N,E
    assert transform.parse_points("6659990,3332000", reverse=True) == [(3332000, 6659990)]

    # --- градусы-минуты-секунды
    pts = transform.parse_points('59°56\'33.6",30°18\'40.9"', fmt="gms")
    approx(pts[0][0], 59 + 56 / 60 + 33.6 / 3600, 1e-6)
    approx(pts[0][1], 30 + 18 / 60 + 40.9 / 3600, 1e-6)

    # --- гг <-> гмс roundtrip
    s = "59.942666667,30.311361111"
    back = transform.gms_to_gg(transform.gg_to_gms(s))
    approx(float(back.split(",")[0]), 59.942666667, 1e-6)
    approx(float(back.split(",")[1]), 30.311361111, 1e-6)

    # --- СК-42 зона 6 (Пулково, Ленобласть) -> WGS84: точка у Эрмитажа
    # эталон: WGS84->СК-42 з6: N=6650398.84, E=6350117.90 (в зоне 6 x_0=6.5 млн)
    (n_wgs, e_wgs) = transform.transform_points("EPSG:28406", "WGS84", [(6650398.84, 6350117.90)])[0]
    approx(n_wgs, 59.9387, 0.001)
    approx(e_wgs, 30.3162, 0.001)

    # --- обратный: WGS84 -> СК-42 з6
    (n_sk, e_sk) = transform.transform_points("WGS84", "EPSG:28406", [(59.9387, 30.3162)])[0]
    approx(n_sk, 6650398.84, 2)
    approx(e_sk, 6350117.90, 2)

    # --- МСК Сосновый Бор (GB:2138) -> WGS84: планшетная точка города (59.90, 29.10)
    # эталон: WGS84->МСК-СБ: N=24333.42, E=32213.55 (координаты от нуля МСК)
    (n_sb, e_sb) = transform.transform_points("GB:2138", "WGS84", [(24333.42, 32213.55)])[0]
    approx(n_sb, 59.90, 0.005)
    approx(e_sb, 29.10, 0.005)

    # --- ПЗ-90 -> WGS84: практически тождественно
    (n_pz, e_pz) = transform.transform_points("EPSG:4740", "WGS84", [(59.9387, 30.3162)])[0]
    approx(n_pz, 59.9387, 0.001)
    approx(e_pz, 30.3162, 0.001)

    # --- неизвестная проекция
    try:
        transform.get_transformer("NOPE:1", "WGS84")
        raise AssertionError("ожидали KeyError")
    except KeyError:
        pass

    print("ВСЕ ПРОВЕРКИ ЯДРА ПРОЙДЕНЫ")


if __name__ == "__main__":
    main()
