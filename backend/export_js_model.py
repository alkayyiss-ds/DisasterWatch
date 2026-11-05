"""
Ekspor model Random Forest Prediksi Dampak ke JavaScript, agar halaman Prediksi Dampak bisa
berjalan TANPA backend (cukup hosting statis: GitHub Pages, Netlify, Vercel, atau buka file langsung).

Menjalankan (dari root repo, setelah train_model.py):
    python backend/export_js_model.py
(otomatis ikut dijalankan oleh `python backend/export_static.py`)

Hasil:
    frontend/js/model/rf_forest.js   300 pohon Random Forest (dipangkas, lihat di bawah)
    frontend/js/model/dw_lookup.js   data pendukung: opsi dropdown, riwayat provinsi, estimasi dampak,
                                     profil klaster, aturan mitigasi (mitigasi.py), metrik model

Logika prediksinya ada di frontend/js/model/dw_model.js (ditulis manual, tidak di-generate).
Keluaran DWModel.prediksi() sama dengan POST /api/prediksi di backend/app.py.

Pemangkasan pohon
-----------------
Halaman hanya punya 10 jenis bencana x 38 provinsi x 12 bulan = 4.560 kombinasi input. Setiap pohon
dijalankan untuk seluruh kombinasi tersebut. Cabang yang tidak pernah dilalui dibuang, dan node yang
semua input-nya selalu ke arah yang sama dilewati. Hasilnya tetap 300 pohon yang sama dan memberi
probabilitas yang SAMA PERSIS dengan model asli untuk setiap input halaman, tetapi ukurannya jauh lebih kecil.
Skrip ini memverifikasi kesamaan itu sebelum menulis file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dw_model import (BULAN, FRONTEND_DIR, JENIS_ALIASES, JENIS_LABELS, MODEL_DIR,  # noqa: E402
                      SEV_LABELS, _time_features, make_inference_row)
import mitigasi  # noqa: E402

OUT_DIR = FRONTEND_DIR / "js" / "model"
MIN_N_ESTIMASI = 5   # sama dengan MIN_N di backend/app.py (minimal laporan historis agar median dipakai)


def domain_year(lookup: dict) -> int:
    """Tahun yang dipakai untuk prediksi = tahun laporan terakhir di data. Semua tahun sesudahnya memberi
    hasil yang sama karena ambang split `year` terbesar di pohon lebih kecil dari tahun tersebut."""
    return int(lookup["riwayat"]["last_date"][:4])


def build_domain(lookup: dict, year: int) -> tuple[pd.DataFrame, list[tuple]]:
    rows, keys = [], []
    for p in lookup["provinsi"]:
        for j in lookup["jenis"]:
            for b in range(1, 13):
                rows.append(make_inference_row(j["value"], p, b, year, lookup["riwayat"]))
                keys.append((p["id_prov"], j["value"], b))
    return pd.concat(rows, ignore_index=True), keys


def prune_tree(tree, reach: np.ndarray) -> dict:
    """Pohon ringkas: hanya split yang kedua cabangnya dilalui input halaman.

    Format (indeks anak >= 0 = node internal, < 0 = daun ke-(~indeks)):
      f[i], t[i]   fitur & ambang node internal i (ke kiri jika x[f] <= t)
      l[i], r[i]   anak kiri & kanan
      v            jumlah sampel per kelas di setiap daun (4 angka per daun, bobot bootstrap)
    """
    cl, cr = tree.children_left, tree.children_right
    feat, thr = tree.feature, tree.threshold
    value = tree.value[:, 0, :]
    wn = tree.weighted_n_node_samples
    out = {"f": [], "t": [], "l": [], "r": [], "v": []}

    def walk(n: int) -> int:
        while cl[n] != -1 and not (reach[cl[n]] and reach[cr[n]]):   # lewati node dengan satu cabang terpakai
            n = cl[n] if reach[cl[n]] else cr[n]
        if cl[n] == -1:
            counts = value[n] * wn[n]
            ints = np.rint(counts)
            assert np.allclose(counts, ints, atol=1e-6), "jumlah sampel daun bukan bilangan bulat"
            out["v"].extend(int(c) for c in ints)
            return ~(len(out["v"]) // 4 - 1)
        i = len(out["f"])
        out["f"].append(int(feat[n])); out["t"].append(float(thr[n]))
        out["l"].append(0); out["r"].append(0)
        out["l"][i] = walk(cl[n])
        out["r"][i] = walk(cr[n])
        return i

    out["root"] = walk(0)
    return out


def predict_pruned(trees: list[dict], X: np.ndarray) -> np.ndarray:
    """Implementasi Python dari logika dw_model.js — untuk verifikasi sebelum menulis file."""
    out = np.zeros((len(X), 4))
    rows = np.arange(len(X))
    for tr in trees:
        f, t = np.asarray(tr["f"], dtype=int), np.asarray(tr["t"], dtype=float)
        l, r = np.asarray(tr["l"], dtype=int), np.asarray(tr["r"], dtype=int)
        v = np.asarray(tr["v"], dtype=float).reshape(-1, 4)
        n = np.full(len(X), tr["root"])
        while (n >= 0).any():
            a = n >= 0
            idx = n[a]
            n[a] = np.where(X[rows[a], f[idx]] <= t[idx], l[idx], r[idx])
        c = v[~n]
        p = c / c.sum(axis=1, keepdims=True)
        out += p / p.sum(axis=1, keepdims=True)
    return out / len(trees)


def js_file(var: str, obj, header: str) -> str:
    body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return f"/* {header}\n   File ini DI-GENERATE oleh backend/export_js_model.py — jangan diedit manual. */\nwindow.{var}={body};\n"


def main() -> None:
    model = joblib.load(MODEL_DIR / "rf_severity.joblib")
    meta = json.loads((MODEL_DIR / "model_meta.json").read_text(encoding="utf-8"))
    lookup = json.loads((MODEL_DIR / "lookup.json").read_text(encoding="utf-8"))
    pre, rf = model[:-1], model[-1]

    year = domain_year(lookup)
    X_df, keys = build_domain(lookup, year)
    X = pre.transform(X_df).astype(np.float32)          # pohon sklearn membandingkan fitur dalam float32
    proba_asli = model.predict_proba(X_df)

    indicator, ptr = rf.decision_path(X)
    reach_all = np.asarray(indicator.sum(axis=0)).ravel() > 0
    trees = [prune_tree(est.tree_, reach_all[ptr[i]:ptr[i + 1]]) for i, est in enumerate(rf.estimators_)]

    proba_js = predict_pruned(trees, X.astype(np.float64))
    selisih = float(np.abs(proba_js - proba_asli).max())
    sama_kelas = bool((proba_js.argmax(1) == proba_asli.argmax(1)).all())
    sama_4desimal = bool((np.round(proba_js, 4) == np.round(proba_asli, 4)).all())
    n_asli = sum(e.tree_.node_count for e in rf.estimators_)
    n_ringkas = sum(len(t["f"]) + len(t["v"]) // 4 for t in trees)
    print(f"Kombinasi input  : {len(keys):,} (tahun {year})")
    print(f"Node pohon       : {n_asli:,} -> {n_ringkas:,} setelah pemangkasan")
    print(f"Selisih maks     : {selisih:.2e} | kelas sama: {sama_kelas} | 4 desimal sama: {sama_4desimal}")
    if not (sama_kelas and sama_4desimal and selisih < 1e-9):
        raise SystemExit("Verifikasi gagal: hasil pohon ringkas berbeda dari model asli.")

    # ── Spesifikasi fitur (urutan kolom setelah ColumnTransformer) ──────────────
    ct = pre.named_steps["pre"] if hasattr(pre, "named_steps") else pre[0]
    ohe = ct.named_transformers_["cat"]
    cat_cols = list(ct.transformers_[0][2])
    num_cols = list(ct.transformers_[1][2])
    bulan_fitur = []
    for b in range(1, 13):
        tf = _time_features([b], [year])
        bulan_fitur.append({"month_sin": float(tf["month_sin"][0]), "month_cos": float(tf["month_cos"][0]),
                            "musim_hujan": int(tf["musim_hujan"][0])})

    forest = {
        "versi": meta["versi"], "nama_model": meta["nama_model"], "tahun_domain": year,
        "kelas": SEV_LABELS,
        "fitur": {"nama": [str(n) for n in ct.get_feature_names_out()],
                  "kategorikal": {c: [str(v) for v in cats] for c, cats in zip(cat_cols, ohe.categories_)},
                  "numerik": num_cols},
        "bulan_fitur": bulan_fitur,
        "n_pohon": len(trees),
        "pohon": [{"root": t["root"], "f": t["f"], "t": t["t"], "l": t["l"], "r": t["r"], "v": t["v"]} for t in trees],
    }

    # ── Data pendukung (sama dengan yang dipakai backend/app.py & mitigasi.py) ───
    ev = meta.get("evaluasi", {})
    data = {
        "versi": meta["versi"],
        "model": {"nama": meta["nama_model"], "accuracy": ev.get("accuracy"),
                  "balanced_accuracy": ev.get("balanced_accuracy"), "mse": ev.get("mse"), "n_uji": ev.get("n_uji")},
        "provinsi": lookup["provinsi"],
        "jenis": lookup["jenis"],
        "jenis_alias": JENIS_ALIASES,
        "jenis_label": JENIS_LABELS,
        "bulan": BULAN,
        "kelas": SEV_LABELS,
        "kepadatan": ["Rendah", "Sedang", "Tinggi", "Sangat tinggi"],
        "min_n_estimasi": MIN_N_ESTIMASI,
        "riwayat": lookup["riwayat"],
        "estimasi": lookup["estimasi"],
        "klaster": lookup["klaster"],
        "mitigasi": {"per_tingkat": {str(k): v for k, v in mitigasi.PER_TINGKAT.items()},
                     "per_jenis": mitigasi.PER_JENIS,
                     "per_kepadatan": mitigasi.PER_KEPADATAN,
                     "per_klaster": {str(k): v for k, v in mitigasi.PER_KLASTER.items()}},
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f1 = OUT_DIR / "rf_forest.js"
    f2 = OUT_DIR / "dw_lookup.js"
    f1.write_text(js_file("DW_RF_FOREST", forest,
                          f"DisasterWatch — Random Forest Prediksi Dampak ({len(trees)} pohon, versi {meta['versi']})"),
                  encoding="utf-8")
    f2.write_text(js_file("DW_LOOKUP", data, f"DisasterWatch — data pendukung Prediksi Dampak (versi {meta['versi']})"),
                  encoding="utf-8")
    for f in (f1, f2):
        print(f"Tersimpan        : {f.relative_to(FRONTEND_DIR.parent)} ({f.stat().st_size / 1024:,.0f} KB)")


if __name__ == "__main__":
    main()
