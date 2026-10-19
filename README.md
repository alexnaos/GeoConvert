# GeoConvert — локальный пересчёт координат

Локальная замена [geobridge.ru/proj](https://geobridge.ru/proj): пересчёт между
МСК, СК-63 (СК-1963), СК-42 (Пулково 1942), ПЗ-90, WGS 84 и другими СК.

- **База**: 543 проекции (364 МСК, 131 СК-63, 33 СК-42, ПЗ-90, WGS84, ГСК, ПСК, УСК…),
  выгруженная из открытого API GeoBridge (`GET /proj/api`) и проверенная PROJ.
- **Движок**: [pyproj](https://pyproj4.github.io/pyproj/) (PROJ) вместо их клиентского proj4js —
  результат совпадает, математика одна и та же (transverse mercator на эллипсоиде Красовского + towgs84).
- **Карта/Яндекс API не используются** — сервис полностью автономный и офлайн.

## Запуск

```
pip install -r requirements.txt
python app.py
```

Открыть <http://127.0.0.1:5050>.

## Возможности

- Ввод: «N,E» через запятую; вставка из Excel (табуляция → запятая);
  вставка из AutoCAD (`_list`, строки `X=… Y=…`, X=север, Y=восток).
- Форматы: градусы десятичные (г.ггг) ↔ г°м'с" (кнопка «гг↔гмс»).
- Реверс N,E (обмен колонок), обмен исходной/целевой СК (⇄).
- Таблица результатов, копирование (таб-разделитель), экспорт точек в KML.
- Карта результатов (Leaflet + OpenStreetMap): нумерованные маркеры с popup,
  автоподгонка области; код Leaflet локальный (`static/vendor`), тайлы OSM
  загружаются по сети — без интернета карта остаётся пустой, сервис работает.
- Копирование для AutoCAD (как в GeoBridge): **точками** (`_point E,N`) или
  **полилинией** (`_pline` + вершины, при одной точке — сегмент замыкается),
  плюс подписи номеров точек `_-text`; вставить в командную строку Ctrl-V.

## API

| Endpoint | Метод | Тело | Ответ |
|---|---|---|---|
| `/api/projections` | GET | — | `[{pkey, title, group}]` |
| `/api/transform` | POST | `{source, target, text, fmt: "gg"\|"gms", reverse}` | `{results: [{n_src, e_src, n_tgt, e_tgt, lat, lon}], count, error}` |
| `/api/convert_fmt` | POST | `{text, to: "gg"\|"gms"}` | `{text}` |

Пример:

```
curl -X POST http://127.0.0.1:5050/api/transform -H "Content-Type: application/json" ^
  -d "{\"source\":\"EPSG:28406\",\"target\":\"WGS84\",\"text\":\"6659990,3332000\",\"fmt\":\"gg\"}"
```

## Перегенерация базы из нового дампа

```
python tools/generate_db.py   # читает C:\Temp\geobridge\proj_api_decoded.json
```

## Структура

```
app.py                — Flask: страница + 3 API-эндпоинта
transform.py          — ядро: загрузка базы, кэш трансформеров, парсеры ввода
data/projections.json — 543 проекций (pkey, title, proj4-строка, группа)
tools/generate_db.py  — генератор базы из дампа /proj/api
templates/index.html  — UI
static/app.js, style.css
```

## Оговорки

- Данные проекций (proj4-строки) собраны GeoBridge из EPSG и открытых материалов
  (ГОСТ 51794-2008, картографические документы); для локального использования.
- Результаты приближённые (как и в исходном сервисе) — не для геодезических работ.
