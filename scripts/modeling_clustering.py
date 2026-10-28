"""
DisasterWatch SDGs 13: Sistem Prediksi dan Pemetaan Risiko Bencana Indonesia
Script Pemodelan dan Evaluasi Clustering Risiko Bencana Indonesia (Tingkat Kabupaten/Kota)

Penulis: DisasterWatch Data Science Team
Sumber Data: Geoportal Data Bencana Indonesia - BNPB
"""

import sys
import os
from pathlib import Path
import json
import warnings
warnings.filterwarnings('ignore')

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN, HDBSCAN
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.decomposition import PCA

# ─────────────────────────────────────────────────────────────────────────────
# 1. SETUP PATH DAN SEED
# ─────────────────────────────────────────────────────────────────────────────
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

ROOT = Path(__file__).resolve().parent.parent
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("DISASTERWATCH SDGs 13: PEMODELAN & EVALUASI CLUSTERING RISIKO BENCANA INDONESIA")
print("=" * 80)
print(f"Root Directory    : {ROOT}")
print(f"Data Processed Dir: {DATA_PROCESSED}")
print(f"Figures Output Dir: {FIGURES_DIR}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. INGESTION DATA DAN AUDIT
# ─────────────────────────────────────────────────────────────────────────────
CLUSTER_READY_FILE = DATA_PROCESSED / "bnpb_disaster_cluster_ready.csv"
CLEAN_FILE = DATA_PROCESSED / "bnpb_disaster_clean.csv"

if not CLUSTER_READY_FILE.exists() or not CLEAN_FILE.exists():
    raise FileNotFoundError(f"File data preprocessed tidak ditemukan di {DATA_PROCESSED}")

df_kab = pd.read_csv(CLUSTER_READY_FILE, encoding="utf-8-sig")
df_clean = pd.read_csv(CLEAN_FILE, encoding="utf-8-sig", low_memory=False)

print(f"\n[1] Data Loaded:")
print(f" - df_kab (cluster ready): {df_kab.shape[0]} kabupaten/kota, {df_kab.shape[1]} kolom")
print(f" - df_clean              : {df_clean.shape[0]} laporan kejadian bencana")

# Ekstraksi koordinat geografis representatif per kabupaten/kota
coords = df_clean.groupby("id_kab").agg({
    "geometry_lat": "mean",
    "geometry_lon": "mean"
}).reset_index().rename(columns={
    "geometry_lat": "latitude",
    "geometry_lon": "longitude"
})

# Hitung komposisi jenis bencana dominan per id_kab dari data kejadian
kejadian_counts = df_clean.pivot_table(
    index="id_kab", 
    columns="kejadian", 
    values="id_jenis_bencana", 
    aggfunc="count", 
    fill_value=0
)
kejadian_counts.columns = [f"freq_{c.lower().replace(' ', '_')}" for c in kejadian_counts.columns]
top_kejadian_per_kab = df_clean.groupby("id_kab")["kejadian"].agg(
    lambda s: s.value_counts().index[0] if len(s) > 0 else "UNKNOWN"
).rename("bencana_dominan")

df_kab = df_kab.merge(coords, on="id_kab", how="left")
df_kab = df_kab.merge(kejadian_counts, on="id_kab", how="left")
df_kab = df_kab.merge(top_kejadian_per_kab, on="id_kab", how="left")

print(f" - Koordinat berhasil digabungkan: {df_kab['latitude'].notna().sum()} / {len(df_kab)} kabupaten/kota valid")

# ─────────────────────────────────────────────────────────────────────────────
# 3. FITUR SELECTION DAN SCALING
# ─────────────────────────────────────────────────────────────────────────────
# Fitur risiko numerik yang digunakan untuk pemodelan nonspasial
feature_cols = [
    'total_laporan',
    'total_korban_jiwa',
    'total_terdampak',
    'total_material',
    'total_agri',
    'jenis_bencana_unik',
    'avg_severity_score',
    'pct_severity_berat',
    'avg_korban_per_event',
    'avg_terdampak_per_event'
]

print(f"\n[2] Pemilihan Fitur Clustering:")
print(f" Fitur terpilih ({len(feature_cols)}): {feature_cols}")
print(f" Catatan: 'total_kerugian' dieksklusikan karena varians 0 (belum dilaporkan di 2026).")
print(f" Catatan: 'longitude' & 'latitude' dieksklusikan dari clustering profil dampak")
print(f"          agar tidak mendistorsi jarak profil risiko dengan jarak fisik bumi.")

X_raw = df_kab[feature_cols].fillna(0).values

# Skewness checking
skewness_raw = pd.Series(df_kab[feature_cols].skew(), name="Raw Skewness")
skewness_log = pd.Series(np.log1p(df_kab[feature_cols]).skew(), name="Log1p Skewness")
skew_comparison = pd.concat([skewness_raw, skewness_log], axis=1)
print("\nPerbandingan Skewness Fitur Sebelum dan Sesudah Log1p:")
print(skew_comparison.round(2))

# Penerapan Log1p + StandardScaler untuk normalisasi skewness & heavy-tail
scaler = StandardScaler()
X_scaled = scaler.fit_transform(np.log1p(X_raw))

# Existing scaled features (RobustScaler) untuk baseline perbandingan
existing_scaled_cols = ['scaled_' + c for c in feature_cols]
X_robust = df_kab[existing_scaled_cols].fillna(0).values

# ─────────────────────────────────────────────────────────────────────────────
# 4. GRID EVALUASI BERBAGAI ALGORITMA CLUSTERING
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] Mengevaluasi Algoritma Clustering (K-Means, Agglomerative, DBSCAN, HDBSCAN)...")
metrics_records = []

