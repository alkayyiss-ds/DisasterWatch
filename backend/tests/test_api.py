"""Tes API Prediksi Dampak. Jalankan dari root repo:  pytest backend/tests -q"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["model_dimuat"] is True


def test_meta(client):
    m = client.get("/api/prediksi/meta").json()
    assert len(m["opsi"]["provinsi"]) == 38
    assert len(m["opsi"]["bulan"]) == 12
    assert m["kelas"] == ["Tanpa Dampak", "Ringan", "Sedang", "Berat"]
    assert 0.5 < m["model"]["metrik"]["accuracy"] < 1
    assert abs(sum(f["bobot"] for f in m["faktor_risiko"]) - 1) < 0.01


@pytest.mark.parametrize("body", [
    {"jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": "Januari", "kepadatan_penduduk": "Sedang"},
    {"jenis_bencana": "KEBAKARAN HUTAN DAN LAHAN", "provinsi": "RIAU", "bulan": 8},
    {"jenis_bencana": "Gempa bumi", "provinsi": "33", "bulan": "7", "kepadatan_penduduk": "sangat tinggi"},
    {"jenis_bencana": "Kekeringan", "provinsi": "Papua Selatan", "bulan": "September", "tahun": 2027},
])
def test_prediksi_valid(client, body):
    r = client.post("/api/prediksi", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    p = j["prediksi"]
    assert p["kelas"] in ["Tanpa Dampak", "Ringan", "Sedang", "Berat"]
    assert abs(sum(x["p"] for x in p["peluang"]) - 1) < 1e-3
    assert p["probabilitas"] == max(x["p"] for x in p["peluang"])
    assert 1 <= len(j["mitigasi"]) <= 6
    assert j["estimasi"]["tersedia"]


def test_karhutla_umumnya_tanpa_dampak(client):
    j = client.post("/api/prediksi", json={"jenis_bencana": "Karhutla", "provinsi": "Riau", "bulan": "Agustus"}).json()
    assert j["prediksi"]["kelas"] == "Tanpa Dampak"


@pytest.mark.parametrize("body", [
    {"jenis_bencana": "Meteor", "provinsi": "Jawa Tengah", "bulan": 1},
    {"jenis_bencana": "Banjir", "provinsi": "Atlantis", "bulan": 1},
    {"jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": 13},
    {"jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": "Smarch"},
    {"jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": 1, "kepadatan_penduduk": "Padat sekali"},
])
def test_prediksi_input_salah(client, body):
    assert client.post("/api/prediksi", json=body).status_code == 422


def test_frontend_disajikan(client):
    assert client.get("/").status_code == 200
    assert client.get("/js/app.js").status_code == 200
