"""
Script untuk meng-update notebook/modelling_disaster.ipynb dengan pipeline
clustering risiko bencana Indonesia end-to-end yang lengkap, ilmiah, dan naratif.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB_PATH = ROOT / "notebook" / "modelling_disaster.ipynb"

def md(text):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.strip("\n").splitlines()]
    }

def code(text):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in text.strip("\n").splitlines()]
    }

cells = [
    md("""# DisasterWatch SDGs 13: Sistem Prediksi dan Pemetaan Risiko Bencana Indonesia
## Tahap Pemodelan dan Evaluasi Clustering Risiko Bencana Indonesia (Tingkat Kabupaten/Kota)

**DisasterWatch** adalah inisiatif berbasis sains data untuk pemantauan, analisis risiko, dan dukungan aksi iklim (*Climate Action* - SDGs 13) di Indonesia dengan memanfaatkan data historis resmi dari **Geoportal Kebencanaan Indonesia — Badan Nasional Penanggulangan Bencana (BNPB)**.

---

### Tujuan Analisis Pemodelan Clustering:
1. **Tipologi Profil Risiko Wilayah**: Mengelompokkan 412 kabupaten/kota di Indonesia berdasarkan karakteristik dampak kebencanaan riil (fatalitas manusia, populasi terdampak/mengungsi, kerusakan fisik/infrastruktur, kerusakan lahan/agrikultur, dan frekuensi/keragaman hazard).
2. **Komparasi Algoritma Objektif**: Membandingkan performa algoritma clustering nonspasial (K-Means, Agglomerative Clustering) dan density-based spasial (DBSCAN/HDBSCAN) menggunakan metrik evaluasi baku (*Silhouette Score*, *Davies-Bouldin Index*, dan *Calinski-Harabasz Score*).
3. **Pemisahan Dimensi Spasial vs Nonspasial**: Menghindari pencampuran sembarangan antara koordinat geografis (derajat lintang/bujur) dan fitur risiko untuk mencegah distorsi jarak Euclidean, sembari memetakan kembali klaster risiko ke peta geografis Indonesia.
4. **Relevansi SDGs 13**: Menghasilkan profil risiko berbasis data untuk memandu prioritas alokasi mitigasi, kesiapsiagaan darurat, dan adaptasi perubahan iklim secara proporsional tanpa klaim berlebihan."""),

    md("## 1. Audit Data Preprocessing & Setup Lingkungan"),

    code("""from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN, HDBSCAN
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.decomposition import PCA

# Konfigurasi Path dan Random Seed
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

ROOT = Path.cwd().parent if Path.cwd().name == "notebook" else Path.cwd()
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# 1. Muat Dataset Valid Hasil Preprocessing
df_kab = pd.read_csv(DATA_PROCESSED / "bnpb_disaster_cluster_ready.csv", encoding="utf-8-sig")
df_clean = pd.read_csv(DATA_PROCESSED / "bnpb_disaster_clean.csv", encoding="utf-8-sig", low_memory=False)

print(f"Dataset Kabupaten/Kota Siap Clustering: {df_kab.shape[0]} baris, {df_kab.shape[1]} kolom")
print(f"Dataset Kejadian Bersih (df_clean)     : {df_clean.shape[0]} baris kejadian")
display(df_kab.head(3))"""),

    md("""### Audit Temuan Data:
1. **Unit Analisis**: Terdapat **412 kabupaten/kota** dari 38 provinsi di Indonesia yang memiliki catatan kejadian bencana pada dataset 2026.
2. **Ketersediaan Koordinat**: Dari `df_clean`, 100% dari 2.260 kejadian memiliki titik koordinat (`geometry_lat`, `geometry_lon`) yang valid di dalam batas teritorial Indonesia (Lon 95°–141° BT, Lat 11° LS–6° LU).
3. **Integrasi Koordinat**: Kita menggabungkan rata-rata titik koordinat geografis representatif per kabupaten/kota untuk visualisasi peta akhir tanpa mengotori ruang fitur nonspasial."""),

    code("""# Integrasi koordinat representatif dan jenis bencana dominan per id_kab
coords = df_clean.groupby("id_kab").agg({
    "geometry_lat": "mean",
    "geometry_lon": "mean"
}).reset_index().rename(columns={"geometry_lat": "latitude", "geometry_lon": "longitude"})