# --- A. K-Means ---
for k in range(2, 7):
    km = KMeans(n_clusters=k, random_state=RANDOM_SEED, n_init=20).fit(X_scaled)
    sil = silhouette_score(X_scaled, km.labels_)
    db = davies_bouldin_score(X_scaled, km.labels_)
    ch = calinski_harabasz_score(X_scaled, km.labels_)
    sizes = np.bincount(km.labels_).tolist()
    metrics_records.append({
        'Algorithm': 'K-Means',
        'Parameter': f'k={k}',
        'k': k,
        'Silhouette': round(sil, 4),
        'Davies_Bouldin': round(db, 4),
        'Calinski_Harabasz': round(ch, 2),
        'Clusters': k,
        'Noise_Count': 0,
        'Cluster_Sizes': str(sizes),
        'Notes': 'Partisi seimbang, interpretabilitas tinggi'
    })

# --- B. Agglomerative (Ward) ---
for k in range(2, 7):
    agg = AgglomerativeClustering(n_clusters=k, linkage='ward').fit(X_scaled)
    sil = silhouette_score(X_scaled, agg.labels_)
    db = davies_bouldin_score(X_scaled, agg.labels_)
    ch = calinski_harabasz_score(X_scaled, agg.labels_)
    sizes = np.bincount(agg.labels_).tolist()
    metrics_records.append({
        'Algorithm': 'Agglomerative (Ward)',
        'Parameter': f'k={k}',
        'k': k,
        'Silhouette': round(sil, 4),
        'Davies_Bouldin': round(db, 4),
        'Calinski_Harabasz': round(ch, 2),
        'Clusters': k,
        'Noise_Count': 0,
        'Cluster_Sizes': str(sizes),
        'Notes': 'Hirarki aglomeratif jarak minimal varians'
    })

# --- C. Agglomerative (Complete) ---
for k in range(2, 7):
    agg = AgglomerativeClustering(n_clusters=k, linkage='complete').fit(X_scaled)
    sil = silhouette_score(X_scaled, agg.labels_)
    db = davies_bouldin_score(X_scaled, agg.labels_)
    ch = calinski_harabasz_score(X_scaled, agg.labels_)
    sizes = np.bincount(agg.labels_).tolist()
    metrics_records.append({
        'Algorithm': 'Agglomerative (Complete)',
        'Parameter': f'k={k}',
        'k': k,
        'Silhouette': round(sil, 4),
        'Davies_Bouldin': round(db, 4),
        'Calinski_Harabasz': round(ch, 2),
        'Clusters': k,
        'Noise_Count': 0,
        'Cluster_Sizes': str(sizes),
        'Notes': 'Sensitif outlier, cluster tidak seimbang'
    })

