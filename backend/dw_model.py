"""
DisasterWatch — modul data & fitur bersama untuk model klasifikasi tingkat dampak.

Dipakai oleh:
  - train_model.py  → membangun data latih, melatih, dan menyimpan model
  - app.py          → menyusun baris fitur dari input halaman "Prediksi Dampak"

Konvensi pembersihan dan label severity SAMA dengan notebook
`notebook/modelling_classification.ipynb` dan `preprocessing_disaster.ipynb`.
Bedanya: halaman Prediksi Dampak hanya punya input jenis bencana, provinsi, dan bulan
(tanpa kab/kota & koordinat), sehingga fitur lokasi & riwayat dihitung di tingkat PROVINSI.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ── Lokasi file ───────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = ROOT_DIR / "data" / "processed"
MODEL_DIR = BACKEND_DIR / "models"
REPORTS_CSV = DATA_DIR / "bnpb_bencana_2015-01-01_2026-10-28.csv"
CLUSTERS_CSV = DATA_DIR / "bnpb_disaster_clusters.csv"
FRONTEND_DIR = ROOT_DIR / "frontend"

# ── Kelas target (ordinal) ────────────────────────────────────────────────────
SEV_LABELS = ["Tanpa Dampak", "Ringan", "Sedang", "Berat"]

IMPACT_COLS = ["meninggal", "hilang", "terluka", "menderita", "mengungsi", "rumah_rusak", "terendam"]

# Label tampilan untuk jenis bencana BNPB (kunci = nilai kolom `kejadian` setelah upper/strip)
JENIS_LABELS = {
    "BANJIR": "Banjir",
    "CUACA EKSTREM": "Cuaca ekstrem",
    "TANAH LONGSOR": "Tanah longsor",
    "KEBAKARAN HUTAN DAN LAHAN": "Karhutla",
    "KEKERINGAN": "Kekeringan",
    "GEMPABUMI": "Gempa bumi",
    "GELOMBANG PASANG DAN ABRASI": "Gelombang pasang & abrasi",
    "ERUPSI GUNUNG API": "Erupsi gunung api",
    "TSUNAMI": "Tsunami",
    "GEMPA BUMI DAN TSUNAMI": "Gempa bumi & tsunami",
}
# Sinonim yang diterima API (huruf kecil) → kode BNPB
JENIS_ALIASES = {
    "karhutla": "KEBAKARAN HUTAN DAN LAHAN",
    "kebakaran hutan dan lahan": "KEBAKARAN HUTAN DAN LAHAN",
    "kebakaran hutan & lahan": "KEBAKARAN HUTAN DAN LAHAN",
    "gempa bumi": "GEMPABUMI",
    "gempa": "GEMPABUMI",
    "longsor": "TANAH LONGSOR",
    "puting beliung": "CUACA EKSTREM",
    "gelombang pasang": "GELOMBANG PASANG DAN ABRASI",
    "abrasi": "GELOMBANG PASANG DAN ABRASI",
    "erupsi": "ERUPSI GUNUNG API",
    "gempa bumi & tsunami": "GEMPA BUMI DAN TSUNAMI",
}

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]

# ── Definisi fitur model ──────────────────────────────────────────────────────
CAT_FEATURES = ["kejadian", "region", "provinsi"]
NUM_FEATURES = [
    "lon", "lat",                                       # titik pusat provinsi
    "month_sin", "month_cos", "musim_hujan",             # bulan & musim
    "year", "era_2024",                                  # era pelaporan BNPB
    "prov_log_n", "prov_sev_mean", "prov_berat_rate",    # riwayat provinsi
    "provtype_log_n", "provtype_sev_mean", "provtype_berat_rate",  # riwayat provinsi × jenis
]
FEATURES = CAT_FEATURES + NUM_FEATURES

# Pengelompokan fitur → faktor yang dikenali pengguna (untuk grafik "Faktor Risiko Dominan")
FEATURE_GROUPS = {
    "Jenis bencana": ["kejadian"],
    "Riwayat wilayah": ["prov_log_n", "prov_sev_mean", "prov_berat_rate",
                        "provtype_log_n", "provtype_sev_mean", "provtype_berat_rate"],
    "Provinsi / lokasi": ["provinsi", "region", "lon", "lat"],
    "Bulan / musim": ["month_sin", "month_cos", "musim_hujan"],
    "Era pelaporan": ["year", "era_2024"],
}

HISTORY_ALPHA = 5  # kekuatan penghalusan Bayesian untuk fitur riwayat


# ══════════════════════════════════════════════════════════════════════════════
# Utilitas label
# ══════════════════════════════════════════════════════════════════════════════
def region_from_prov(id_prov: int) -> str:
    p = int(id_prov)
    if 11 <= p <= 21:
        return "Sumatera"
    if 31 <= p <= 36:
        return "Jawa"
    if p == 51:
        return "Bali"
    if p in (52, 53):
        return "Nusa Tenggara"
    if 61 <= p <= 65:
        return "Kalimantan"
    if 71 <= p <= 76:
        return "Sulawesi"
    if p in (81, 82):
        return "Maluku"
    return "Papua"


def prov_display(name: str) -> str:
    """'JAWA TENGAH' → 'Jawa Tengah', dengan pengecualian singkatan."""
    special = {"DKI JAKARTA": "DKI Jakarta", "DAERAH ISTIMEWA YOGYAKARTA": "DI Yogyakarta"}
    return special.get(name, name.title())


def jenis_display(code: str) -> str:
    return JENIS_LABELS.get(code, code.capitalize())


# ══════════════════════════════════════════════════════════════════════════════
# Load & bersihkan data laporan BNPB
# ══════════════════════════════════════════════════════════════════════════════
def load_reports(path: Path = REPORTS_CSV) -> pd.DataFrame:
    usecols = ["id_prov", "id_kab", "provinsi", "kabkot", "kejadian", "lokasi", "tahun", "bulan", "tanggal",
               *IMPACT_COLS, "lng_prov", "lat_prov", "geometry_lon", "geometry_lat"]
    df = pd.read_csv(path, usecols=usecols, low_memory=False)

    for c in ["kejadian", "kabkot", "provinsi", "lokasi"]:
        df[c] = df[c].astype(str).str.strip().str.upper()
    # 78 variasi penulisan provinsi → 38 nama baku via id_prov
    prov_name = df.groupby("id_prov")["provinsi"].agg(lambda s: s.value_counts().index[0])
    df["provinsi"] = df["id_prov"].map(prov_name)

    df["date"] = pd.to_datetime(dict(year=df.tahun, month=df.bulan, day=df.tanggal), errors="coerce")
    df = df.dropna(subset=["date", "kejadian", "id_kab"])

    for c in IMPACT_COLS:  # NaN pada kolom dampak = tidak ada dampak tercatat
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).clip(lower=0)

    # laporan ganda: kunci bisnis + angka dampak identik
    df = df.drop_duplicates(subset=["date", "id_kab", "kejadian", "lokasi"] + IMPACT_COLS)

    df["korban_jiwa"] = df.meninggal + df.hilang
    df["terdampak"] = df.menderita + df.mengungsi
    df["kerusakan"] = df.rumah_rusak + df.terendam
    korban_total = df.korban_jiwa + df.terluka
    df["severity_code"] = np.select(
        [(df.korban_jiwa >= 5) | (df.terdampak >= 500) | (df.kerusakan >= 100),
         (df.korban_jiwa >= 1) | (df.terdampak >= 50) | (df.kerusakan >= 10),
         (korban_total > 0) | (df.terdampak > 0) | (df.kerusakan > 0)],
        [3, 2, 1], default=0)

    df["year"] = df.date.dt.year
    df["month"] = df.date.dt.month
    return df.sort_values("date").reset_index(drop=True)


def province_table(df: pd.DataFrame) -> pd.DataFrame:
    """Satu baris per provinsi: id, nama, region, titik pusat (median lng/lat_prov).

    Empat provinsi Papua hasil pemekaran 2022 tidak punya lng/lat_prov di data BNPB,
    sehingga titik pusatnya diganti median koordinat kejadian di provinsi tersebut.
    """
    num = lambda s: pd.to_numeric(s, errors="coerce")
    d = df.assign(_lon=num(df.lng_prov), _lat=num(df.lat_prov),
                  _glon=num(df.geometry_lon).where(num(df.geometry_lon).between(94, 142)),
                  _glat=num(df.geometry_lat).where(num(df.geometry_lat).between(-12, 7)))
    t = (d.groupby(["id_prov", "provinsi"])
           .agg(lon=("_lon", "median"), lat=("_lat", "median"),
                glon=("_glon", "median"), glat=("_glat", "median"),
                n_laporan=("kejadian", "size"))
           .reset_index())
    t["lon"] = t.lon.fillna(t.glon)
    t["lat"] = t.lat.fillna(t.glat)
    t = t.drop(columns=["glon", "glat"])
    t["region"] = t.id_prov.apply(region_from_prov)
    t["label"] = t.provinsi.apply(prov_display)
    return t.sort_values("label").reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# Fitur
# ══════════════════════════════════════════════════════════════════════════════
def _time_features(month, year) -> dict:
    month = np.asarray(month)
    year = np.asarray(year)
    return {
        "month_sin": np.sin(2 * np.pi * month / 12),
        "month_cos": np.cos(2 * np.pi * month / 12),
        "musim_hujan": np.isin(month, [11, 12, 1, 2, 3]).astype(int),
        "year": year,
        "era_2024": (year >= 2024).astype(int),
    }


def _priors(df: pd.DataFrame) -> tuple[float, float]:
    """Prior global untuk penghalusan, dari periode awal saja (2015–2017) agar tidak memakai info masa depan."""
    early = df[df.year <= 2017]
    return float(early.severity_code.mean()), float((early.severity_code == 3).mean())


def _past_history(df: pd.DataFrame, keys: list[str], prefix: str, priors) -> pd.DataFrame:
    """Statistik dari laporan dengan tanggal LEBIH AWAL pada grup `keys` (tanpa kebocoran waktu)."""
    prior_sev, prior_berat = priors
    d = df[keys + ["date", "severity_code"]].copy()
    d["_berat"] = (d.severity_code == 3).astype(int)
    g = (d.groupby(keys + ["date"]).agg(_n=("severity_code", "size"), _s=("severity_code", "sum"), _b=("_berat", "sum"))
           .reset_index().sort_values(keys + ["date"]))
    for c in ["_n", "_s", "_b"]:
        g[c + "_past"] = g.groupby(keys)[c].cumsum() - g[c]
    out = df[keys + ["date"]].merge(g[keys + ["date", "_n_past", "_s_past", "_b_past"]], on=keys + ["date"], how="left")
    a = HISTORY_ALPHA
    return pd.DataFrame({
        f"{prefix}_log_n": np.log1p(out._n_past.values),
        f"{prefix}_sev_mean": ((out._s_past + a * prior_sev) / (out._n_past + a)).values,
        f"{prefix}_berat_rate": ((out._b_past + a * prior_berat) / (out._n_past + a)).values,
    }, index=df.index)


def build_training_frame(df: pd.DataFrame, prov: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Matriks fitur untuk pelatihan: riwayat dihitung hanya dari laporan sebelumnya."""
    priors = _priors(df)
    p = prov.set_index("id_prov")
    X = pd.DataFrame({
        "kejadian": df.kejadian.values,
        "region": df.id_prov.map(p.region).values,
        "provinsi": df.provinsi.values,
        "lon": df.id_prov.map(p.lon).values,
        "lat": df.id_prov.map(p.lat).values,
        **_time_features(df.month.values, df.year.values),
    }, index=df.index)
    X = X.join(_past_history(df, ["id_prov"], "prov", priors))
    X = X.join(_past_history(df, ["id_prov", "kejadian"], "provtype", priors))
    return X[FEATURES], df.severity_code.values


