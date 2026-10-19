/* GeoConvert: клиентская логика (без фреймворков, офлайн) */
"use strict";

const $ = (id) => document.getElementById(id);
const srcSel = $("srcSel");
const dstSel = $("dstSel");
const srcText = $("srcText");
const dstText = $("dstText");
const statusEl = $("status");
const tablePanel = $("tablePanel");
const resTableBody = document.querySelector("#resTable tbody");

let projs = [];          // [{pkey, title, group}]
let lastResults = [];    // [{n_src, e_src, n_tgt, e_tgt, lat, lon}]
let debounceTimer = null;

function fmtVal(n, isDeg) {
    return isDeg ? n.toFixed(9) : n.toFixed(3);
}

function gms(deg) {
    const sign = deg < 0 ? "-" : "";
    deg = Math.abs(deg);
    const g = Math.floor(deg);
    const m0 = (deg - g) * 60;
    const m = Math.floor(m0);
    const s = (m0 - m) * 60;
    return `${sign}${g}°${m}'${s.toFixed(3)}"`;
}

function currentFmt() {
    return document.querySelector('input[name="fmt"]:checked').value;
}

function setStatus(msg, isError) {
    statusEl.textContent = msg || "";
    statusEl.className = "status" + (isError ? " error" : "");
}

function fillSelect(sel, selected) {
    const groups = {};
    for (const p of projs) {
        (groups[p.group] = groups[p.group] || []).push(p);
    }
    sel.innerHTML = "";
    const order = ["WGS84", "ПЗ-90", "СК-42", "СК-63", "МСК", "Прочее"];
    for (const g of order) {
        if (!groups[g]) continue;
        const og = document.createElement("optgroup");
        og.label = `${g} (${groups[g].length})`;
        for (const p of groups[g]) {
            const o = document.createElement("option");
            o.value = p.pkey;
            o.textContent = `${p.title} [${p.pkey}]`;
            og.appendChild(o);
        }
        sel.appendChild(og);
    }
    if (selected && [...sel.options].some((o) => o.value === selected)) sel.value = selected;
}

async function loadProjections() {
    const r = await fetch("/api/projections");
    projs = await r.json();
    let defSrc = "WGS84";
    let defDst = "EPSG:28406";
    if (!projs.some((p) => p.pkey === defDst)) defDst = projs[0].pkey;
    fillSelect(srcSel, defSrc);
    fillSelect(dstSel, defDst);
}

async function transformNow() {
    const text = srcText.value;
    if (!text.trim()) {
        dstText.value = "";
        tablePanel.hidden = true;
        updateMap([]);
        lastResults = [];
        setStatus("");
        return;
    }
    setStatus("Пересчёт…");
    try {
        const r = await fetch("/api/transform", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                source: srcSel.value,
                target: dstSel.value,
                text: text,
                fmt: currentFmt(),
                reverse: false,
            }),
        });
        const data = await r.json();
        if (data.error) {
            setStatus(data.error, true);
            tablePanel.hidden = true;
            updateMap([]);
            dstText.value = "";
            lastResults = [];
            return;
        }
        lastResults = data.results;
        const isDeg = currentFmt() === "gms";
        dstText.value = data.results
            .map((p) => (isDeg ? `${gms(p.n_tgt)},${gms(p.e_tgt)}` : `${fmtVal(p.n_tgt, false)},${fmtVal(p.e_tgt, false)}`))
            .join("\n");
        renderTable(data.results, isDeg);
        updateMap(data.results);
        setStatus(`${data.count} точек · ${srcSel.selectedOptions[0]?.textContent || ""} → ${dstSel.selectedOptions[0]?.textContent || ""}`);
    } catch (e) {
        setStatus("Ошибка запроса: " + e, true);
    }
}

function scheduleTransform() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(transformNow, 350);
}

