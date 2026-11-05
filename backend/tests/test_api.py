"""Tes API DisasterWatch (backend/app.py + extra_api.py). Jalankan dari root repo:  pytest backend/tests -q

Butuh artefak model (python backend/train_model.py) dan data di data/processed/.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app  # noqa: E402

KELAS = ["Tanpa Dampak", "Ringan", "Sedang", "Berat"]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_dashboard_data(client):
    r = client.get("/api/dashboard-data")
    assert r.status_code == 200, r.text
    j = r.json()
    assert 50 < j["kpi"]["akurasi"] < 100            # persen
    assert j["kpi"]["wilayah"] > 0
    assert len(j["monthly"]["values"]) == 12
    assert abs(sum(j["feature"]["values"]) - 1) < 0.01


@pytest.mark.parametrize("path", ["/api/overview", "/api/overview?tahun=-1&dari=2020", "/api/extra",
                                  "/api/tren", "/api/laporan"])
def test_endpoint_lain(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("body", [
    {"jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": "Januari", "kepadatan": "Sedang"},
    {"jenis_bencana": "KEBAKARAN HUTAN DAN LAHAN", "provinsi": "RIAU", "bulan": "8"},
    {"jenis_bencana": "gempa", "provinsi": "Daerah Istimewa Yogyakarta", "bulan": "juli"},
    {"jenis_bencana": "Kekeringan", "provinsi": "Papua Selatan", "bulan": "September"},
])
def test_prediksi_valid(client, body):
    r = client.post("/api/prediksi", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["tingkat"] in range(4) and j["label"] == KELAS[j["tingkat"]]
    assert len(j["probabilitas"]) == 4 and abs(sum(j["probabilitas"]) - 100) <= 2
    assert j["probabilitas"][j["tingkat"]] == max(j["probabilitas"])
    if j["rentang"] is not None:
        assert j["n_historis"] >= 5
        assert all(len(v) == 2 and v[0] <= v[1] for v in j["rentang"].values())


def test_karhutla_umumnya_tanpa_dampak(client):
    j = client.post("/api/prediksi", json={"jenis_bencana": "Karhutla", "provinsi": "Riau", "bulan": "Agustus"}).json()
    assert j["label"] == "Tanpa Dampak"


@pytest.mark.parametrize("body", [
    {"jenis_bencana": "Meteor", "provinsi": "Jawa Tengah", "bulan": "Januari"},
    {"jenis_bencana": "Banjir", "provinsi": "Atlantis", "bulan": "Januari"},
    {"jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": "13"},
    {"jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": "Smarch"},
])
def test_prediksi_input_salah(client, body):
    assert client.post("/api/prediksi", json=body).status_code == 400