# --- D. DBSCAN pada Ruang Fitur Risiko ---
for eps in [1.0, 1.5, 2.0]:
    for ms in [3, 5, 8]:
        dbs = DBSCAN(eps=eps, min_samples=ms).fit(X_scaled)
        labels = dbs.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = (labels == -1).sum()
        if n_clusters > 1:
            mask = labels != -1
            sil = silhouette_score(X_scaled[mask], labels[mask]) if mask.sum() > n_clusters else -1
            db = davies_bouldin_score(X_scaled[mask], labels[mask]) if mask.sum() > n_clusters else -1
            ch = calinski_harabasz_score(X_scaled[mask], labels[mask]) if mask.sum() > n_clusters else -1
        else:
            sil, db, ch = -1, -1, -1
        metrics_records.append({
            'Algorithm': 'DBSCAN (Feature Space)',
            'Parameter': f'eps={eps}, ms={ms}',
            'k': n_clusters,
            'Silhouette': round(sil, 4) if sil != -1 else np.nan,
            'Davies_Bouldin': round(db, 4) if db != -1 else np.nan,
            'Calinski_Harabasz': round(ch, 2) if ch != -1 else np.nan,
            'Clusters': n_clusters,
            'Noise_Count': n_noise,
            'Cluster_Sizes': f'valid={len(labels)-n_noise}, noise={n_noise}',
            'Notes': f'Noise {n_noise}/{len(labels)} ({n_noise/len(labels)*100:.1f}%)'
        })

# --- E. HDBSCAN pada Ruang Fitur Risiko ---
for mcs in [5, 10, 15]:
    hdb = HDBSCAN(min_cluster_size=mcs).fit(X_scaled)
    labels = hdb.labels_
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    if n_clusters > 1:
        mask = labels != -1
        sil = silhouette_score(X_scaled[mask], labels[mask]) if mask.sum() > n_clusters else -1
        db = davies_bouldin_score(X_scaled[mask], labels[mask]) if mask.sum() > n_clusters else -1
        ch = calinski_harabasz_score(X_scaled[mask], labels[mask]) if mask.sum() > n_clusters else -1
    else:
        sil, db, ch = -1, -1, -1
    metrics_records.append({
        'Algorithm': 'HDBSCAN (Feature Space)',
        'Parameter': f'min_cluster_size={mcs}',
        'k': n_clusters,
        'Silhouette': round(sil, 4) if sil != -1 else np.nan,
        'Davies_Bouldin': round(db, 4) if db != -1 else np.nan,
        'Calinski_Harabasz': round(ch, 2) if ch != -1 else np.nan,
        'Clusters': n_clusters,
        'Noise_Count': n_noise,
        'Cluster_Sizes': f'valid={len(labels)-n_noise}, noise={n_noise}',
        'Notes': f'Noise {n_noise}/{len(labels)} ({n_noise/len(labels)*100:.1f}%)'
    })

# --- F. Spatial DBSCAN (Haversine pada Koordinat Fisik Bumi) ---
rads = np.radians(df_kab[['latitude', 'longitude']].values)
for km_eps in [100, 150, 200]:
    eps_rad = km_eps / 6371.0
    for ms in [3, 5]:
        db_sp = DBSCAN(eps=eps_rad, min_samples=ms, metric='haversine').fit(rads)
        labels = db_sp.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = (labels == -1).sum()
        if n_clusters > 1:
            mask = labels != -1
            sil = silhouette_score(rads[mask], labels[mask], metric='haversine') if mask.sum() > n_clusters else -1
            db = davies_bouldin_score(rads[mask], labels[mask]) if mask.sum() > n_clusters else -1
            ch = calinski_harabasz_score(rads[mask], labels[mask]) if mask.sum() > n_clusters else -1
        else:
            sil, db, ch = -1, -1, -1
        metrics_records.append({
            'Algorithm': 'Spatial DBSCAN (Haversine)',
            'Parameter': f'eps={km_eps}km, ms={ms}',
            'k': n_clusters,
            'Silhouette': round(sil, 4) if sil != -1 else np.nan,
            'Davies_Bouldin': round(db, 4) if db != -1 else np.nan,
            'Calinski_Harabasz': round(ch, 2) if ch != -1 else np.nan,
            'Clusters': n_clusters,
            'Noise_Count': n_noise,
            'Cluster_Sizes': f'valid={len(labels)-n_noise}, noise={n_noise}',
            'Notes': f'Pengelompokan hotspot spasial kepulauan Indonesia'
        })

