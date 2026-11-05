"""Bandingkan model JavaScript (frontend/js/model/) dengan backend. Butuh Node.js.

Jalankan dari root repo:
    pytest backend/tests/test_js_model.py -q                 # sampel 400 kombinasi input
    DW_JS_FULL=1 pytest backend/tests/test_js_model.py -q    # seluruh 4.560 kombinasi
"""
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app  # noqa: E402
from dw_model import BULAN, JENIS_ALIASES, JENIS_LABELS, MODEL_DIR  # noqa: E402
import mitigasi  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MODEL_JS = ROOT / "frontend" / "js" / "model"

NODE_RUNNER = r"""
const fs = require('fs'), vm = require('vm');
globalThis.window = globalThis;
for (const f of ['rf_forest.js', 'dw_lookup.js', 'dw_model.js']) vm.runInThisContext(fs.readFileSync(process.argv[2] + '/' + f, 'utf8'), { filename: f });
const inp = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const run = f => { try { return { ok: f() }; } catch (e) { return { error: e.name, status: e.status || null, message: e.message }; } };
fs.writeFileSync(process.argv[4], JSON.stringify({
  prediksi: inp.prediksi.map(b => run(() => DWModel.prediksi(b))),
  mitigasi: inp.mitigasi.map(a => run(() => DWModel.mitigasi(a[0], a[1], a[2], a[3]))),
  opsi: DWModel.opsi(),
}));
"""

pytestmark = pytest.mark.skipif(shutil.which("node") is None or not (MODEL_JS / "rf_forest.js").exists(),
                                reason="butuh Node.js dan hasil `python backend/export_js_model.py`")


def run_js(tmp_path, prediksi=(), mitigasi_args=()):
    runner, inp, out = tmp_path / "runner.js", tmp_path / "in.json", tmp_path / "out.json"
    runner.write_text(NODE_RUNNER, encoding="utf-8")
    inp.write_text(json.dumps({"prediksi": list(prediksi), "mitigasi": list(mitigasi_args)}), encoding="utf-8")
    subprocess.run(["node", str(runner), str(MODEL_JS), str(inp), str(out)], check=True)
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def lookup():
    return json.loads((MODEL_DIR / "lookup.json").read_text(encoding="utf-8"))


def semua_input(lookup):
    """Semua kombinasi jenis × provinsi × bulan, dengan variasi bentuk penulisan input."""
    alias = {v: k for k, v in JENIS_ALIASES.items()}
    bodies, i = [], 0
    for p in lookup["provinsi"]:
        for kode, label in JENIS_LABELS.items():
            for b in range(1, 13):
                bodies.append({"jenis_bencana": (label, kode, alias.get(kode, label))[i % 3],
                               "provinsi": (p["label"], p["provinsi"])[i % 2],
                               "bulan": (BULAN[b - 1], str(b), BULAN[b - 1].upper())[i % 3],
                               "kepadatan": "Sedang"})
                i += 1
    return bodies


def test_prediksi_js_sama_dengan_api(client, lookup, tmp_path):
    bodies = semua_input(lookup)
    if not os.environ.get("DW_JS_FULL"):
        bodies = random.Random(42).sample(bodies, 400)
    js = run_js(tmp_path, prediksi=bodies)["prediksi"]
    beda = []
    for body, r in zip(bodies, js):
        api = client.post("/api/prediksi", json=body).json()
        if "ok" not in r or r["ok"] != api:
            beda.append((body, r, api))
    assert not beda, f"{len(beda)} dari {len(bodies)} input berbeda, contoh: {beda[0]}"


def test_mitigasi_js_sama_dengan_mitigasi_py(lookup, tmp_path):
    k = lookup["klaster"]
    args, harapan = [], []
    for p in lookup["provinsi"]:
        prof = k["provinsi"].get(str(p["id_prov"])) if k.get("tersedia") else None
        for kode, label in JENIS_LABELS.items():
            for kep in ["Rendah", "Sedang", "Tinggi", "Sangat tinggi"]:
                for t in range(4):
                    args.append([t, label, kep, p["label"]])
                    harapan.append(mitigasi.rekomendasi(t, kode, kep, prof["dominan"] if prof else None))
    js = run_js(tmp_path, mitigasi_args=args)["mitigasi"]
    beda = [(a, r, h) for a, r, h in zip(args, js, harapan) if "ok" not in r or r["ok"]["rekomendasi"] != h]
    assert not beda, f"{len(beda)} dari {len(args)} berbeda, contoh: {beda[0]}"


def test_js_menolak_input_salah(client, tmp_path):
    salah = [
        {"jenis_bencana": "Meteor", "provinsi": "Jawa Tengah", "bulan": "Januari"},
        {"jenis_bencana": "Banjir", "provinsi": "Atlantis", "bulan": "Januari"},
        {"jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": "13"},
        {"jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": "Smarch"},
    ]
    hasil = run_js(tmp_path, prediksi=salah)["prediksi"]
    for body, r in zip(salah, hasil):
        api = client.post("/api/prediksi", json=body)
        assert r.get("error") == "InputError" and r["status"] == api.status_code == 400
        assert r["message"] == api.json()["detail"]


def test_opsi_dropdown(tmp_path):
    o = run_js(tmp_path)["opsi"]
    assert len(o["provinsi"]) == 38 and len(o["bulan"]) == 12
    assert [j["label"] for j in o["jenis"]] == [v for k, v in JENIS_LABELS.items() if k != "GEMPA BUMI DAN TSUNAMI"]
