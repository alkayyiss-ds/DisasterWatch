from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import os
import joblib
import json

# dw_model = modul fitur yang sama dengan yang dipakai train_model.py
try:
    from backend.dw_model import (JENIS_LABELS, JENIS_ALIASES, BULAN, SEV_LABELS,
                                  REPORTS_CSV, make_inference_row)
except ImportError:
    from dw_model import (JENIS_LABELS, JENIS_ALIASES, BULAN, SEV_LABELS,
                          REPORTS_CSV, make_inference_row)

app = FastAPI(title="DisasterWatch API")

try:
    from backend.extra_api import router as extra_router
except ImportError:
    from extra_api import router as extra_router
app.include_router(extra_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. KONFIGURASI PATH & LOAD MODEL
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
MODEL_DIR = os.path.join(BASE_DIR, "backend", "models")

MODEL_PATH = os.path.join(MODEL_DIR, "rf_severity.joblib")
LOOKUP_PATH = os.path.join(MODEL_DIR, "lookup.json")
META_PATH = os.path.join(MODEL_DIR, "model_meta.json")

model = None
lookup_data = {}
model_meta = {}

if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        print("INFO: Model Random Forest berhasil dimuat.")
    except Exception as e:
        print(f"ERROR: Gagal memuat model. {e}")
else:
    print("WARNING: rf_severity.joblib tidak ditemukan.")

if os.path.exists(LOOKUP_PATH):
    with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
        lookup_data = json.load(f)
    print("INFO: Lookup data berhasil dimuat.")

if os.path.exists(META_PATH):
    with open(META_PATH, "r", encoding="utf-8") as f:
        model_meta = json.load(f)
    print("INFO: Metadata model berhasil dimuat.")

# Indeks provinsi dari lookup.json (nama baku & label tampilan, huruf besar)
PROV_INDEX = {}
for _p in lookup_data.get("provinsi", []):
    PROV_INDEX[str(_p["provinsi"]).upper()] = _p
    PROV_INDEX[str(_p["label"]).upper()] = _p

# Indeks nama jenis: kode BNPB, label tampilan, dan alias
JENIS_INDEX = {k: k for k in JENIS_LABELS}
for _k, _v in JENIS_LABELS.items():
    JENIS_INDEX[_v.upper()] = _k
for _a, _k in JENIS_ALIASES.items():
    JENIS_INDEX[_a.upper()] = _k

MIN_N = 5  # minimal jumlah laporan historis agar median dipercaya


def cari_estimasi(pid: str, kejadian: str, tingkat: int):
    """Median dampak historis: provinsi×jenis×tingkat dulu, lalu jenis×tingkat; era 2024+ dulu, lalu semua."""
    est = lookup_data.get("estimasi", {})
    urutan = [
        ("2024+", "prov_jenis", f"{pid}|{kejadian}|{tingkat}", "provinsi & jenis (2024+)"),
        ("semua", "prov_jenis", f"{pid}|{kejadian}|{tingkat}", "provinsi & jenis (2015-sekarang)"),
        ("2024+", "jenis", f"{kejadian}|{tingkat}", "jenis bencana nasional (2024+)"),
        ("semua", "jenis", f"{kejadian}|{tingkat}", "jenis bencana nasional (2015-sekarang)"),
    ]
    for era, scope, key, basis in urutan:
        s = est.get(era, {}).get(scope, {}).get(key)
        if s and s.get("n", 0) >= MIN_N:
            return s, basis
    return None, None


# ==========================================
# 2. SKEMA INPUT UNTUK PREDIKSI
# ==========================================
class PrediksiInput(BaseModel):
    jenis_bencana: str
    provinsi: str
    bulan: str
    kepadatan: str = ""   # tidak dipakai model (hanya untuk rekomendasi mitigasi)

# ==========================================
# 3. ENDPOINT: DATA DASHBOARD (CSV ASLI)
# ==========================================
@app.get("/api/dashboard-data")
def get_dashboard_data():
    try:
        df_monthly = pd.read_csv(os.path.join(DATA_DIR, "bnpb_aggregate_monthly.csv"))
        df_prov = pd.read_csv(os.path.join(DATA_DIR, "bnpb_aggregate_province.csv"))
        df_type = pd.read_csv(os.path.join(DATA_DIR, "bnpb_aggregate_type.csv"))

        df_prov_sorted = df_prov.sort_values(by="jumlah_kejadian", ascending=False).head(5)
        top_prov = df_prov_sorted[["provinsi", "jumlah_kejadian"]].to_dict(orient="records")

        df_type_sorted = df_type.sort_values(by="jumlah_laporan", ascending=False)
        komposisi = {
            "labels": df_type_sorted["kejadian"].tolist(),
            "values": df_type_sorted["jumlah_laporan"].tolist()
        }

        tahun = int(df_monthly["year"].max())
        df_thn = df_monthly[df_monthly["year"] == tahun]
        monthly_labels = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
        monthly_values = []
        for i in range(1, 13):
            val = df_thn[df_thn["month"] == i]["jumlah_laporan"].values
            monthly_values.append(int(val[0]) if len(val) > 0 else 0)

        # Jumlah wilayah (kab/kota) dari data klaster; fallback hitung dari CSV laporan
        wilayah = lookup_data.get("klaster", {}).get("n_wilayah_unik")
        if not wilayah:
            wilayah = int(pd.read_csv(REPORTS_CSV, usecols=["id_kab"])["id_kab"].nunique())

        akurasi = model_meta.get("evaluasi", {}).get("accuracy", 0)

        return {
            "kpi": {
                "total": int(df_thn["jumlah_laporan"].sum()),
                "meninggal": int(df_thn["meninggal"].sum()),
                "rumah": int(df_thn["rumah_rusak"].sum()),
                "prov": len(df_prov[df_prov["jumlah_laporan"] > 0]),
                "akurasi": round(akurasi * 100, 1),
                "wilayah": int(wilayah)
            },
            "topProvinsi": top_prov,
            "komposisi": komposisi,
            "monthly": {"labels": monthly_labels, "values": monthly_values},
            "feature": {
                "labels": [f["faktor"] for f in model_meta.get("faktor_risiko", [])],
                "values": [f["bobot"] for f in model_meta.get("faktor_risiko", [])]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 4. ENDPOINT: PREDIKSI DAMPAK (MODEL ASLI)
# ==========================================
@app.post("/api/prediksi")
def prediksi_dampak(data: PrediksiInput):
    if model is None:
        raise HTTPException(status_code=500, detail="Model ML tidak termuat di server.")
    if not lookup_data:
        raise HTTPException(status_code=500, detail="lookup.json tidak termuat di server.")

    try:
        # 1. Normalisasi input ke kode BNPB
        kejadian = JENIS_INDEX.get(data.jenis_bencana.strip().upper())
        if kejadian is None:
            raise HTTPException(status_code=400, detail=f"Jenis bencana tidak dikenal: {data.jenis_bencana}")

        prov_row = PROV_INDEX.get(data.provinsi.strip().upper())
        if prov_row is None:
            raise HTTPException(status_code=400, detail=f"Provinsi tidak dikenal: {data.provinsi}")

        # 2. Bulan (nama Indonesia atau angka 1-12)
        b = data.bulan.strip()
        if b.isdigit() and 1 <= int(b) <= 12:
            bulan_num = int(b)
        elif b.capitalize() in BULAN:
            bulan_num = BULAN.index(b.capitalize()) + 1
        else:
            raise HTTPException(status_code=400, detail=f"Bulan tidak dikenal: {data.bulan}")

        # 3. Susun 16 fitur persis seperti saat training (riwayat dari snapshot lookup.json)
        tahun = datetime.now().year
        X = make_inference_row(kejadian, prov_row, bulan_num, tahun, lookup_data["riwayat"])

        # 4. Prediksi & probabilitas
        tingkat = int(model.predict(X)[0])
        probabilitas = [0, 0, 0, 0]
        proba = model.predict_proba(X)[0]
        for cls, p in zip(model.classes_, proba):
            probabilitas[int(cls)] = round(float(p) * 100)

        # 5. Estimasi dampak = median laporan historis BNPB pada tingkat yang sama
        stat, basis = cari_estimasi(str(int(prov_row["id_prov"])), kejadian, tingkat)
        if stat:
            korban = int(round(stat["korban_jiwa"]["median"]))
            terdampak = int(round(stat["terdampak"]["median"]))
            rusak = int(round(stat["kerusakan"]["median"]))
            rentang = {
                "korban": [int(round(stat["korban_jiwa"]["p25"])), int(round(stat["korban_jiwa"]["p75"]))],
                "terdampak": [int(round(stat["terdampak"]["p25"])), int(round(stat["terdampak"]["p75"]))],
                "rusak": [int(round(stat["kerusakan"]["p25"])), int(round(stat["kerusakan"]["p75"]))],
            }
            n_historis = int(stat["n"])
        else:
            korban = terdampak = rusak = 0
            rentang = None
            n_historis = 0
            basis = "tidak ada data historis yang cukup"

        return {
            "tingkat": tingkat,
            "label": SEV_LABELS[tingkat],
            "probabilitas": probabilitas,
            "korban": korban,
            "terdampak": terdampak,
            "rusak": rusak,
            "rentang": rentang,
            "basis_estimasi": basis,
            "n_historis": n_historis
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saat prediksi: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)