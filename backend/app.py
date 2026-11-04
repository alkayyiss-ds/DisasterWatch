"""
DisasterWatch — Backend API untuk halaman "Prediksi Dampak".

Menjalankan (dari root repo):
    uvicorn backend.app:app --reload --port 8000
lalu buka  http://localhost:8000          (dashboard)
           http://localhost:8000/docs     (dokumentasi & uji coba API)

Endpoint:
    GET  /api/health          status server & model
    GET  /api/prediksi/meta   opsi dropdown, metrik model, faktor risiko, ringkasan klaster
    POST /api/prediksi        prediksi tingkat dampak + estimasi + rekomendasi mitigasi
"""
from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parent))   # agar modul lokal bisa diimpor dari root repo
from dw_model import (BULAN, FRONTEND_DIR, JENIS_ALIASES, MODEL_DIR, SEV_LABELS,  # noqa: E402
                      jenis_display, make_inference_row)
from mitigasi import jumlah_rekomendasi, rekomendasi  # noqa: E402

log = logging.getLogger("disasterwatch")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

KEPADATAN = ["Rendah", "Sedang", "Tinggi", "Sangat tinggi"]
BADGE = {0: ("green", "Dampak Rendah"), 1: ("blue", "Dampak Ringan"), 2: ("orange", "Dampak Sedang"), 3: ("red", "Dampak Berat")}
STATE: dict = {}


# ══════════════════════════════════════════════════════════════════════════════
# Muat model saat server mulai
# ══════════════════════════════════════════════════════════════════════════════
def load_artifacts() -> None:
    files = [MODEL_DIR / n for n in ("rf_severity.joblib", "model_meta.json", "lookup.json")]
    if not all(f.exists() for f in files):
        log.warning("Artefak model belum ada → melatih model terlebih dahulu (±1 menit)...")
        import train_model
        train_model.main()
    STATE["model"] = joblib.load(files[0])
    STATE["meta"] = json.loads(files[1].read_text(encoding="utf-8"))
    lookup = json.loads(files[2].read_text(encoding="utf-8"))
    STATE["lookup"] = lookup
    STATE["prov_by_key"] = {}
    for p in lookup["provinsi"]:          # terima kode BNPB ('JAWA TENGAH'), label ('Jawa Tengah'), atau id ('33')
        for key in (p["provinsi"], p["label"], str(p["id_prov"])):
            STATE["prov_by_key"][key.lower()] = p
    STATE["jenis_by_key"] = {}
    for j in lookup["jenis"]:
        STATE["jenis_by_key"][j["value"].lower()] = j["value"]
        STATE["jenis_by_key"][j["label"].lower()] = j["value"]
    for alias, code in JENIS_ALIASES.items():
        if code.lower() in STATE["jenis_by_key"]:
            STATE["jenis_by_key"][alias] = code
    ev = STATE["meta"]["evaluasi"]
    log.info("Model dimuat: %s | accuracy uji %.3f | MSE %.4f", STATE["meta"]["nama_model"], ev["accuracy"], ev["mse"])


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_artifacts()
    yield


app = FastAPI(title="DisasterWatch API", version="1.0",
              description="Prediksi tingkat dampak bencana (Random Forest) untuk halaman Prediksi Dampak.",
              lifespan=lifespan)
# Izinkan frontend dibuka langsung dari file (origin "null") atau dari server lain saat pengembangan
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


# ══════════════════════════════════════════════════════════════════════════════
# Skema request
# ══════════════════════════════════════════════════════════════════════════════
class PrediksiRequest(BaseModel):
    jenis_bencana: str = Field(..., examples=["Banjir"], description="Kode BNPB (BANJIR) atau label (Banjir, Karhutla, Gempa bumi, ...)")
    provinsi: str = Field(..., examples=["Jawa Tengah"], description="Nama provinsi (Jawa Tengah / JAWA TENGAH) atau id_prov (33)")
    bulan: int | str = Field(..., examples=["Januari"], description="Nama bulan (Januari) atau angka 1–12")
    kepadatan_penduduk: str | None = Field("Sedang", examples=["Sedang"], description="Rendah / Sedang / Tinggi / Sangat tinggi (hanya untuk rekomendasi mitigasi)")
    tahun: int | None = Field(None, ge=2015, le=2035, description="Tahun kejadian; default tahun berjalan")

    @field_validator("bulan")
    @classmethod
    def _bulan(cls, v):
        if isinstance(v, str) and not v.strip().isdigit():
            names = [b.lower() for b in BULAN]
            if v.strip().lower() not in names:
                raise ValueError(f"bulan tidak dikenal: {v!r}")
            return names.index(v.strip().lower()) + 1
        v = int(v)
        if not 1 <= v <= 12:
            raise ValueError("bulan harus 1–12")
        return v

    @field_validator("kepadatan_penduduk")
    @classmethod
    def _kepadatan(cls, v):
        if v is None:
            return v
        for k in KEPADATAN:
            if v.strip().lower() == k.lower():
                return k
        raise ValueError(f"kepadatan_penduduk harus salah satu dari {KEPADATAN}")