df_metrics = pd.DataFrame(metrics_records)
metrics_file = DATA_PROCESSED / "clustering_metrics_comparison.csv"
df_metrics.to_csv(metrics_file, index=False, encoding="utf-8-sig")
print(f"[OK] Tabel evaluasi metrik disimpan ke: {metrics_file}")
print("\nRingkasan Metrik Model Utama:")
print(df_metrics[df_metrics['Algorithm'].isin(['K-Means', 'Agglomerative (Ward)', 'Agglomerative (Complete)'])][['Algorithm', 'k', 'Silhouette', 'Davies_Bouldin', 'Calinski_Harabasz', 'Cluster_Sizes']].to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 5. PEMILIHAN MODEL TERBAIK & PENETAPAN LABEL PROFIL RISIKO
# ─────────────────────────────────────────────────────────────────────────────
# Model Terbaik: K-Means k=4 dengan Log1p + StandardScaler
# Alasan:
# 1. K-Means k=4 menghasilkan 4 kuadran risiko yang sangat interpretable bagi mitigasi BNPB:
#    - Cluster 0: Risiko Rendah / Kejadian Sporadis
#    - Cluster 1: Risiko Sedang / Kerusakan Infrastruktur & Pemukiman
#    - Cluster 2: Risiko Tinggi / Dampak Kemanusiaan & Pengungsian
#    - Cluster 3: Risiko Ekstrem / Multi-Hazard & Fatalitas Tinggi
# 2. Skor Silhouette stabil (0.3237), Davies-Bouldin rendah (1.2204), Calinski-Harabasz tinggi (172.78).
# 3. Ukuran cluster seimbang ([172, 120, 105, 15]), tidak mengalami keruntuhan (degenerasi) cluster
#    seperti DBSCAN (yang membuang 25-50% data sebagai noise) atau Agglomerative Complete (400 vs 12).

best_kmeans = KMeans(n_clusters=4, random_state=RANDOM_SEED, n_init=25)
cluster_labels_raw = best_kmeans.fit_predict(X_scaled)

# Standarisasi nomor cluster agar berurutan berdasarkan tingkat rata-rata severity:
# Kita urutkan cluster 0..3 dari tingkat dampak terendah ke tertinggi
cluster_severity_rank = (
    pd.DataFrame({'cluster_raw': cluster_labels_raw, 'score': df_kab['avg_severity_score']})
    .groupby('cluster_raw')['score'].mean()
    .sort_values().index.tolist()
)
rank_map = {old: new for new, old in enumerate(cluster_severity_rank)}
df_kab['cluster'] = [rank_map[c] for c in cluster_labels_raw]

# Label nama profil dan deskripsi metodologis
CLUSTER_NAMES = {
    0: "Risiko Rendah (Sporadis & Dampak Minimal)",
    1: "Risiko Multi-Bencana Kronis & Kerusakan Lahan",
    2: "Risiko Kemanusiaan Akut & Pengungsian Massal",
    3: "Risiko Katastropik & Fatalitas Ekstrem"
}
CLUSTER_SHORT_NAMES = {
    0: "Tingkat I - Rendah/Sporadis",
    1: "Tingkat II - Kronis/Multi-Hazard",
    2: "Tingkat III - Kemanusiaan Akut",
    3: "Tingkat IV - Katastropik Ekstrem"
}
CLUSTER_COLORS = {
    0: "#2ca02c", # Hijau
    1: "#1f77b4", # Biru
    2: "#ff7f0e", # Oranye
    3: "#d62728"  # Merah
}

df_kab['cluster_name'] = df_kab['cluster'].map(CLUSTER_NAMES)
df_kab['cluster_short'] = df_kab['cluster'].map(CLUSTER_SHORT_NAMES)

print(f"\n[4] Profiling Hasil Clustering K-Means (k=4):")
cluster_summary = df_kab.groupby('cluster')[feature_cols].mean()
cluster_summary['jumlah_wilayah'] = df_kab.groupby('cluster').size()
cluster_summary['persentase'] = (cluster_summary['jumlah_wilayah'] / len(df_kab) * 100).round(1)
cluster_summary['nama_profil'] = [CLUSTER_NAMES[c] for c in cluster_summary.index]

print(cluster_summary[['nama_profil', 'jumlah_wilayah', 'persentase', 'total_laporan', 'total_korban_jiwa', 'total_terdampak', 'total_material', 'total_agri']].round(2).to_string())

# Simpan dataset cluster hasil akhir
output_cluster_file = DATA_PROCESSED / "bnpb_disaster_clusters.csv"
df_kab.to_csv(output_cluster_file, index=False, encoding="utf-8-sig")
print(f"[OK] Dataset cluster per kabupaten/kota disimpan ke: {output_cluster_file}")

# Simpan ringkasan profil cluster
profile_file = DATA_PROCESSED / "cluster_profiles.csv"
cluster_summary.to_csv(profile_file, encoding="utf-8-sig")
print(f"[OK] Tabel profil cluster disimpan ke: {profile_file}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. SPATIAL DBSCAN MODEL UNTUK PERBANDINGAN HOTSPOT
# ─────────────────────────────────────────────────────────────────────────────
best_spatial_eps_km = 150
best_spatial_ms = 5
eps_rad = best_spatial_eps_km / 6371.0
spatial_dbs = DBSCAN(eps=eps_rad, min_samples=best_spatial_ms, metric='haversine').fit(rads)
df_kab['spatial_cluster'] = spatial_dbs.labels_
n_spatial_clusters = len(set(spatial_dbs.labels_)) - (1 if -1 in spatial_dbs.labels_ else 0)
n_spatial_noise = (spatial_dbs.labels_ == -1).sum()
print(f"\n[5] Spatial DBSCAN (Hotspot Geografis 150km): {n_spatial_clusters} zona kepulauan, {n_spatial_noise} wilayah terisolasi (noise)")

# ─────────────────────────────────────────────────────────────────────────────
# 7. GENERASI VISUALISASI LENGKAP
# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] Menghasilkan Visualisasi Profesional...")

# --- Figure 1: Perbandingan Metrik Evaluasi Model ---
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
km_metrics = df_metrics[df_metrics['Algorithm'] == 'K-Means']
agg_ward = df_metrics[df_metrics['Algorithm'] == 'Agglomerative (Ward)']
agg_comp = df_metrics[df_metrics['Algorithm'] == 'Agglomerative (Complete)']

# Silhouette
axes[0].plot(km_metrics['k'], km_metrics['Silhouette'], marker='o', lw=2.5, color='#1f77b4', label='K-Means')
axes[0].plot(agg_ward['k'], agg_ward['Silhouette'], marker='s', lw=2.5, color='#2ca02c', label='Agglomerative (Ward)')
axes[0].plot(agg_comp['k'], agg_comp['Silhouette'], marker='^', lw=2.5, color='#ff7f0e', label='Agglomerative (Complete)')
axes[0].axvline(4, color='red', ls='--', alpha=0.7, label='Optimal k=4')
axes[0].set_title('Silhouette Score (Lebih tinggi lebih baik)', fontsize=12, fontweight='bold')
axes[0].set_xlabel('Jumlah Cluster (k)')
axes[0].set_ylabel('Silhouette Score')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Davies-Bouldin
axes[1].plot(km_metrics['k'], km_metrics['Davies_Bouldin'], marker='o', lw=2.5, color='#1f77b4', label='K-Means')
axes[1].plot(agg_ward['k'], agg_ward['Davies_Bouldin'], marker='s', lw=2.5, color='#2ca02c', label='Agglomerative (Ward)')
axes[1].plot(agg_comp['k'], agg_comp['Davies_Bouldin'], marker='^', lw=2.5, color='#ff7f0e', label='Agglomerative (Complete)')
axes[1].axvline(4, color='red', ls='--', alpha=0.7, label='Optimal k=4')
axes[1].set_title('Davies-Bouldin Index (Lebih rendah lebih baik)', fontsize=12, fontweight='bold')
axes[1].set_xlabel('Jumlah Cluster (k)')
axes[1].set_ylabel('Davies-Bouldin Index')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

# Calinski-Harabasz
axes[2].plot(km_metrics['k'], km_metrics['Calinski_Harabasz'], marker='o', lw=2.5, color='#1f77b4', label='K-Means')
axes[2].plot(agg_ward['k'], agg_ward['Calinski_Harabasz'], marker='s', lw=2.5, color='#2ca02c', label='Agglomerative (Ward)')
axes[2].plot(agg_comp['k'], agg_comp['Calinski_Harabasz'], marker='^', lw=2.5, color='#ff7f0e', label='Agglomerative (Complete)')
axes[2].axvline(4, color='red', ls='--', alpha=0.7, label='Optimal k=4')
axes[2].set_title('Calinski-Harabasz Score (Lebih tinggi lebih baik)', fontsize=12, fontweight='bold')
axes[2].set_xlabel('Jumlah Cluster (k)')
axes[2].set_ylabel('Calinski-Harabasz Score')
axes[2].legend()
axes[2].grid(True, alpha=0.3)

plt.suptitle('Evaluasi Metrik Model Clustering Risiko Bencana Indonesia', fontsize=14, fontweight='bold', y=1.03)
plt.tight_layout()
fig.savefig(FIGURES_DIR / "clustering_metrics_evaluation.png", dpi=300, bbox_inches='tight')
plt.close(fig)
print(f" [OK] Disimpan: {FIGURES_DIR / 'clustering_metrics_evaluation.png'}")

# --- Figure 2: Peta Sebaran Spasial Cluster Risiko Bencana Indonesia ---
fig, ax = plt.subplots(figsize=(18, 9), facecolor='#f8f9fa')
ax.set_facecolor('#e8f4f8') # Warna latar samudra/laut

# Batas spasial Indonesia
ax.set_xlim(94.5, 141.5)
ax.set_ylim(-11.5, 6.5)

# Gambar titik per cluster dengan ukuran dan warna berbeda
for c_idx in sorted(df_kab['cluster'].unique()):
    sub = df_kab[df_kab['cluster'] == c_idx]
    size = 45 if c_idx == 0 else (65 if c_idx == 1 else (95 if c_idx == 2 else 150))
    alpha = 0.7 if c_idx < 3 else 0.95
    edgecolor = 'black' if c_idx == 3 else 'none'
    lw = 1.2 if c_idx == 3 else 0
    ax.scatter(
        sub['longitude'], 
        sub['latitude'], 
        c=CLUSTER_COLORS[c_idx], 
        s=size, 
        alpha=alpha, 
        edgecolors=edgecolor,
        linewidths=lw,
        label=f"{CLUSTER_SHORT_NAMES[c_idx]} (n={len(sub)})",
        zorder=3 + c_idx
    )

# Label beberapa wilayah penting di Cluster Katastropik
sub_cat = df_kab[df_kab['cluster'] == 3]
for _, row in sub_cat.iterrows():
    ax.annotate(
        f"{row['kabkot']}",
        (row['longitude'], row['latitude']),
        textcoords="offset points",
        xytext=(5, 5),
        fontsize=8.5,
        fontweight='bold',
        color='#990000',
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#d62728", lw=0.8, alpha=0.85),
        zorder=10
    )

ax.set_title(
    "PETA PEMETAAN TINGKAT & TIPOLOGI RISIKO BENCANA INDONESIA (SDGs 13)\n"
    "Hasil Clustering Nonspasial Profil Risiko BNPB (K-Means k=4)",
    fontsize=14,
    fontweight='bold',
    pad=15
)
ax.set_xlabel("Bujur Timur (Longitude °E)", fontsize=11)
ax.set_ylabel("Lintang (Latitude °N/S)", fontsize=11)
ax.grid(True, color='white', linestyle='--', linewidth=0.8, alpha=0.8)
ax.legend(loc='lower left', frameon=True, facecolor='white', framealpha=0.95, fontsize=10, title="Tipologi Risiko Bencana")

plt.tight_layout()
fig.savefig(FIGURES_DIR / "map_clustering_indonesia.png", dpi=300, bbox_inches='tight')
plt.close(fig)
print(f" [OK] Disimpan: {FIGURES_DIR / 'map_clustering_indonesia.png'}")

# --- Figure 3: Proyeksi 2D PCA & Ruang Fitur ---
pca = PCA(n_components=2, random_state=RANDOM_SEED)
X_pca = pca.fit_transform(X_scaled)
df_kab['pca_1'] = X_pca[:, 0]
df_kab['pca_2'] = X_pca[:, 1]

fig, ax = plt.subplots(figsize=(10, 8))
for c_idx in sorted(df_kab['cluster'].unique()):
    sub = df_kab[df_kab['cluster'] == c_idx]
    ax.scatter(
        sub['pca_1'], 
        sub['pca_2'], 
        c=CLUSTER_COLORS[c_idx], 
        s=60, 
        alpha=0.75, 
        label=f"{CLUSTER_SHORT_NAMES[c_idx]} (n={len(sub)})"
    )

# Visualisasi Vektor Loading Fitur (Biplot)
loadings = pca.components_.T * np.sqrt(pca.explained_variance_) * 1.5
for i, feat in enumerate(feature_cols):
    ax.arrow(0, 0, loadings[i, 0], loadings[i, 1], color='black', alpha=0.5, head_width=0.08)
    ax.text(loadings[i, 0] * 1.15, loadings[i, 1] * 1.15, feat, color='black', fontsize=8.5, ha='center', va='center')

ax.set_title(
    f"Proyeksi 2D PCA Klaster Risiko Bencana\n"
    f"Varians Terjelaskan: PC1={pca.explained_variance_ratio_[0]*100:.1f}%, PC2={pca.explained_variance_ratio_[1]*100:.1f}% "
    f"(Total: {pca.explained_variance_ratio_[:2].sum()*100:.1f}%)",
    fontsize=12,
    fontweight='bold'
)
ax.set_xlabel(f"Principal Component 1 (Skala Dampak Fisik & Kemanusiaan)", fontsize=10)
ax.set_ylabel(f"Principal Component 2 (Frekuensi & Variasi Bencana)", fontsize=10)
ax.legend(loc='best', frameon=True)
ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(FIGURES_DIR / "pca_clusters_projection.png", dpi=300, bbox_inches='tight')
plt.close(fig)
print(f" [OK] Disimpan: {FIGURES_DIR / 'pca_clusters_projection.png'}")

# --- Figure 4: Radar Chart Profil Relatif Tiap Cluster ---
radar_feats = [
    'total_laporan', 
    'total_korban_jiwa', 
    'total_terdampak', 
    'total_material', 
    'total_agri', 
    'jenis_bencana_unik', 
    'avg_severity_score', 
    'pct_severity_berat'
]
radar_labels = [
    'Frekuensi\nKejadian', 
    'Korban\nJiwa', 
    'Warga\nTerdampak', 
    'Kerusakan\nMaterial', 
    'Kerusakan\nLahan', 
    'Keragaman\nHazard', 
    'Severitas\nRata-rata', 
    'Proporsi\nBerat'
]

# Normalisasi 0 - 1 antar nilai mean cluster untuk radar
cluster_means = df_kab.groupby('cluster')[radar_feats].mean()
cluster_means_norm = (cluster_means - cluster_means.min()) / (cluster_means.max() - cluster_means.min() + 1e-6)

num_vars = len(radar_feats)
angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
angles += angles[:1]

fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
for c_idx in sorted(df_kab['cluster'].unique()):
    values = cluster_means_norm.loc[c_idx].tolist()
    values += values[:1]
    ax.plot(angles, values, color=CLUSTER_COLORS[c_idx], linewidth=2.5, label=CLUSTER_SHORT_NAMES[c_idx])
    ax.fill(angles, values, color=CLUSTER_COLORS[c_idx], alpha=0.15)

ax.set_theta_offset(np.pi / 2)
ax.set_theta_direction(-1)
ax.set_thetagrids(np.degrees(angles[:-1]), radar_labels, fontsize=10)
ax.set_ylim(0, 1.05)
ax.set_title("Radar Chart Profil Risiko Relatif Tiap Cluster Bencana", fontsize=13, fontweight='bold', pad=25)
ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1.1), fontsize=9.5)