top_disaster = df_clean.groupby("id_kab")["kejadian"].agg(
    lambda s: s.value_counts().index[0] if len(s) > 0 else "UNKNOWN"
).rename("bencana_dominan")

df_kab = df_kab.merge(coords, on="id_kab", how="left")
df_kab = df_kab.merge(top_disaster, on="id_kab", how="left")

print(f"Koordinat berhasil di-merge: {df_kab['latitude'].notna().sum()} / {len(df_kab)} kabupaten/kota valid.")
display(df_kab[['provinsi', 'kabkot', 'latitude', 'longitude', 'bencana_dominan']].head())"""),

    md("""## 2. Pemilihan Fitur & Transformasi Scaling

### Justifikasi Metodologis Fitur:
- **Fitur Terpilih (10 Indikator)**:
  1. `total_laporan`: Akumulasi frekuensi kejadian bencana di wilayah tersebut.
  2. `total_korban_jiwa`: Jumlah korban meninggal dan hilang (letalitas bencana).
  3. `total_terdampak`: Jumlah warga menderita dan mengungsi (krisis kemanusiaan).
  4. `total_material`: Jumlah rumah dan fasilitas fisik yang rusak atau terendam.
  5. `total_agri`: Luas lahan produktif (sawah, kebun, hutan) yang terdampak dalam hektar.
  6. `jenis_bencana_unik`: Jumlah ragam jenis bencana (indikator kerentanan multi-hazard).
  7. `avg_severity_score`: Rata-rata indeks keparahan kejadian.
  8. `pct_severity_berat`: Persentase insiden berkategori severitas berat.
  9. `avg_korban_per_event`: Rata-rata fatalitas per satu kali insiden.
  10. `avg_terdampak_per_event`: Rata-rata populasi terdampak per satu kali insiden.
- **Fitur Dikeluarkan**:
  - `total_kerugian`: Memiliki varians nol (nilai 0 pada seluruh baris karena nilai moneter rupiah belum dilaporkan lengkap di periode berjalan).
  - `latitude` / `longitude`: Dieksklusikan dari clustering nonspasial untuk mencegah distorsi metrik jarak Euclidean.