# ══════════════════════════════════════════════════════════════════════════════
# Utilitas
# ══════════════════════════════════════════════════════════════════════════════
def fmt_angka(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def pilih_estimasi(id_prov: int, kejadian: str, kelas: int):
    """Statistik dampak historis laporan serupa; dari yang paling spesifik ke paling umum."""
    est = STATE["lookup"]["estimasi"]
    urutan = [("2024+", "prov_jenis", f"{id_prov}|{kejadian}|{kelas}", 15, "provinsi"),
              ("2024+", "jenis", f"{kejadian}|{kelas}", 30, "nasional"),
              ("semua", "prov_jenis", f"{id_prov}|{kejadian}|{kelas}", 30, "provinsi"),
              ("semua", "jenis", f"{kejadian}|{kelas}", 5, "nasional")]
    for era, tabel, key, min_n, cakupan in urutan:
        s = est[era][tabel].get(key)
        if s and s["n"] >= min_n:
            return s, era, cakupan
    return None, None, None


def susun_estimasi(id_prov: int, prov_label: str, kejadian: str, kelas: int) -> dict:
    s, era, cakupan = pilih_estimasi(id_prov, kejadian, kelas)
    if s is None:
        return {"tersedia": False, "basis": "Belum ada laporan historis yang serupa."}

    kj = s["korban_jiwa"]
    if kj["p75"] < 1:
        korban = {"teks": "Umumnya 0 jiwa", "detail": f"{s['pct_ada_korban']:.0f}% laporan serupa ada korban jiwa"}
    elif kj["p25"] == kj["p75"]:
        korban = {"teks": f"~ {fmt_angka(kj['median'])} jiwa", "detail": f"{s['pct_ada_korban']:.0f}% laporan serupa ada korban jiwa"}
    else:
        korban = {"teks": f"~ {fmt_angka(kj['p25'])}–{fmt_angka(kj['p75'])} jiwa",
                  "detail": f"{s['pct_ada_korban']:.0f}% laporan serupa ada korban jiwa"}

    def blok(q, satuan):
        if q["p75"] < 1:
            return {"teks": f"Umumnya 0 {satuan}", "detail": "mayoritas laporan serupa 0"}
        return {"teks": f"~ {fmt_angka(q['median'])} {satuan}",
                "detail": f"rentang umum {fmt_angka(q['p25'])}–{fmt_angka(q['p75'])}"}

    wilayah = prov_label if cakupan == "provinsi" else "seluruh Indonesia"
    periode = "sejak 2024" if era == "2024+" else "2015–2026"
    return {
        "tersedia": True,
        "korban_jiwa": {**korban, **kj},
        "terdampak": {**blok(s["terdampak"], "jiwa"), **s["terdampak"]},
        "kerusakan": {**blok(s["kerusakan"], "unit"), **s["kerusakan"]},
        "n_laporan_serupa": s["n"],
        "basis": (f"Median dari {fmt_angka(s['n'])} laporan {jenis_display(kejadian).lower()} kategori "
                  f"\"{SEV_LABELS[kelas]}\" di {wilayah} ({periode})"),
    }


def profil_klaster(id_prov: int) -> dict | None:
    k = STATE["lookup"]["klaster"]
    if not k.get("tersedia"):
        return None
    p = k["provinsi"].get(str(id_prov))
    if p is None:
        return None
    nama = k["nama"][str(p["dominan"])]
    return {"klaster": p["dominan"], "nama": nama["nama"], "pendek": nama["pendek"],
            "n_wilayah": p["n_wilayah"], "distribusi": p["distribusi"]}


# ══════════════════════════════════════════════════════════════════════════════
# Endpoint
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/health")
def health():
    return {"status": "ok", "model_dimuat": "model" in STATE,
            "versi_model": STATE.get("meta", {}).get("versi")}


@app.get("/api/prediksi/meta")
def prediksi_meta():
    meta, lookup = STATE["meta"], STATE["lookup"]
    ev = meta["evaluasi"]
    klaster = lookup["klaster"]
    ringkasan_klaster = []
    if klaster.get("tersedia"):
        for kid, nama in klaster["nama"].items():
            ringkasan_klaster.append({"klaster": int(kid), "nama": nama["nama"], "pendek": nama["pendek"],
                                      "jumlah_wilayah": klaster["jumlah"].get(kid, 0)})
    return {
        "model": {
            "nama": meta["nama_model"], "algoritma": "RandomForestClassifier", "versi": meta["versi"],
            "dilatih_pada": meta["dilatih_pada"], "periode_data": meta["periode_data"], "n_laporan": meta["n_laporan"],
            "hyperparameter": meta["hyperparameter"],
            "metrik": {k: ev[k] for k in ("accuracy", "balanced_accuracy", "f1_macro", "f1_weighted", "mse",
                                          "baseline_kelas_mayoritas", "baseline_jenis_bencana_saja", "n_uji")},
            "catatan": meta["catatan"],
        },
        "opsi": {
            "jenis_bencana": [{"value": j["value"], "label": j["label"]} for j in lookup["jenis"]],
            "provinsi": [{"value": p["provinsi"], "label": p["label"], "id_prov": p["id_prov"]} for p in lookup["provinsi"]],
            "bulan": [{"value": i + 1, "label": b} for i, b in enumerate(BULAN)],
            "kepadatan_penduduk": KEPADATAN,
        },
        "kelas": SEV_LABELS,
        "faktor_risiko": meta["faktor_risiko"],
        "klaster": {"ringkasan": ringkasan_klaster, "total_wilayah": klaster.get("n_wilayah_unik", 0)},
        "kpi": {"akurasi": ev["accuracy"], "wilayah_terklasifikasi": klaster.get("n_wilayah_unik", 0),
                "tingkat_risiko": len(SEV_LABELS), "rekomendasi_mitigasi": jumlah_rekomendasi()},
    }


@app.post("/api/prediksi")
def prediksi(req: PrediksiRequest):
    kejadian = STATE["jenis_by_key"].get(req.jenis_bencana.strip().lower())
    if kejadian is None:
        raise HTTPException(422, f"jenis_bencana tidak dikenal: {req.jenis_bencana!r}. "
                                 f"Pilihan: {[j['label'] for j in STATE['lookup']['jenis']]}")
    prov = STATE["prov_by_key"].get(req.provinsi.strip().lower())
    if prov is None:
        raise HTTPException(422, f"provinsi tidak dikenal: {req.provinsi!r}")
    tahun = req.tahun or date.today().year

    X = make_inference_row(kejadian, prov, req.bulan, tahun, STATE["lookup"]["riwayat"])
    proba = STATE["model"].predict_proba(X)[0]
    kelas = int(proba.argmax())
    color, badge = BADGE[kelas]
    klaster = profil_klaster(prov["id_prov"])
    riwayat = STATE["lookup"]["riwayat"]["provtype"].get(f"{prov['id_prov']}|{kejadian}", {"n": 0})

    return {
        "input": {"jenis_bencana": kejadian, "jenis_label": jenis_display(kejadian),
                  "provinsi": prov["provinsi"], "provinsi_label": prov["label"],
                  "bulan": req.bulan, "bulan_label": BULAN[req.bulan - 1], "tahun": tahun,
                  "kepadatan_penduduk": req.kepadatan_penduduk},
        "prediksi": {
            "kode": kelas, "kelas": SEV_LABELS[kelas],
            "probabilitas": round(float(proba[kelas]), 4),
            "peluang": [{"kelas": SEV_LABELS[i], "kode": i, "p": round(float(p), 4)} for i, p in enumerate(proba)],
            "badge": {"warna": color, "teks": badge},
        },
        "estimasi": susun_estimasi(prov["id_prov"], prov["label"], kejadian, kelas),
        "klaster_provinsi": klaster,
        "mitigasi": rekomendasi(kelas, kejadian, req.kepadatan_penduduk, klaster["klaster"] if klaster else None),
        "riwayat": {"n_laporan_jenis_di_provinsi": riwayat["n"]},
        "catatan": "Kepadatan penduduk tidak dipakai model (tidak ada di data BNPB); hanya memengaruhi rekomendasi mitigasi.",
    }


# ── Sajikan frontend dari server yang sama: http://localhost:8000/ ─────────────
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