function renderTable(results, isDeg) {
    resTableBody.innerHTML = "";
    for (let i = 0; i < results.length; i++) {
        const p = results[i];
        const tr = document.createElement("tr");
        const f = (v) => (isDeg ? gms(v) : fmtVal(v, false));
        tr.innerHTML =
            `<td>${i + 1}</td>` +
            `<td>${isDeg ? gms(p.n_src) : fmtVal(p.n_src, false)}</td>` +
            `<td>${isDeg ? gms(p.e_src) : fmtVal(p.e_src, false)}</td>` +
            `<td>${f(p.n_tgt)}</td>` +
            `<td>${f(p.e_tgt)}</td>`;
        resTableBody.appendChild(tr);
    }
    tablePanel.hidden = results.length === 0;
    document.getElementById("countLabel").textContent = `Таблица результатов: ${results.length} шт.`;
}

/* ---- карта (Leaflet + OpenStreetMap) ---- */
let map = null;
let mapLayer = null;

function updateMap(results) {
    const mapPanel = document.getElementById("mapPanel");
    const pts = results.filter((p) => p.lat != null && p.lon != null);
    if (typeof L === "undefined" || pts.length === 0) {
        mapPanel.hidden = true;
        return;
    }
    mapPanel.hidden = false;
    if (!map) {
        map = L.map("map").setView([pts[0].lat, pts[0].lon], 12);
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(map);
        mapLayer = L.layerGroup().addTo(map);
    }
    mapLayer.clearLayers();
    const bounds = [];
    for (let i = 0; i < pts.length; i++) {
        const p = pts[i];
        bounds.push([p.lat, p.lon]);
        const icon = L.divIcon({
            className: "pt-mark-wrap",
            html: String(i + 1),
            iconSize: [24, 24],
            iconAnchor: [12, 12],
        });
        L.marker([p.lat, p.lon], { icon })
            .bindPopup(
                `<b>№${i + 1}</b><br>` +
                `исходные: ${fmtVal(p.n_src, false)},${fmtVal(p.e_src, false)}<br>` +
                `результат: ${fmtVal(p.n_tgt, false)},${fmtVal(p.e_tgt, false)}`,
            )
            .addTo(mapLayer);
    }
    if (bounds.length === 1) map.setView(bounds[0], 16);
    else map.fitBounds(bounds, { padding: [30, 30], maxZoom: 17 });
    setTimeout(() => map.invalidateSize(), 100); // панель могла быть скрыта — пересчёт размера
}

/* ---- кнопки ---- */

$("switchUcs").onclick = () => {
    const a = srcSel.value;
    srcSel.value = dstSel.value;
    dstSel.value = a;
    transformNow();
};

$("revBtn").onclick = () => {
    srcText.value = srcText.value
        .split("\n")
        .map((line) => {
            const m = line.match(/^\s*(.*?)\s*[,;\t]\s*(.*?)\s*$/);
            return m ? `${m[2]},${m[1]}` : line;
        })
        .join("\n");
    scheduleTransform();
};

$("fmtSwap").onclick = async () => {
    const to = currentFmt() === "gg" ? "gms" : "gg";
    const r = await fetch("/api/convert_fmt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: srcText.value, to: to }),
    });
    const data = await r.json();
    if (data.error) {
        setStatus(data.error, true);
        return;
    }
    srcText.value = data.text;
    document.querySelector(`input[name="fmt"][value="${to}"]`).checked = true;
    transformNow();
};

function copyToClipboard(text, label) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(
        () => setStatus(`${label} скопировано в буфер`),
        () => setStatus("Не удалось скопировать (нет доступа к буферу)", true),
    );
}

$("copyRes").onclick = () => {
    const isDeg = currentFmt() === "gms";
    copyToClipboard(
        lastResults.map((p) => (isDeg ? `${gms(p.n_tgt)},${gms(p.e_tgt)}` : `${fmtVal(p.n_tgt, false)},${fmtVal(p.e_tgt, false)}`)).join("\n"),
        "Результат",
    );
};