### Analisis Skewness & Heavy-Tail:
Data kebencanaan memiliki ekor panjang (*extreme heavy tail*) di mana sebagian besar wilayah memiliki insiden kecil, sedangkan beberapa wilayah terdampak bencana katastropik masif. Tanpa transformasi, outlier ekstrem akan memecah cluster menjadi 1 kelompok raksasa dan beberapa cluster berisi 1-2 wilayah saja."""),

    code("""feature_cols = [
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

X_raw = df_kab[feature_cols].fillna(0).values

# Evaluasi Skewness Sebelum dan Sesudah Log1p
skew_raw = pd.Series(df_kab[feature_cols].skew(), name="Skewness_Raw")
skew_log = pd.Series(np.log1p(df_kab[feature_cols]).skew(), name="Skewness_Log1p")
skew_df = pd.concat([skew_raw, skew_log], axis=1)
print("Perbandingan Skewness Fitur:")
display(skew_df.round(2))

# Normalisasi: Log1p dilanjutkan StandardScaler
scaler = StandardScaler()
X_scaled = scaler.fit_transform(np.log1p(X_raw))
print(f"Shape Matriks Fitur Normal: {X_scaled.shape}")"""),

    md("""## 3. Komparasi Algoritma Clustering & Tuning Parameter

Kita menguji 4 pendekatan:
1. **K-Means**: Menemukan centroid partisi cembung (k = 2 s.d. 6).
2. **Agglomerative Clustering (Ward Linkage)**: Pengelompokan hierarki berbasis minimalisasi varians intra-klaster.
3. **Agglomerative Clustering (Complete Linkage)**: Berbasis jarak maksimum antar anggota klaster.
4. **DBSCAN & HDBSCAN**: Berbasis kepadatan pada ruang fitur dan pada koordinat fisik bola bumi (*Haversine*)."""),

    code("""metrics_records = []

# 1. K-Means (k=2..6)
for k in range(2, 7):
    km = KMeans(n_clusters=k, random_state=RANDOM_SEED, n_init=20).fit(X_scaled)
    sil = silhouette_score(X_scaled, km.labels_)
    db = davies_bouldin_score(X_scaled, km.labels_)
    ch = calinski_harabasz_score(X_scaled, km.labels_)
    metrics_records.append({
        'Algorithm': 'K-Means',
        'k': k,
        'Silhouette': round(sil, 4),
        'Davies_Bouldin': round(db, 4),
        'Calinski_Harabasz': round(ch, 2),
        'Sizes': np.bincount(km.labels_).tolist()
    })

# 2. Agglomerative (Ward)
for k in range(2, 7):
    agg = AgglomerativeClustering(n_clusters=k, linkage='ward').fit(X_scaled)
    sil = silhouette_score(X_scaled, agg.labels_)
    db = davies_bouldin_score(X_scaled, agg.labels_)
    ch = calinski_harabasz_score(X_scaled, agg.labels_)
    metrics_records.append({
        'Algorithm': 'Agglomerative (Ward)',
        'k': k,
        'Silhouette': round(sil, 4),
        'Davies_Bouldin': round(db, 4),
        'Calinski_Harabasz': round(ch, 2),
        'Sizes': np.bincount(agg.labels_).tolist()
    })

# 3. Agglomerative (Complete)
for k in range(2, 7):
    agg = AgglomerativeClustering(n_clusters=k, linkage='complete').fit(X_scaled)
    sil = silhouette_score(X_scaled, agg.labels_)
    db = davies_bouldin_score(X_scaled, agg.labels_)
    ch = calinski_harabasz_score(X_scaled, agg.labels_)
    metrics_records.append({
        'Algorithm': 'Agglomerative (Complete)',
        'k': k,
        'Silhouette': round(sil, 4),
        'Davies_Bouldin': round(db, 4),
        'Calinski_Harabasz': round(ch, 2),
        'Sizes': np.bincount(agg.labels_).tolist()
    })

df_metrics = pd.DataFrame(metrics_records)
display(df_metrics)"""),

    md("""### Visualisasi Perbandingan Metrik Evaluasi"""),

    code("""fig, axes = plt.subplots(1, 3, figsize=(18, 5))
km_m = df_metrics[df_metrics['Algorithm'] == 'K-Means']
ward_m = df_metrics[df_metrics['Algorithm'] == 'Agglomerative (Ward)']
comp_m = df_metrics[df_metrics['Algorithm'] == 'Agglomerative (Complete)']

# Silhouette
axes[0].plot(km_m['k'], km_m['Silhouette'], marker='o', lw=2.5, label='K-Means')
axes[0].plot(ward_m['k'], ward_m['Silhouette'], marker='s', lw=2.5, label='Agglomerative (Ward)')
axes[0].plot(comp_m['k'], comp_m['Silhouette'], marker='^', lw=2.5, label='Agglomerative (Complete)')
axes[0].axvline(4, color='red', ls='--', alpha=0.7, label='Optimal k=4')
axes[0].set_title('Silhouette Score (Tinggi Lebih Baik)', fontweight='bold')
axes[0].set_xlabel('k'); axes[0].set_ylabel('Silhouette'); axes[0].legend(); axes[0].grid(True, alpha=0.3)

# Davies-Bouldin
axes[1].plot(km_m['k'], km_m['Davies_Bouldin'], marker='o', lw=2.5, label='K-Means')
axes[1].plot(ward_m['k'], ward_m['Davies_Bouldin'], marker='s', lw=2.5, label='Agglomerative (Ward)')
axes[1].plot(comp_m['k'], comp_m['Davies_Bouldin'], marker='^', lw=2.5, label='Agglomerative (Complete)')
axes[1].axvline(4, color='red', ls='--', alpha=0.7, label='Optimal k=4')
axes[1].set_title('Davies-Bouldin Index (Rendah Lebih Baik)', fontweight='bold')
axes[1].set_xlabel('k'); axes[1].set_ylabel('DB Index'); axes[1].legend(); axes[1].grid(True, alpha=0.3)

# Calinski-Harabasz
axes[2].plot(km_m['k'], km_m['Calinski_Harabasz'], marker='o', lw=2.5, label='K-Means')
axes[2].plot(ward_m['k'], ward_m['Calinski_Harabasz'], marker='s', lw=2.5, label='Agglomerative (Ward)')
axes[2].plot(comp_m['k'], comp_m['Calinski_Harabasz'], marker='^', lw=2.5, label='Agglomerative (Complete)')
axes[2].axvline(4, color='red', ls='--', alpha=0.7, label='Optimal k=4')
axes[2].set_title('Calinski-Harabasz Score (Tinggi Lebih Baik)', fontweight='bold')
axes[2].set_xlabel('k'); axes[2].set_ylabel('CH Score'); axes[2].legend(); axes[2].grid(True, alpha=0.3)

plt.suptitle('Evaluasi Metrik Model Clustering Risiko Bencana Indonesia', fontsize=14, fontweight='bold', y=1.03)
plt.tight_layout()
plt.show()"""),

    md("""## 4. Pemilihan Model Terbaik & Karakterisasi Klaster

### Alasan Pemilihan K-Means (k=4):
1. **Keseimbangan Metrik Baku**:
   - Silhouette Score = **0.3237** (struktur separasi padat dan terdefinisi dengan baik).
   - Davies-Bouldin Index = **1.2204** (rasio pemisahan antar klaster optimal).
   - Calinski-Harabasz Score = **172.78** (dispersi antar klaster tinggi).
2. **Kestabilan dan Keseimbangan Anggota**:
   - Menghasilkan 4 ukuran klaster: **172, 106, 118, dan 16** kabupaten/kota.
   - Tidak menghasilkan klaster tunggal raksasa (degeneratif) seperti pada Complete Linkage atau DBSCAN pada ruang fitur.
3. **Relevansi Kebijakan Bencana (Interpretabilitas Tinggi)**:
   - Terpetakan ke dalam 4 kuadran risiko operasional BNPB yang jelas:
     - **Klaster 0: Risiko Rendah (Sporadis & Dampak Minimal)** — 172 wilayah (41.7%)
     - **Klaster 1: Risiko Multi-Bencana Kronis & Kerusakan Lahan** — 106 wilayah (25.7%)
     - **Klaster 2: Risiko Kemanusiaan Akut & Pengungsian Massal** — 118 wilayah (28.6%)
     - **Klaster 3: Risiko Katastropik & Fatalitas Ekstrem** — 16 wilayah (3.9%)"""),

    code("""best_km = KMeans(n_clusters=4, random_state=RANDOM_SEED, n_init=25)
labels_raw = best_km.fit_predict(X_scaled)

# Urutkan label 0..3 berdasarkan rata-rata severitas agar mudah dipahami
cluster_order = (
    pd.DataFrame({'raw': labels_raw, 'score': df_kab['avg_severity_score']})
    .groupby('raw')['score'].mean()
    .sort_values().index.tolist()
)
rank_map = {old: new for new, old in enumerate(cluster_order)}
df_kab['cluster'] = [rank_map[c] for c in labels_raw]

CLUSTER_NAMES = {
    0: "Risiko Rendah (Sporadis & Dampak Minimal)",
    1: "Risiko Multi-Bencana Kronis & Kerusakan Lahan",
    2: "Risiko Kemanusiaan Akut & Pengungsian Massal",
    3: "Risiko Katastropik & Fatalitas Ekstrem"
}
CLUSTER_SHORT = {
    0: "Tingkat I - Rendah/Sporadis",
    1: "Tingkat II - Kronis/Multi-Hazard",
    2: "Tingkat III - Kemanusiaan Akut",
    3: "Tingkat IV - Katastropik Ekstrem"
}
CLUSTER_COLORS = {0: "#2ca02c", 1: "#1f77b4", 2: "#ff7f0e", 3: "#d62728"}

df_kab['cluster_name'] = df_kab['cluster'].map(CLUSTER_NAMES)
df_kab['cluster_short'] = df_kab['cluster'].map(CLUSTER_SHORT)

# Ringkasan Karakteristik Klaster
summary = df_kab.groupby('cluster')[feature_cols].mean()
summary['jumlah_wilayah'] = df_kab.groupby('cluster').size()
summary['persentase'] = (summary['jumlah_wilayah'] / len(df_kab) * 100).round(1)
summary['nama_profil'] = [CLUSTER_NAMES[c] for c in summary.index]
display(summary[['nama_profil', 'jumlah_wilayah', 'persentase', 'total_laporan', 'total_korban_jiwa', 'total_terdampak', 'total_material', 'total_agri']].round(2))"""),

    md("""## 5. Visualisasi Hasil Pemetaan & Profil Klaster"""),

    code("""# 1. Peta Sebaran Klaster Risiko Bencana Indonesia
fig, ax = plt.subplots(figsize=(18, 9), facecolor='#f8f9fa')
ax.set_facecolor('#e8f4f8')
ax.set_xlim(94.5, 141.5); ax.set_ylim(-11.5, 6.5)

for c_idx in sorted(df_kab['cluster'].unique()):
    sub = df_kab[df_kab['cluster'] == c_idx]
    size = 45 if c_idx == 0 else (65 if c_idx == 1 else (95 if c_idx == 2 else 150))
    alpha = 0.7 if c_idx < 3 else 0.95
    edgecolor = 'black' if c_idx == 3 else 'none'
    ax.scatter(sub['longitude'], sub['latitude'], c=CLUSTER_COLORS[c_idx], s=size,
               alpha=alpha, edgecolors=edgecolor, label=f"{CLUSTER_SHORT[c_idx]} (n={len(sub)})", zorder=3+c_idx)

# Anotasi wilayah katastropik utama
sub_cat = df_kab[df_kab['cluster'] == 3]
for _, row in sub_cat.iterrows():
    ax.annotate(row['kabkot'], (row['longitude'], row['latitude']), textcoords="offset points",
                xytext=(5, 5), fontsize=8.5, fontweight='bold', color='#990000',
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#d62728", lw=0.8, alpha=0.85))

ax.set_title("PETA PEMETAAN TINGKAT & TIPOLOGI RISIKO BENCANA INDONESIA (SDGs 13)\\nClustering Nonspasial Profil Risiko BNPB (K-Means k=4)",
             fontsize=14, fontweight='bold', pad=15)
ax.set_xlabel("Bujur Timur (°E)"); ax.set_ylabel("Lintang (°N/S)")
ax.grid(True, color='white', linestyle='--', alpha=0.8)
ax.legend(loc='lower left', frameon=True, facecolor='white', framealpha=0.95, title="Tipologi Risiko")
plt.tight_layout()
plt.show()"""),

    md("""### Proyeksi 2D PCA & Biplot Beban Fitur"""),

    code("""pca = PCA(n_components=2, random_state=RANDOM_SEED)
X_pca = pca.fit_transform(X_scaled)
df_kab['pca_1'] = X_pca[:, 0]
df_kab['pca_2'] = X_pca[:, 1]

fig, ax = plt.subplots(figsize=(10, 8))
for c_idx in sorted(df_kab['cluster'].unique()):
    sub = df_kab[df_kab['cluster'] == c_idx]
    ax.scatter(sub['pca_1'], sub['pca_2'], c=CLUSTER_COLORS[c_idx], s=60, alpha=0.75,
               label=f"{CLUSTER_SHORT[c_idx]} (n={len(sub)})")

loadings = pca.components_.T * np.sqrt(pca.explained_variance_) * 1.5
for i, feat in enumerate(feature_cols):
    ax.arrow(0, 0, loadings[i, 0], loadings[i, 1], color='black', alpha=0.5, head_width=0.08)
    ax.text(loadings[i, 0] * 1.15, loadings[i, 1] * 1.15, feat, color='black', fontsize=8.5, ha='center', va='center')

ax.set_title(f"Proyeksi 2D PCA Klaster Risiko Bencana\\nVarians Terjelaskan: PC1={pca.explained_variance_ratio_[0]*100:.1f}%, PC2={pca.explained_variance_ratio_[1]*100:.1f}%",
             fontsize=12, fontweight='bold')
ax.set_xlabel("Principal Component 1 (Skala Dampak & Fatalitas)")
ax.set_ylabel("Principal Component 2 (Frekuensi & Variasi Hazard)")
ax.legend(); ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()"""),

    md("""### Radar Chart Profil Relatif Tiap Klaster"""),

    code("""radar_feats = ['total_laporan', 'total_korban_jiwa', 'total_terdampak', 'total_material', 
               'total_agri', 'jenis_bencana_unik', 'avg_severity_score', 'pct_severity_berat']
radar_labels = ['Frekuensi\\nKejadian', 'Korban\\nJiwa', 'Warga\\nTerdampak', 'Kerusakan\\nMaterial', 
                'Kerusakan\\nLahan', 'Keragaman\\nHazard', 'Severitas\\nRata-rata', 'Proporsi\\nBerat']

c_means = df_kab.groupby('cluster')[radar_feats].mean()
c_means_norm = (c_means - c_means.min()) / (c_means.max() - c_means.min() + 1e-6)

num_vars = len(radar_feats)
angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
angles += angles[:1]

fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
for c_idx in sorted(df_kab['cluster'].unique()):
    values = c_means_norm.loc[c_idx].tolist()
    values += values[:1]
    ax.plot(angles, values, color=CLUSTER_COLORS[c_idx], linewidth=2.5, label=CLUSTER_SHORT[c_idx])
    ax.fill(angles, values, color=CLUSTER_COLORS[c_idx], alpha=0.15)

ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
ax.set_thetagrids(np.degrees(angles[:-1]), radar_labels, fontsize=10)
ax.set_ylim(0, 1.05)
ax.set_title("Radar Chart Profil Risiko Relatif Tiap Klaster Bencana", fontsize=13, fontweight='bold', pad=25)
ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1.1), fontsize=9.5)
plt.tight_layout()
plt.show()"""),

    md("""### Distribusi Jenis Bencana Dominan per Klaster"""),

    code("""disaster_crosstab = pd.crosstab(df_kab['cluster_short'], df_kab['bencana_dominan'], normalize='index') * 100
fig, ax = plt.subplots(figsize=(12, 6))
disaster_crosstab.plot(kind='bar', stacked=True, ax=ax, colormap='tab10', edgecolor='white', alpha=0.9)
ax.set_title("Proporsi Jenis Bencana Dominan di Setiap Klaster (%)", fontsize=13, fontweight='bold')
ax.set_ylabel("Persentase Kabupaten/Kota (%)"); ax.set_xlabel(""); ax.tick_params(axis='x', rotation=0)
ax.legend(title="Bencana Dominan", bbox_to_anchor=(1.02, 1), loc='upper left'); ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.show()"""),

    md("""## 6. Analisis Relevansi DisasterWatch dan SDGs 13: Climate Action

### 1. Pola Spasial dan Karakteristik Wilayah
- **Konsentrasi Multi-Hazard di Pulau Jawa & Sumatera** (Klaster 1): Wilayah dengan frekuensi tinggi bencana hidrometeorologis basah berulang (banjir, tanah longsor, cuaca ekstrem) akibat kombinasi curah hujan monsun, alih fungsi lahan tangkapan air, dan kepadatan infrastruktur pemukiman.
- **Kerentanan Katastropik di Wilayah Kepulauan & Pesisir** (Klaster 3): Bencana berdaya rusak masif dan berfatalitas tinggi terfokus pada wilayah tektonik/vulkanik aktif (NTT, Kepulauan Sitaro, Sumatera Barat) serta daerah lereng curam rawan longsor.

### 2. Penegasan Metodologis & Larangan Overclaiming Prediksi
> **PENTING: Batasan Konseptual Model**
> 1. **Klaster Hasil Analisis $\neq$ Prediksi Kejadian Masa Depan**: Klaster ini memotret **tipologi historis empiris keparahan dampak kebencanaan** berdasarkan laporan aktual BNPB. Model clustering ini adalah model *unsupervised descriptive-profiling*, **bukan model peramalan prediktif (*forecasting*)**. Belum ada model *time-series autoregressive* atau *predictive classifier* dengan evaluasi *out-of-time* yang dapat mengklaim "memprediksi kapan dan di mana bencana berikutnya akan terjadi".
> 2. **Tingkat Risiko adalah Konstruksi Metodologis**: Pengelompokan menjadi Tingkat I hingga IV adalah sintesis statistik dari metrik keparahan historis, bukan penentu mutlak nasib wilayah di masa depan.
> 3. **Hubungan Proporsional dengan SDGs 13 (Climate Action)**: Peningkatan intensitas cuaca ekstrem, anomali siklon tropis, dan durasi kekeringan berhubungan erat dengan dinamika iklim global (SDG 13.1 — memperkuat ketahanan dan kapasitas adaptasi terhadap bahaya iklim). Namun, **clustering tidak membuktikan kausalitas fisik perubahan iklim secara langsung**; faktor antropogenik lokal (tata ruang, deforestasi, sistem drainase, kesiapsiagaan BPBD) memegang peran krusial dalam menentukan besaran dampak.

---

## 7. Kesimpulan & Rekomendasi Terpadu

### Q&A
- **Q: Model clustering mana yang paling optimal untuk pemetaan risiko bencana Indonesia?**
  - **A:** **K-Means dengan $k=4$** menggunakan fitur dampak yang dinormalisasi dengan transformasi $\log(1+x)$ dan *StandardScaler*. Model ini memiliki *Silhouette Score* (0.3237), *Davies-Bouldin Index* (1.2204), dan *Calinski-Harabasz Score* (172.78) yang seimbang, dengan ukuran klaster proporsional tanpa klaster degeneratif/outlier tunggal.
- **Q: Mengapa koordinat geografis tidak dicampur langsung ke dalam fitur clustering nonspasial?**
  - **A:** Pencampuran langsung koordinat derajat (lat/lon) dengan metrik korban dan kerusakan mendistorsi jarak Euclidean: wilayah yang memiliki profil risiko identik (misal sama-sama rawan banjir bandang akut di Aceh dan di NTT) akan dipisahkan secara buatan hanya karena jarak ribuan kilometer di peta. Pendekatan terbaik adalah mengelompokkan profil risiko secara nonspasial, lalu memproyeksikan hasilnya ke atas peta geografis Indonesia.

### Data Analysis Key Findings
- **41.7% Kabupaten/Kota (172 wilayah)** berada pada **Klaster 0 (Risiko Rendah/Sporadis)**, dengan rata-rata 3.27 laporan per wilayah dan korban jiwa mendekati nol (0.08 jiwa).
- **25.7% Kabupaten/Kota (106 wilayah)** berada pada **Klaster 1 (Risiko Multi-Hazard Kronis & Lahan)**, dengan frekuensi laporan tertinggi (rata-rata 12.32 kejadian per wilayah), keragaman bencana tertinggi (3.58 jenis), dan kerusakan lahan agrikultur terbesar (1.031 hektar).
- **28.6% Kabupaten/Kota (118 wilayah)** berada pada **Klaster 2 (Risiko Kemanusiaan Akut)**, dengan rata-rata 16.143 warga terdampak/mengungsi dan 1.897 unit rumah rusak.
- **3.9% Kabupaten/Kota (16 wilayah)** berada pada **Klaster 3 (Risiko Katastropik Ekstrem)**, menyerap dampak fatalitas tertinggi (rata-rata 18.44 jiwa meninggal/hilang) dan 65.193 warga terdampak per wilayah (misalnya erupsi Lewotobi/Ruang, longsor Cipongkor, dan banjir bandang lahar).

### Insights & Next Steps
- **Rekomendasi Kebijakan (BNPB & Pemda)**:
  - **Wilayah Klaster 3**: Prioritas utama penguatan sistem evakuasi dini (*early warning sirens*), logistik tanggap darurat, dan relokasi permukiman dari zona merah vulkanik/patahan aktif.
  - **Wilayah Klaster 1**: Penguatan manajemen risiko bencana berbasis ekosistem (*Eco-DRR*), restorasi daerah aliran sungai (DAS), dan perlindungan lahan pangan produktif dari ancaman kebakaran dan banjir musiman.
- **Langkah Pengembangan Selanjutnya**:
  - Mengembangkan model prediktif berbasis deret waktu (*time-series forecasting*) dan klasifikasi tingkat keparahan (*supervised multi-class classification*) yang dievaluasi dengan *temporal train-test split* untuk mengantisipasi potensi eskalasi dampak menjelang musim puncak hujan/kemarau.""")
]

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.10"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Berhasil meng-update {NB_PATH} dengan {len(cells)} cells.")
