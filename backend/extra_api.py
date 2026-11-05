"""Endpoint tambahan DisasterWatch: semua angka dihitung dari data BNPB asli (bukan dummy)."""
import json
from functools import lru_cache

import pandas as pd
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pandas.tseries.offsets import MonthEnd

try:
    from backend.dw_model import load_reports, prov_display, jenis_display, CLUSTERS_CSV, DATA_DIR, MODEL_DIR, REPORTS_CSV
except ImportError:
    from dw_model import load_reports, prov_display, jenis_display, CLUSTERS_CSV, DATA_DIR, MODEL_DIR, REPORTS_CSV

router = APIRouter()
BLN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


@lru_cache(maxsize=1)
def _df():
    d = load_reports()
    d["id_kab"] = d.id_kab.astype(int)
    return d


@lru_cache(maxsize=1)
def _lookup():
    with open(MODEL_DIR / "lookup.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _kab_names():
    return _df().groupby("id_kab").kabkot.agg(lambda x: x.value_counts().index[0]).to_dict()


def _top_kab(d):
    names = _kab_names()
    return [{"nama": str(names.get(k, k)).title(), "n": int(v)} for k, v in d.id_kab.value_counts().head(5).items()]


def _cutoff(df, year):
    """Bulan terakhir yang LENGKAP pada tahun itu (bulan berjalan yang belum selesai tidak dihitung)."""
    last = df.date.max()
    if year < last.year:
        return 12
    return last.month if last == last + MonthEnd(0) else last.month - 1


def _pct(cur, prev):
    return None if prev == 0 else round(float((cur - prev) / prev * 100), 1)


@router.get("/api/overview")
def overview(tahun: int = 0, jenis: str = "semua", provinsi: str = "semua", dari: int = 0):
    """tahun=0 → tahun terbaru; tahun<0 → semua tahun."""
    df = _df()
    if tahun == 0:
        tahun = int(df.year.max())
    base = df
    if jenis != "semua":
        base = base[base.kejadian == jenis.upper()]
    if provinsi != "semua":
        base = base[base.provinsi == provinsi.upper()]
    if tahun < 0:
        d = base[base.year >= dari] if dari else base
    else:
        d = base[base.year == tahun]

    trend, pemb = {"total": None, "meninggal": None, "rumah": None}, ""
    if tahun > 0:
        cut = _cutoff(df, tahun)
        cur = base[(base.year == tahun) & (base.month <= cut)]
        prev = base[(base.year == tahun - 1) & (base.month <= cut)]
        if cut:
            trend = {"total": _pct(len(cur), len(prev)),
                     "meninggal": _pct(cur.meninggal.sum(), prev.meninggal.sum()),
                     "rumah": _pct(cur.rumah_rusak.sum(), prev.rumah_rusak.sum())}
            pemb = "Jan–" + BLN[cut - 1]

    monthly = d.groupby("month").size().reindex(range(1, 13), fill_value=0)
    vc = d.kejadian.value_counts()
    counts = d.provinsi.value_counts()
    q1, q2 = (counts.quantile(1 / 3), counts.quantile(2 / 3)) if len(counts) else (0, 0)
    lk = {p["provinsi"]: p for p in _lookup().get("provinsi", [])}
    peta = []
    for prov, n in counts.items():
        p = lk.get(prov)
        if not p or p.get("lat") is None or p.get("lon") is None:
            continue
        peta.append({"nama": prov_display(prov), "lat": float(p["lat"]), "lng": float(p["lon"]), "n": int(n),
                     "risiko": "tinggi" if n >= q2 else "sedang" if n >= q1 else "rendah"})
    return {
        "tahun": tahun,
        "pembanding": pemb,
        "kpi": {"total": int(len(d)), "meninggal": int(d.meninggal.sum()), "rumah": int(d.rumah_rusak.sum()),
                "prov": int(d.provinsi.nunique())},
        "trend": trend,
        "monthly": {"labels": BLN, "values": [int(x) for x in monthly.values]},
        "komposisi": {"labels": [jenis_display(k) for k in vc.index], "values": [int(v) for v in vc.values]},
        "topProvinsi": [{"provinsi": prov_display(k), "jumlah_kejadian": int(v)} for k, v in counts.head(5).items()],
        "petaTitik": peta,
        "topKab": _top_kab(d),
    }


@router.get("/api/extra")
def extra():
    df, lk = _df(), _lookup()
    vc = df.provinsi.value_counts()

    top = vc.head(5).index.tolist()
    sub = df[df.provinsi.isin(top)]
    ct = pd.crosstab(sub.provinsi, sub.kejadian).reindex(top).fillna(0)
    col = lambda k: [int(x) for x in (ct[k] if k in ct else [0] * len(top))]
    dominan = {"labels": [prov_display(p) for p in top], "banjir": col("BANJIR"),
               "cuaca": col("CUACA EKSTREM"), "longsor": col("TANAH LONGSOR")}

    kl = lk.get("klaster", {})
    klaster = sorted(({"id": int(i), "nama": v["nama"], "pendek": v.get("pendek", v["nama"]),
                       "wilayah": kl.get("jumlah", {}).get(i, 0)} for i, v in kl.get("nama", {}).items()),
                     key=lambda k: k["id"])
    klaster_impact, klaster_prov = None, []
    if CLUSTERS_CSV.exists():
        c = (pd.read_csv(CLUSTERS_CSV, usecols=["id_kab", "cluster", "total_laporan"])
               .sort_values("total_laporan", ascending=False).drop_duplicates("id_kab"))
        c["id_kab"] = c.id_kab.astype(int)
        g = (df.merge(c[["id_kab", "cluster"]], on="id_kab")
               .groupby("cluster").agg(korban=("korban_jiwa", "mean"), terdampak=("terdampak", "mean")).sort_index())
        klaster_impact = {"labels": [f"Klaster {int(i)}" for i in g.index],
                          "korban": [round(float(x), 2) for x in g.korban],
                          "terdampak": [round(float(x), 1) for x in g.terdampak]}
        ids = {p["provinsi"]: p["id_prov"] for p in lk.get("provinsi", [])}
        for prov in vc.head(6).index:
            dom = kl.get("provinsi", {}).get(str(ids.get(prov)))
            if dom:
                k = dom["dominan"]
                klaster_prov.append({"nama": prov_display(prov), "klaster": int(k),
                                     "label": kl.get("nama", {}).get(str(k), {}).get("pendek", f"Klaster {k}")})

    # musiman: rata-rata per bulan, hanya tahun yang sudah lengkap
    full = df[df.year < df.year.max()]
    seas = full.groupby(["year", "month"]).size().groupby("month").mean().reindex(range(1, 13), fill_value=0)

    # aktual per bulan (bulan berjalan yang belum lengkap dibuang)
    s = df.groupby(["year", "month"]).size()
    last_y = int(df.year.max())
    cut = _cutoff(df, last_y)
    s = s[[(y, m) for (y, m) in s.index if not (y == last_y and m > cut)]]
    aktual = {"labels": [f"{y}-{m:02d}" for y, m in s.index], "values": [int(v) for v in s.values]}

    # --- BACA FORECAST (CSV ATAU JSON) ---
    forecast = None
    fp_csv = DATA_DIR / "forecast.csv" 
    fp_json = ROOT_DIR / "trend-modeling" / "forecast_output.json"
    
    if fp_csv.exists():
        f = pd.read_csv(fp_csv)
        forecast = {"labels": f.bulan.astype(str).tolist(), "prediksi": f.prediksi.round(0).tolist(),
                    "lower": f.lower.round(0).tolist(), "upper": f.upper.round(0).tolist()}
    elif fp_json.exists():
        with open(fp_json, 'r') as jf:
            data_json = json.load(jf)
            
            # Ambil data forecast untuk NASIONAL
            try:
                # Cek apakah strukturnya seperti ini: {"series": {"NASIONAL": {"forecast": [...]}}}
                if "series" in data_json and "NASIONAL" in data_json["series"]:
                    f_list = data_json["series"]["NASIONAL"]["forecast"]
                    
                    # Karena di JSON semua angka desimal, kita bulatkan
                    forecast = {
                        "labels": [str(item["month"]) for item in f_list],
                        "prediksi": [round(float(item.get("pred", 0))) for item in f_list],
                        "lower": [round(float(item.get("lower", 0))) for item in f_list],
                        "upper": [round(float(item.get("upper", 0))) for item in f_list]
                    }
                else:
                    print("WARNING: Struktur JSON forecast tidak dikenali.")
            except Exception as e:
                print(f"Error parsing JSON forecast: {e}")

    top_kab = _top_kab(df)

    return {"dominan": dominan, "klaster": klaster, "klasterTotal": kl.get("n_wilayah_unik"), "klasterImpact": klaster_impact, "klasterProv": klaster_prov,
            "seasonal": {"labels": BLN, "values": [round(float(x), 1) for x in seas.values],
                         "periode": f"{int(full.year.min())}–{int(full.year.max())}"},
            "aktual": aktual, "forecast": forecast, "topKab": top_kab}


# ---------- Laporan: daftar & unduhan file asli ----------
ROOT_DIR = DATA_DIR.parent.parent


@lru_cache(maxsize=1)
def _n_dataset():
    return int(len(pd.read_csv(REPORTS_CSV, usecols=["id_prov"])))


def _files():
    f = {"dataset": (REPORTS_CSV, "Dataset BNPB (CSV)"),
         "klaster": (CLUSTERS_CSV, "Hasil Klasterisasi Risiko Wilayah (CSV)"),
         "meta": (MODEL_DIR / "model_meta.json", "Metrik Evaluasi Model (JSON)")}
    rep = ROOT_DIR / "reports"
    if rep.exists():
        for p in sorted(rep.iterdir()):
            if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".xlsx", ".pptx", ".csv"}:
                f["rep-" + p.name] = (p, p.stem.replace("_", " ").replace("-", " ").title())
    return {k: v for k, v in f.items() if v[0].exists()}


def _size(b):
    return f"{b / 1e6:.1f} MB" if b >= 1e6 else f"{max(b / 1e3, 1):.0f} KB"


@router.get("/api/laporan")
def laporan():
    out = []
    for k, (p, judul) in _files().items():
        st = p.stat()
        desk = f"{_size(st.st_size)} · diperbarui {datetime.fromtimestamp(st.st_mtime):%d-%m-%Y}"
        if k == "dataset":
            desk = f"{_n_dataset():,}".replace(",", ".") + " laporan · " + desk
        out.append({"kode": k, "judul": judul, "deskripsi": desk, "tipe": p.suffix.lstrip(".").upper()})
    return out


@router.get("/api/unduh/{kode}")
def unduh(kode: str):
    f = _files().get(kode)
    if not f:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return FileResponse(f[0], filename=f[0].name)