def history_snapshot(df: pd.DataFrame) -> dict:
    """Riwayat SELURUH data sampai laporan terakhir — dipakai saat prediksi kejadian yang akan datang."""
    prior_sev, prior_berat = _priors(df)
    a = HISTORY_ALPHA

    def stats(g):
        n, s, b = len(g), g.severity_code.sum(), (g.severity_code == 3).sum()
        return {"log_n": float(np.log1p(n)), "sev_mean": float((s + a * prior_sev) / (n + a)),
                "berat_rate": float((b + a * prior_berat) / (n + a)), "n": int(n)}

    prov = {str(int(k)): stats(g) for k, g in df.groupby("id_prov")}
    provtype = {f"{int(k[0])}|{k[1]}": stats(g) for k, g in df.groupby(["id_prov", "kejadian"])}
    empty = {"log_n": 0.0, "sev_mean": prior_sev, "berat_rate": prior_berat, "n": 0}
    return {"prov": prov, "provtype": provtype, "empty": empty,
            "last_date": df.date.max().strftime("%Y-%m-%d")}


def make_inference_row(kejadian: str, prov_row: dict, month: int, year: int, snapshot: dict) -> pd.DataFrame:
    """Satu baris fitur untuk input halaman Prediksi Dampak."""
    pid = str(int(prov_row["id_prov"]))
    hp = snapshot["prov"].get(pid, snapshot["empty"])
    ht = snapshot["provtype"].get(f"{pid}|{kejadian}", snapshot["empty"])
    row = {
        "kejadian": kejadian, "region": prov_row["region"], "provinsi": prov_row["provinsi"],
        "lon": prov_row["lon"], "lat": prov_row["lat"],
        **{k: v.item() for k, v in ((k, np.asarray(v)) for k, v in _time_features([month], [year]).items())},
        "prov_log_n": hp["log_n"], "prov_sev_mean": hp["sev_mean"], "prov_berat_rate": hp["berat_rate"],
        "provtype_log_n": ht["log_n"], "provtype_sev_mean": ht["sev_mean"], "provtype_berat_rate": ht["berat_rate"],
    }
    return pd.DataFrame([row])[FEATURES]


def mse_pdf(y_true, C, k: int = 4) -> float:
    """MSE sesuai materi Multi Perceptron: SE_d = Σ_k (Target_k − C_k)², MSE = SSE / f."""
    T = np.eye(k)[np.asarray(y_true)]
    return float(((T - np.asarray(C)) ** 2).sum(axis=1).mean())