plt.tight_layout()
fig.savefig(FIGURES_DIR / "cluster_risk_profiles_radar.png", dpi=300, bbox_inches='tight')
plt.close(fig)
print(f" [OK] Disimpan: {FIGURES_DIR / 'cluster_risk_profiles_radar.png'}")

# --- Figure 5: Distribusi Dampak Kunci per Cluster (Bar Charts) ---
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
cluster_names_order = [CLUSTER_SHORT_NAMES[i] for i in range(4)]
colors_order = [CLUSTER_COLORS[i] for i in range(4)]

# 1. Total Laporan
axes[0, 0].bar(cluster_names_order, cluster_summary['total_laporan'], color=colors_order, edgecolor='black', alpha=0.85)
axes[0, 0].set_title('Rata-rata Frekuensi Kejadian per Wilayah', fontweight='bold')
axes[0, 0].set_ylabel('Rata-rata Jumlah Laporan')
axes[0, 0].tick_params(axis='x', rotation=15)
for i, v in enumerate(cluster_summary['total_laporan']):
    axes[0, 0].text(i, v + 0.3, f"{v:.1f}", ha='center', fontweight='bold', fontsize=9)

# 2. Total Korban Jiwa
axes[0, 1].bar(cluster_names_order, cluster_summary['total_korban_jiwa'], color=colors_order, edgecolor='black', alpha=0.85)
axes[0, 1].set_title('Rata-rata Korban Jiwa (Meninggal + Hilang)', fontweight='bold')
axes[0, 1].set_ylabel('Jiwa')
axes[0, 1].tick_params(axis='x', rotation=15)
for i, v in enumerate(cluster_summary['total_korban_jiwa']):
    axes[0, 1].text(i, v + 0.4, f"{v:.1f}", ha='center', fontweight='bold', fontsize=9)

