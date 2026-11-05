"""Ekspor data statis untuk frontend TANPA backend.

Jalankan dari root repo (venv aktif):
    python backend/export_static.py
    python backend/export_static.py --dengan-dataset   # sertakan CSV dataset besar (>25 MB) untuk tombol Unduh

Hasil: frontend/data/*.json (+ frontend/data/unduh/*) — semua dihitung dari data BNPB, model, dan hasil trend-modeling.
"""
import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import joblib
import pandas as pd

import extra_api as X
from dw_model import FRONTEND_DIR, JENIS_LABELS, MODEL_DIR, jenis_display, make_inference_row

OUT = FRONTEND_DIR / "data"
LIMIT_BYTES = 25e6


def _n(x):
    try:
        return None if x is None or pd.isna(x) else float(x)
    except (TypeError, ValueError):
        return None


def dump(name, obj):
    p = OUT / f"{name}.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
                  default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(f"  {name}.json".ljust(22) + f"{p.stat().st_size / 1e3:>9,.0f} KB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dengan-dataset", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "unduh").mkdir(exist_ok=True)

    print("Membaca data BNPB ...")
    df, lk = X._df(), X._lookup()
    mm = json.load(open(MODEL_DIR / "model_meta.json", encoding="utf-8"))
    last = df.date.max()
    cut = X._cutoff(df, int(last.year))

    jenis = [{"kode": k, "label": jenis_display(k)} for k in sorted(df.kejadian.unique())]
    jidx = {j["kode"]: i for i, j in enumerate(jenis)}
    provs = [{"kode": p["provinsi"], "label": p["label"], "id_prov": int(p["id_prov"]),
              "lat": _n(p.get("lat")), "lng": _n(p.get("lon"))} for p in lk["provinsi"]]
    pidx = {p["kode"]: i for i, p in enumerate(provs)}

    print("Menulis file ke", OUT)
    # 1) tabel agregat: dasar semua filter Overview / Peta di browser
    g = (df.groupby(["year", "month", "kejadian", "provinsi"])
           .agg(n=("id_prov", "size"), m=("meninggal", "sum"), r=("rumah_rusak", "sum")).reset_index())
    g = g[g.provinsi.isin(pidx)]
    dump("agg", {"y": g.year.astype(int).tolist(), "mo": g.month.astype(int).tolist(),
                 "j": g.kejadian.map(jidx).astype(int).tolist(), "p": g.provinsi.map(pidx).astype(int).tolist(),
                 "n": g.n.astype(int).tolist(), "m": g.m.round().astype(int).tolist(), "r": g.r.round().astype(int).tolist()})

    # 2) kabupaten/kota
    names = X._kab_names()
    kg = df.groupby(["year", "kejadian", "id_kab"]).size().reset_index(name="n")
    kids = sorted(int(k) for k in kg.id_kab.unique())
    kidx = {k: i for i, k in enumerate(kids)}
    dump("kab", {"kab": [{"nama": str(names.get(k, k)).title(), "prov": int(k // 100)} for k in kids],
                 "y": kg.year.astype(int).tolist(), "j": kg.kejadian.map(jidx).astype(int).tolist(),
                 "k": kg.id_kab.astype(int).map(kidx).tolist(), "n": kg.n.astype(int).tolist()})

    # 3) klaster & dominan
    ex = X.extra()
    dump("extra", {k: ex[k] for k in ("dominan", "klaster", "klasterTotal", "klasterImpact", "klasterProv")})

    # 4) tren: semua seri x semua model (hasil trend-modeling/)
    first = X.tren("NASIONAL", "auto", 12)
    T = {"opsi": first["opsi"]["seri"], "seri": {}}
    for s in T["opsi"]:
        try:
            base = X.tren(s["kode"], "auto", 12)
        except Exception as e:
            print(f"  ! seri {s['kode']} dilewati: {getattr(e, 'detail', e)}")
            continue
        models = []
        for m in base["opsi"]["model"]:
            if m["kode"] == "auto":
                continue
            r = X.tren(s["kode"], m["kode"], 12)
            models.append({**r["model"], "uji": r["uji"], "fc": r["prediksi"]})
        T["seri"][s["kode"]] = {"nama": base["nama"], "rata": base["rata"], "kecil": base["kecil"],
                                "aktual": base["aktual"], "musiman": base["musiman"], "models": models}
    T["opsi"] = [o for o in T["opsi"] if o["kode"] in T["seri"]]
    dump("tren", T)

    # 5) prediksi dampak: model Random Forest dijalankan untuk semua kombinasi pilihan dropdown
    print("Menjalankan model untuk semua kombinasi (jenis x provinsi x bulan) ...")
    model = joblib.load(MODEL_DIR / "rf_severity.joblib")
    year = datetime.now().year
    keys, rows = [], []
    for jk in [k for k in JENIS_LABELS if k != "GEMPA BUMI DAN TSUNAMI"]:
        for p in lk["provinsi"]:
            for m in range(1, 13):
                keys.append((jk, p, m))
                rows.append(make_inference_row(jk, p, m, year, lk["riwayat"]))
    proba = model.predict_proba(pd.concat(rows, ignore_index=True))
    est = lk.get("estimasi", {})

    def cari(pid, kej, t):
        for era, scope, key, basis in [
            ("2024+", "prov_jenis", f"{pid}|{kej}|{t}", "provinsi & jenis (2024+)"),
            ("semua", "prov_jenis", f"{pid}|{kej}|{t}", "provinsi & jenis (2015-sekarang)"),
            ("2024+", "jenis", f"{kej}|{t}", "jenis bencana nasional (2024+)"),
            ("semua", "jenis", f"{kej}|{t}", "jenis bencana nasional (2015-sekarang)")]:
            s = est.get(era, {}).get(scope, {}).get(key)
            if s and s.get("n", 0) >= 5:
                return s, basis
        return None, None

    P = {}
    for (jk, p, m), pr in zip(keys, proba):
        pp = [0, 0, 0, 0]
        for c, v in zip(model.classes_, pr):
            pp[int(c)] = round(float(v) * 100)
        t = int(model.classes_[pr.argmax()])
        s, basis = cari(str(int(p["id_prov"])), jk, t)
        if s:
            q = lambda k, f: int(round(s[k][f]))
            e = {"t": t, "p": pp, "e": [q("korban_jiwa", "median"), q("terdampak", "median"), q("kerusakan", "median")],
                 "g": [q("korban_jiwa", "p25"), q("korban_jiwa", "p75"), q("terdampak", "p25"), q("terdampak", "p75"),
                       q("kerusakan", "p25"), q("kerusakan", "p75")], "b": basis, "n": int(s["n"])}
        else:
            e = {"t": t, "p": pp, "e": None, "g": None, "b": "tidak ada data historis yang cukup", "n": 0}
        P[f"{jenis_display(jk)}|{p['label']}|{m}"] = e
    dump("prediksi", P)

    # 6) laporan + salinan file untuk tombol Unduh
    lap = []
    for kode, (p, judul) in X._files().items():
        st = p.stat()
        desk = f"{X._size(st.st_size)} · diperbarui {datetime.fromtimestamp(st.st_mtime):%d-%m-%Y}"
        if kode == "dataset":
            desk = f"{X._n_dataset():,}".replace(",", ".") + " laporan · " + desk
        url = None
        if st.st_size <= LIMIT_BYTES or args.dengan_dataset:
            shutil.copy2(p, OUT / "unduh" / p.name)
            url = f"data/unduh/{p.name}"
        else:
            desk += " · terlalu besar untuk versi publik"
        lap.append({"kode": kode, "judul": judul, "deskripsi": desk, "tipe": p.suffix.lstrip(".").upper(), "url": url})
    dump("laporan", lap)

    # 7) meta
    kl = lk.get("klaster", {})
    fr = mm.get("faktor_risiko", [])
    dump("meta", {"akurasi": mm.get("evaluasi", {}).get("accuracy"),
                  "wilayah": kl.get("n_wilayah_unik") or int(df.id_kab.nunique()),
                  "faktor": {"labels": [f["faktor"] for f in fr], "values": [f["bobot"] for f in fr]},
                  "terakhir": {"tanggal": last.strftime("%Y-%m-%d"), "tahun": int(last.year), "bulan_lengkap": int(cut)},
                  "jenis": jenis, "provinsi": provs, "diekspor": datetime.now().isoformat(timespec="seconds")})
    print("Selesai. Jalankan frontend:  cd frontend ; python -m http.server 8001")


if __name__ == "__main__":
    main()