"""
Latih model Random Forest (model klasifikasi terbaik) untuk halaman "Prediksi Dampak".

Jalankan dari root repo:
    python backend/train_model.py

Output (folder backend/models/):
    rf_severity.joblib   pipeline scikit-learn (OneHotEncoder + RandomForestClassifier)
    model_meta.json      metrik evaluasi, hyperparameter, faktor risiko dominan
    lookup.json          daftar opsi, riwayat provinsi, estimasi dampak historis, profil klaster
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from dw_model import (BULAN, CAT_FEATURES, CLUSTERS_CSV, FEATURE_GROUPS, JENIS_LABELS, MODEL_DIR, NUM_FEATURES,
                      REPORTS_CSV, SEV_LABELS, build_training_frame, history_snapshot, jenis_display,
                      load_reports, mse_pdf, province_table)

RANDOM_SEED = 42
N_TREES = 300
LEAF_CANDIDATES = [5, 10, 20]   # dipilih berdasarkan MSE validation (lihat README)


def make_pipeline(min_samples_leaf: int) -> Pipeline:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_FEATURES),
        ("num", "passthrough", NUM_FEATURES),       # pohon keputusan tidak butuh scaling
    ])
    rf = RandomForestClassifier(n_estimators=N_TREES, min_samples_leaf=min_samples_leaf, max_features="sqrt",
                                n_jobs=-1, random_state=RANDOM_SEED)
    return Pipeline([("pre", pre), ("rf", rf)])


def grouped_permutation_importance(pipe, X, y, groups, n_repeats=3, seed=RANDOM_SEED) -> dict:
    """Penurunan accuracy jika SEMUA kolom dalam satu kelompok diacak bersamaan."""
    rng = np.random.default_rng(seed)
    base = accuracy_score(y, pipe.predict(X))
    out = {}
    for name, cols in groups.items():
        drops = []
        for _ in range(n_repeats):
            Xp = X.copy()
            idx = rng.permutation(len(Xp))
            Xp[cols] = Xp[cols].values[idx]
            drops.append(base - accuracy_score(y, pipe.predict(Xp)))
        out[name] = float(np.mean(drops))
    return out


def impact_stats(df: pd.DataFrame) -> dict:
    """Ringkasan dampak historis per (jenis, kelas) dan (provinsi, jenis, kelas)."""
    def summarize(g: pd.DataFrame) -> dict:
        def q(s):
            return {"median": float(s.median()), "p25": float(s.quantile(0.25)), "p75": float(s.quantile(0.75)),
                    "mean": float(s.mean())}
        return {"n": int(len(g)), "korban_jiwa": q(g.korban_jiwa), "terdampak": q(g.terdampak),
                "kerusakan": q(g.kerusakan), "pct_ada_korban": float((g.korban_jiwa >= 1).mean() * 100)}

    out = {}
    for era, d in [("2024+", df[df.year >= 2024]), ("semua", df)]:
        out[era] = {
            "jenis": {f"{k}|{c}": summarize(g) for (k, c), g in d.groupby(["kejadian", "severity_code"])},
            "prov_jenis": {f"{int(p)}|{k}|{c}": summarize(g)
                           for (p, k, c), g in d.groupby(["id_prov", "kejadian", "severity_code"])},
        }
    return out


def cluster_profiles(prov: pd.DataFrame) -> dict:
    """Profil klaster K-Means (rekan) per provinsi.

    Catatan: bnpb_disaster_clusters.csv memuat beberapa baris untuk satu id_kab (variasi penulisan nama
    kab/kota). Diambil satu baris per id_kab, yaitu baris dengan total_laporan terbanyak.
    """
    if not CLUSTERS_CSV.exists():
        return {"tersedia": False}
    c = pd.read_csv(CLUSTERS_CSV, usecols=["id_kab", "cluster", "cluster_name", "cluster_short", "total_laporan"])
    n_rows = len(c)
    c = c.sort_values("total_laporan", ascending=False).drop_duplicates("id_kab")
    c["id_prov"] = (c.id_kab // 100).astype(int)
    names = c.drop_duplicates("cluster").set_index("cluster")[["cluster_name", "cluster_short"]].sort_index()
    per_prov = {}
    for pid, g in c.groupby("id_prov"):
        counts = g.cluster.value_counts().reindex(names.index, fill_value=0)
        dominant = int(counts[counts == counts.max()].index.max())   # seri → klaster berisiko lebih tinggi
        per_prov[str(pid)] = {"dominan": dominant, "n_wilayah": int(len(g)),
                              "distribusi": {str(int(k)): int(v) for k, v in counts.items()}}
    return {
        "tersedia": True,
        "n_baris_file": int(n_rows),
        "n_wilayah_unik": int(len(c)),
        "nama": {str(int(k)): {"nama": r.cluster_name, "pendek": r.cluster_short} for k, r in names.iterrows()},
        "jumlah": {str(int(k)): int(v) for k, v in c.cluster.value_counts().sort_index().items()},
        "provinsi": per_prov,
    }


def main() -> None:
    t0 = time.time()
    print(f"[1/6] Membaca data: {REPORTS_CSV.name}")
    df = load_reports()
    prov = province_table(df)
    X, y = build_training_frame(df, prov)
    print(f"      {len(df):,} laporan · {len(prov)} provinsi · {df.kejadian.nunique()} jenis bencana")

    # ── Split 70/10/20 (sama dengan notebook) ────────────────────────────────
    X_tmp, X_test, y_tmp, y_test = train_test_split(X, y, test_size=0.20, stratify=y, random_state=RANDOM_SEED)
    X_train, X_val, y_train, y_val = train_test_split(X_tmp, y_tmp, test_size=0.125, stratify=y_tmp,
                                                      random_state=RANDOM_SEED)

    print("[2/6] Memilih min_samples_leaf berdasarkan MSE validation")
    tuning = []
    for leaf in LEAF_CANDIDATES:
        p = make_pipeline(leaf).fit(X_train, y_train)
        m = mse_pdf(y_val, p.predict_proba(X_val))
        tuning.append({"min_samples_leaf": leaf, "mse_val": m})
        print(f"      leaf={leaf:<3} MSE val = {m:.4f}")
    best_leaf = min(tuning, key=lambda r: r["mse_val"])["min_samples_leaf"]
    print(f"      → dipilih min_samples_leaf = {best_leaf}")

    print("[3/6] Evaluasi pada data uji (20%)")
    pipe = make_pipeline(best_leaf).fit(pd.concat([X_train, X_val]), np.r_[y_train, y_val])
    P = pipe.predict_proba(X_test)
    yp = P.argmax(axis=1)
    metrics = {
        "accuracy": accuracy_score(y_test, yp),
        "balanced_accuracy": balanced_accuracy_score(y_test, yp),
        "f1_macro": f1_score(y_test, yp, average="macro"),
        "f1_weighted": f1_score(y_test, yp, average="weighted"),
        "mse": mse_pdf(y_test, P),
    }
    report = classification_report(y_test, yp, target_names=SEV_LABELS, output_dict=True)
    cm = confusion_matrix(y_test, yp, labels=range(4)).tolist()
    for k, v in metrics.items():
        print(f"      {k:18s} = {v:.4f}")

    # Baseline pembanding
    base_major = accuracy_score(y_test, np.full_like(y_test, np.bincount(y_train).argmax()))
    oh = OneHotEncoder(handle_unknown="ignore", sparse_output=False).fit(X_train[["kejadian"]])
    lr = LogisticRegression(max_iter=1000).fit(oh.transform(X_train[["kejadian"]]), y_train)
    base_jenis = accuracy_score(y_test, lr.predict(oh.transform(X_test[["kejadian"]])))
    print(f"      baseline kelas mayoritas = {base_major:.4f} | baseline jenis bencana saja = {base_jenis:.4f}")

    print("[4/6] Faktor risiko dominan (grouped permutation importance)")
    imp = grouped_permutation_importance(pipe, X_test, y_test, FEATURE_GROUPS)
    total = sum(max(v, 0) for v in imp.values()) or 1.0
    faktor = sorted(({"faktor": k, "penurunan_accuracy": round(v, 4), "bobot": round(max(v, 0) / total, 4)}
                     for k, v in imp.items()), key=lambda r: -r["penurunan_accuracy"])
    for f in faktor:
        print(f"      {f['faktor']:20s} {f['penurunan_accuracy']:.4f}  ({f['bobot']*100:.1f}%)")

    print("[5/6] Melatih model final dengan SELURUH data")
    final = make_pipeline(best_leaf).fit(X, y)

    print("[6/6] Menyimpan artefak ke", MODEL_DIR)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, MODEL_DIR / "rf_severity.joblib", compress=3)

    jenis_counts = df.kejadian.value_counts()
    meta = {
        "nama_model": "Random Forest — Tingkat Dampak Bencana",
        "versi": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M"),
        "dilatih_pada": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sumber_data": REPORTS_CSV.name,
        "periode_data": [df.date.min().strftime("%Y-%m-%d"), df.date.max().strftime("%Y-%m-%d")],
        "n_laporan": int(len(df)),
        "kelas": SEV_LABELS,
        "distribusi_kelas": {SEV_LABELS[k]: int(v) for k, v in pd.Series(y).value_counts().sort_index().items()},
        "hyperparameter": {"n_estimators": N_TREES, "min_samples_leaf": int(best_leaf), "max_features": "sqrt",
                           "random_state": RANDOM_SEED},
        "tuning": tuning,
        "fitur": {"kategorikal": CAT_FEATURES, "numerik": NUM_FEATURES},
        "evaluasi": {
            "skema": "stratified split 70/10/20; metrik di data uji 20% (model dilatih ulang dengan 80%)",
            "n_uji": int(len(y_test)),
            **{k: round(float(v), 4) for k, v in metrics.items()},
            "baseline_kelas_mayoritas": round(float(base_major), 4),
            "baseline_jenis_bencana_saja": round(float(base_jenis), 4),
            "classification_report": report,
            "confusion_matrix": {"label": SEV_LABELS, "matriks": cm},
        },
        "faktor_risiko": faktor,
        "catatan": [
            "Fitur lokasi & riwayat dihitung di tingkat provinsi karena halaman Prediksi Dampak tidak memiliki input kab/kota.",
            "Kepadatan penduduk tidak tersedia di data BNPB sehingga tidak dipakai model; input ini hanya memengaruhi rekomendasi mitigasi.",
            "Label severity mengikuti aturan preprocessing tim (korban jiwa, warga terdampak, rumah rusak/terendam).",
        ],
        "waktu_latih_detik": round(time.time() - t0, 1),
    }
    lookup = {
        "provinsi": prov[["id_prov", "provinsi", "label", "region", "lon", "lat", "n_laporan"]].to_dict("records"),
        "jenis": [{"value": k, "label": jenis_display(k), "n_laporan": int(jenis_counts.get(k, 0))}
                  for k in JENIS_LABELS if k in jenis_counts.index],
        "bulan": BULAN,
        "riwayat": history_snapshot(df),
        "estimasi": impact_stats(df),
        "klaster": cluster_profiles(prov),
    }
    with open(MODEL_DIR / "model_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    with open(MODEL_DIR / "lookup.json", "w", encoding="utf-8") as f:
        json.dump(lookup, f, ensure_ascii=False)
    size = (MODEL_DIR / "rf_severity.joblib").stat().st_size / 1e6
    print(f"Selesai dalam {time.time() - t0:.0f} detik · rf_severity.joblib = {size:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