# 3. Total Penduduk Terdampak
axes[1, 0].bar(cluster_names_order, cluster_summary['total_terdampak'], color=colors_order, edgecolor='black', alpha=0.85)
axes[1, 0].set_title('Rata-rata Penduduk Terdampak & Mengungsi', fontweight='bold')
axes[1, 0].set_ylabel('Jiwa')
axes[1, 0].tick_params(axis='x', rotation=15)
for i, v in enumerate(cluster_summary['total_terdampak']):
    axes[1, 0].text(i, v + 1000, f"{v:,.0f}", ha='center', fontweight='bold', fontsize=9)

# 4. Total Kerusakan Fisik (Material)
axes[1, 1].bar(cluster_names_order, cluster_summary['total_material'], color=colors_order, edgecolor='black', alpha=0.85)
axes[1, 1].set_title('Rata-rata Kerusakan Fisik (Rumah + Fasilitas)', fontweight='bold')
axes[1, 1].set_ylabel('Unit')
axes[1, 1].tick_params(axis='x', rotation=15)
for i, v in enumerate(cluster_summary['total_material']):
    axes[1, 1].text(i, v + 150, f"{v:,.0f}", ha='center', fontweight='bold', fontsize=9)

plt.suptitle('Perbandingan Rata-rata Indikator Dampak Berdasarkan Cluster Risiko', fontsize=14, fontweight='bold', y=0.99)
plt.tight_layout()
fig.savefig(FIGURES_DIR / "cluster_feature_distribution.png", dpi=300, bbox_inches='tight')
plt.close(fig)
print(f" [OK] Disimpan: {FIGURES_DIR / 'cluster_feature_distribution.png'}")