$("copyTable").onclick = () => {
    const isDeg = currentFmt() === "gms";
    const f = (v, deg) => (deg ? gms(v) : fmtVal(v, false));
    copyToClipboard(
        lastResults.map((p) => [f(p.n_src, isDeg), f(p.e_src, isDeg), f(p.n_tgt, isDeg), f(p.e_tgt, isDeg)].join("\t")).join("\n"),
        "Таблица",
    );
};

$("kmlBtn").onclick = () => {
    if (!lastResults.length) return;
    let places = "";
    for (let i = 0; i < lastResults.length; i++) {
        const p = lastResults[i];
        if (p.lat == null || p.lon == null) continue;
        places +=
            `<Placemark><name>${i + 1}</name><description>` +
            `${fmtVal(p.n_src, false)},${fmtVal(p.e_src, false)} → ${fmtVal(p.n_tgt, false)},${fmtVal(p.e_tgt, false)}` +
            `</description><Point><coordinates>${p.lon.toFixed(9)},${p.lat.toFixed(9)},0</coordinates></Point></Placemark>`;
    }
    if (!places) {
        setStatus("KML недоступен: нет WGS84-координат", true);
        return;
    }
    const kml = `<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>GeoConvert</name>${places}</Document></kml>`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([kml], { type: "application/vnd.google-earth.kml+xml" }));
    a.download = "geconvert.kml";
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus("KML сохранён");
};

/* ---- копирование для AutoCAD (формат GeoBridge: _point / _pline + подписи) ---- */
function acNum(v) {
    return Math.abs(v) >= 1000 ? v.toFixed(3) : v.toFixed(9);
}

function buildAcText(mode) {
    if (!lastResults.length) return "";
    const pts = lastResults.map((p) => ({ e: p.e_tgt, n: p.n_tgt }));
    const cmds = [];
    if (mode === "point") {
        for (const q of pts) cmds.push(`_point ${acNum(q.e)},${acNum(q.n)}`);
    } else {
        cmds.push("_pline");
        for (const q of pts) cmds.push(`${acNum(q.e)},${acNum(q.n)}`);
        if (pts.length === 1) cmds.push(`${acNum(pts[0].e)},${acNum(pts[0].n)}`); // 1 точка: линия всё равно будет
    }
    // подписи номеров точек, как в GeoBridge: со сдвигом +1 от точки
    const texts = pts.map((q, i) => `_-text ${acNum(q.e + 1)},${acNum(q.n + 1)} 1 0 ${i + 1}`);
    return mode === "point"
        ? cmds.concat(texts).join("\n") + "\n"
        : cmds.join("\n") + "\n\n" + texts.join("\n") + "\n";
}

const acModal = $("acModal");

function showAcModal(text) {
    if (!text) {
        setStatus("Нет результатов для копирования", true);
        return;
    }
    const ta = $("acText");
    ta.value = text;
    acModal.hidden = false;
    ta.focus();
    ta.select();
}

$("acPointBtn").onclick = () => showAcModal(buildAcText("point"));
$("mapFit").onclick = () => updateMap(lastResults);
$("acPolyBtn").onclick = () => showAcModal(buildAcText("pline"));
$("acClose").onclick = () => { acModal.hidden = true; };
$("acCopy").onclick = () => copyToClipboard($("acText").value, "Для AutoCAD");
acModal.addEventListener("click", (e) => { if (e.target === acModal) acModal.hidden = true; });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !acModal.hidden) acModal.hidden = true; });

srcText.addEventListener("input", scheduleTransform);
srcSel.addEventListener("change", transformNow);
dstSel.addEventListener("change", transformNow);
document.querySelectorAll('input[name="fmt"]').forEach((el) => el.addEventListener("change", transformNow));

loadProjections().then(transformNow).catch((e) => setStatus("Ошибка загрузки проекций: " + e, true));
