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

    forecast = None
    fp = DATA_DIR / "forecast.csv"   # opsional: kolom bulan (YYYY-MM), prediksi, lower, upper
    if fp.exists():
        f = pd.read_csv(fp)
        forecast = {"labels": f.bulan.astype(str).tolist(), "prediksi": f.prediksi.round(0).tolist(),
                    "lower": f.lower.round(0).tolist(), "upper": f.upper.round(0).tolist()}

    top_kab = _top_kab(df)

    return {"dominan": dominan, "klaster": klaster, "klasterTotal": kl.get("n_wilayah_unik"), "klasterImpact": klaster_impact, "klasterProv": klaster_prov,
            "seasonal": {"labels": BLN, "values": [round(float(x), 1) for x in seas.values],
                         "periode": f"{int(full.year.min())}–{int(full.year.max())}"},
            "aktual": aktual, "forecast": forecast, "topKab": top_kab}


# ---------- Laporan: daftar & unduhan file asli ----------
ROOT_DIR = DATA_DIR.parent.parent
TREN_DIR = ROOT_DIR / "trend-modeling"


@lru_cache(maxsize=1)
def _n_dataset():
    return int(len(pd.read_csv(REPORTS_CSV, usecols=["id_prov"])))


def _files():
    f = {"dataset": (REPORTS_CSV, "Dataset BNPB (CSV)"),
         "klaster": (CLUSTERS_CSV, "Hasil Klasterisasi Risiko Wilayah (CSV)"),
         "meta": (MODEL_DIR / "model_meta.json", "Metrik Evaluasi Model (JSON)"),
         "forecast": (TREN_DIR / "forecast_12_bulan.csv", "Prediksi Tren 12 Bulan (CSV)"),
         "metrik-tren": (TREN_DIR / "metrics_all_models.csv", "Metrik Model Tren (CSV)")}
    rep = ROOT_DIR / "reports"
    if rep.exists():
        for p in sorted(rep.iterdir()):
            if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".md"}:
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


# ---------- Tren & prediksi: dibaca langsung dari folder trend-modeling/ ----------
@lru_cache(maxsize=1)
def _tren():
    if not TREN_DIR.exists():
        raise HTTPException(status_code=404, detail="Folder trend-modeling tidak ditemukan")
    files = {"sum": "metrics_summary.csv", "all": "metrics_all_models.csv", "fc": "forecast_all_models.csv",
             "best": "forecast_12_bulan.csv", "cnt": "monthly_counts.csv", "seas": "seasonality_monthly.csv",
             "test": "test_predictions_all_models.csv"}
    return {k: pd.read_csv(TREN_DIR / f) for k, f in files.items()}


def _f(x):
    return None if pd.isna(x) else round(float(x), 2)


@router.get("/api/tren")
def tren(seri: str = "NASIONAL", model: str = "auto", horizon: int = 12):
    t = _tren()
    seri = seri.upper()
    sm = t["sum"]
    if seri not in set(sm.seri):
        raise HTTPException(status_code=404, detail=f"Seri tidak dikenal: {seri}")
    srow = sm[sm.seri == seri].iloc[0]
    mods = t["all"][t["all"].seri == seri]
    if mods.empty:
        raise HTTPException(status_code=404, detail=f"Tidak ada hasil model untuk seri: {seri}")
    flag = mods[mods.is_best.astype(str).str.lower().isin(["true", "1", "1.0"])]
    best = (flag if not flag.empty else mods.sort_values("mae")).iloc[0]   # tanpa penanda is_best -> MAE terkecil
    if model == "auto":
        row = best
    else:
        pick = mods[mods.model == model]
        if pick.empty:
            raise HTTPException(status_code=404, detail=f"Model tidak ada untuk {seri}: {model}")
        row = pick.iloc[0]
    key = row.model

    fc = t["fc"][(t["fc"].seri == seri) & (t["fc"].model == key)]
    if fc.empty and key == best.model:
        fc = t["best"][t["best"].seri == seri]
    fc = fc.head(max(1, horizon))
    te = t["test"][(t["test"].seri == seri) & (t["test"].model == key)]
    cnt = t["cnt"]
    ak = cnt[["bulan", seri]].dropna() if seri in cnt.columns else cnt.iloc[0:0].assign(**{seri: []})[["bulan", seri]]
    se = t["seas"][t["seas"].seri == seri].sort_values("month_num")

    nama = lambda k: "Nasional (semua jenis)" if k == "NASIONAL" else jenis_display(k)
    ada = set(t["all"].seri)
    seri_opsi = [{"kode": k, "nama": nama(k)} for k in sm.seri if k in ada]
    seri_opsi.sort(key=lambda x: (x["kode"] != "NASIONAL", x["nama"]))
    return {
        "seri": seri, "nama": nama(seri), "rata": _f(srow.rata2_per_bulan), "kecil": bool(srow.rata2_per_bulan < 5),
        "opsi": {"seri": seri_opsi,
                 "model": [{"kode": "auto", "label": "Otomatis (terbaik)"}] +
                          [{"kode": m.model, "label": m.label} for m in mods.itertuples()]},
        "model": {"kode": key, "label": row.label, "terbaik": bool(key == best.model), "terbaik_label": best.label,
                  "mae": _f(row.mae), "rmse": _f(row.rmse), "mape": _f(row.mape)},
        "tabel": [{"label": m.label, "mae": _f(m.mae), "rmse": _f(m.rmse), "mape": _f(m.mape),
                   "terbaik": bool(m.model == best.model)} for m in mods.sort_values("mae").itertuples()],
        "aktual": {"labels": ak.bulan.astype(str).tolist(), "values": [int(v) for v in ak[seri]]},
        "uji": {"labels": te.month.astype(str).tolist(), "pred": [_f(v) for v in te.pred]},
        "prediksi": {"labels": fc.month.astype(str).tolist(), "pred": [_f(v) for v in fc.pred],
                     "lower": [_f(v) for v in fc.lower], "upper": [_f(v) for v in fc.upper]},
        "musiman": {"labels": se.month_label.tolist(), "values": [_f(v) for v in se.avg],
                    "periode": str(se.period.iloc[0]) if len(se) else ""},
    }