# --- Figure 6: Distribusi Jenis Bencana Dominan per Cluster ---
disaster_crosstab = pd.crosstab(df_kab['cluster_short'], df_kab['bencana_dominan'], normalize='index') * 100
fig, ax = plt.subplots(figsize=(12, 6))
disaster_crosstab.plot(kind='bar', stacked=True, ax=ax, colormap='tab10', edgecolor='white', alpha=0.9)
ax.set_title("Proporsi Jenis Bencana Dominan di Setiap Cluster (%)", fontsize=13, fontweight='bold')
ax.set_ylabel("Persentase Kabupaten/Kota (%)")
ax.set_xlabel("")
ax.tick_params(axis='x', rotation=0)
ax.legend(title="Bencana Dominan", bbox_to_anchor=(1.02, 1), loc='upper left')
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
fig.savefig(FIGURES_DIR / "cluster_disaster_type_breakdown.png", dpi=300, bbox_inches='tight')
plt.close(fig)
print(f" [OK] Disimpan: {FIGURES_DIR / 'cluster_disaster_type_breakdown.png'}")

# --- Figure 7: Peta Hotspot Spasial DBSCAN (Haversine 150km) ---
fig, ax = plt.subplots(figsize=(16, 8), facecolor='#f8f9fa')
ax.set_facecolor('#e8f4f8')
ax.set_xlim(94.5, 141.5)
ax.set_ylim(-11.5, 6.5)

# Plot noise spatial
noise_mask = df_kab['spatial_cluster'] == -1
ax.scatter(
    df_kab.loc[noise_mask, 'longitude'], 
    df_kab.loc[noise_mask, 'latitude'],
    c='gray',
    s=25,
    alpha=0.5,
    marker='x',
    label=f'Wilayah Terisolasi / Outlier Spasial (n={noise_mask.sum()})'
)

# Plot clusters
cmap = plt.get_cmap('tab10', n_spatial_clusters)
for sp_c in range(n_spatial_clusters):
    c_mask = df_kab['spatial_cluster'] == sp_c
    ax.scatter(
        df_kab.loc[c_mask, 'longitude'], 
        df_kab.loc[c_mask, 'latitude'],
        color=cmap(sp_c),
        s=60,
        alpha=0.8,
        label=f'Hotspot Spasial #{sp_c+1} (n={c_mask.sum()})'
    )

ax.set_title(
    "PETA KLASTER SPASIAL DENSITY-BASED (DBSCAN HAVERSINE, eps=150km)\n"
    "Pengelompokan Berdasarkan Kepadatan Geografis Kejadian Bencana di Indonesia",
    fontsize=13,
    fontweight='bold',
    pad=15
)
ax.set_xlabel("Longitude (°E)")
ax.set_ylabel("Latitude (°N/S)")
ax.grid(True, color='white', linestyle='--', alpha=0.8)
ax.legend(loc='lower left', bbox_to_anchor=(0.01, 0.01), fontsize=8.5, ncol=2, framealpha=0.9)

plt.tight_layout()
fig.savefig(FIGURES_DIR / "spatial_dbscan_hotspots_map.png", dpi=300, bbox_inches='tight')
plt.close(fig)
print(f" [OK] Disimpan: {FIGURES_DIR / 'spatial_dbscan_hotspots_map.png'}")

print("\n" + "=" * 80)
print("SELURUH PROSES PEMODELAN, EVALUASI, DAN VISUALISASI SELESAI DENGAN SUKSES!")
print("=" * 80)
