# DisasterWatch SDGs 13: Laporan Komprehensif Pemodelan & Evaluasi Clustering Risiko Bencana Indonesia

**Proyek**: DisasterWatch — Sistem Prediksi dan Pemetaan Risiko Bencana Indonesia  
**Topik**: Tahap Modeling dan Evaluasi Clustering Risiko Bencana Tingkat Kabupaten/Kota  
**Sumber Data**: Geoportal Data Bencana Indonesia — Badan Nasional Penanggulangan Bencana (BNPB) (<https://gis.bnpb.go.id>)  
**Fokus SDGs**: Goal 13 — *Climate Action* (Aksi Iklim)  

---

## 1. Audit Karakteristik Data

### 1.1 Struktur dan Provenance Data
Berdasarkan pembaharuan repositori dan eksekusi pipeline (*preprocessing* -> *feature engineering* -> *modelling*), dataset yang digunakan sebagai input pemodelan adalah hasil pemrosesan lengkap data historis resmi BNPB:
- **`bnpb_disaster_clean.csv`**: 44.280 laporan kejadian bencana historis nasional yang telah dibersihkan.
- **`bnpb_disaster_cluster_ready.csv`**: 1.041 entri agregat wilayah kabupaten/kota dengan 25 kolom (fitur akumulasi dampak dan skala).
- **`bnpb_province_clusters.csv`**: Agregat klaster regional provinsi.
- **`bnpb_aggregate_*.csv`**: Agregasi multidimensi temporal (harian, bulanan) dan spasial (provinsi, jenis bencana).

### 1.2 Cakupan Geografis, Temporal, dan Sebaran Data
- **Cakupan Wilayah**: **1.041 kabupaten/kota/wilayah administratif** di seluruh Indonesia dengan 100% titik koordinat representatif valid di dalam teritorial Indonesia.
- **Fitur Nonspasial**: Pemisahan dimensi spasial dan nonspasial dipertahankan secara ketat untuk mencegah distorsi jarak Euclidean, di mana koordinat geografis hanya digunakan untuk pemetaan visual dan *Spatial DBSCAN*, bukan untuk pengelompokan profil keparahan risiko.

---

## 2. Metodologi Clustering: Fitur, Transformasi & Algoritma

### 2.1 Pemilihan Fitur (10 Indikator Utama)
1. `total_laporan`: Akumulasi frekuensi kejadian bencana.
2. `total_korban_jiwa`: Korban meninggal dan hilang (letalitas bencana).
3. `total_terdampak`: Warga menderita dan mengungsi (krisis kemanusiaan).
4. `total_material`: Rumah dan fasilitas fisik rusak/terendam.
5. `total_agri`: Luas lahan produktif terdampak (hektar).
6. `jenis_bencana_unik`: Keragaman hazard (indikator multi-hazard).
7. `avg_severity_score`: Rata-rata skor severitas kejadian.
8. `pct_severity_berat`: Persentase insiden berkategori berat.
9. `avg_korban_per_event`: Letalitas rata-rata per kejadian.
10. `avg_terdampak_per_event`: Dampak populasi rata-rata per kejadian.

*Catatan*: `total_kerugian` dieksklusikan karena varians nol (belum dilaporkan merata).

### 2.2 Penanganan Heavy-Tail Skewness ($\log(1+x)$)
Transformasi logaritmik berhasil mereduksi kemencengan data ekstrem secara signifikan:
- `total_laporan`: Skewness turun dari **12.89** menjadi **0.18**
- `total_korban_jiwa`: Skewness turun dari **27.98** menjadi **1.11**
- `total_terdampak`: Skewness turun dari **5.03** menjadi **-0.95**
- `total_material`: Skewness turun dari **5.72** menjadi **-0.81**
- `total_agri`: Skewness turun dari **26.37** menjadi **-0.13**
- `avg_severity_score`: Skewness turun dari **5.31** menjadi **0.71**
- `avg_korban_per_event`: Skewness turun dari **12.23** menjadi **3.14**

Setelah normalisasi logaritmik, data distandarisasi menggunakan `StandardScaler`.

---

## 3. Hasil Evaluasi & Komparasi Algoritma

Tabel komparasi metrik evaluasi clustering pada seluruh model yang diuji:

| Algoritma | Parameter ($k$) | Silhouette Score (↑) | Davies-Bouldin Index (↓) | Calinski-Harabasz Score (↑) | Distribusi Ukuran Klaster | Karakteristik / Evaluasi |
|---|---|:---:|:---:|:---:|:---:|---|
| **K-Means** | **$k = 4$** | **0.2506** | **1.3139** | **364.31** | **[77, 171, 413, 380]** | **Terpilih (Optimal, Seimbang & Representatif)** |
| K-Means | $k = 2$ | 0.2938 | 1.3273 | 452.22 | [324, 717] | Terlalu makro (hanya membagi 2 kutub) |
| K-Means | $k = 3$ | 0.2329 | 1.4682 | 387.72 | [427, 446, 168] | Metrik pemisahan lebih rendah |
| K-Means | $k = 5$ | 0.2223 | 1.3788 | 337.12 | [330, 62, 154, 281, 214] | Penurunan Silhouette score |
| K-Means | $k = 6$ | 0.2050 | 1.3326 | 313.36 | [199, 193, 146, 235, 62, 206] | Klaster mulai terfragmentasi |
| Agglomerative (Ward) | $k = 2$ | 0.3570 | 1.1190 | 379.40 | [875, 166] | Terlalu timpang (imbalanced) |
| Agglomerative (Ward) | $k = 3$ | 0.2020 | 1.5868 | 347.66 | [395, 166, 480] | Metrik lebih rendah dari K-Means |
| Agglomerative (Ward) | $k = 4$ | 0.2047 | 1.4413 | 311.38 | [480, 166, 331, 64] | Metrik lebih rendah dari K-Means |
| Agglomerative (Complete) | $k = 2$ | 0.4209 | 0.9758 | 78.61 | [1019, 22] | **Degeneratif**: 1.019 sampel menumpuk di 1 klaster |
| Agglomerative (Complete) | $k = 3$ | 0.3462 | 0.9787 | 244.17 | [888, 22, 131] | Penumpukan sampel dominan |
| Agglomerative (Complete) | $k = 4$ | 0.2427 | 1.4772 | 199.73 | [823, 65, 131, 22] | Klaster sangat timpang |

### Alasan Pemilihan Model Terbaik: K-Means ($k = 4$)
1. **Struktur Seimbang**: Menghasilkan 4 klaster yang proporsional ([77, 171, 413, 380]) tanpa menyisakan penumpukan ekstrem seperti pada Complete Linkage (823 vs 22).
2. **Kerapatan dan Separasi**: Memiliki nilai Calinski-Harabasz yang tinggi (**364.31**) dan Davies-Bouldin Index yang kompetitif (**1.3139**).
3. **Relevansi Operasional**: Membagi risiko wilayah ke dalam 4 kuadran kebijakan penanggulangan bencana yang terdefinisi dengan sangat jelas.

---

## 4. Karakteristik & Profil Tipologi Klaster Risiko

Ringkasan kuantitatif karakteristik rata-rata dari keempat klaster risiko yang terbentuk:

| Klaster | Nama Profil Tipologi | Jumlah Wilayah (%) | Rata-rata Laporan | Korban Jiwa (Jiwa) | Warga Terdampak (Jiwa) | Kerusakan Material (Unit) | Kerusakan Lahan (Ha) |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Klaster 0** | **Risiko Rendah (Sporadis & Dampak Minimal)** | 171 (16,4%) | 8,56 | 1,29 | 365,72 | 96,10 | 139,25 |
| **Klaster 1** | **Risiko Multi-Bencana Kronis & Kerusakan Lahan** | 413 (39,7%) | **89,59** | 9,20 | 144.023,04 | **19.599,64** | **8.551,51** |
| **Klaster 2** | **Risiko Kemanusiaan Akut & Pengungsian Massal** | 380 (36,5%) | 11,07 | 1,03 | 20.436,45 | 2.915,86 | 449,92 |
| **Klaster 3** | **Risiko Katastropik & Fatalitas Ekstrem** | 77 (7,4%) | 20,91 | **117,88** | **144.561,87** | 14.373,42 | 2.251,54 |

### Uraian Detail Profil:
- **Klaster 0 — Risiko Rendah (Sporadis & Dampak Minimal)**:
  - Karakteristik: Bencana jarang terjadi dengan dampak kerusakan dan korban minimal.
  - Rekomendasi: Pemeliharaan proteksi lingkungan dan pemantauan preventif berkala.
- **Klaster 1 — Risiko Multi-Bencana Kronis & Kerusakan Lahan**:
  - Karakteristik: Frekuensi insiden tertinggi (**rata-rata 89,59 kali**) dengan dampak kerusakan lahan produktif dan aset material fisik yang sangat masif (**>8.500 ha lahan dan >19.500 unit fisik rusak**). Khas bencana hidrometeorologi musiman (banjir, cuaca ekstrem, karhutla).
  - Rekomendasi: Mitigasi struktural makro (normalisasi DAS, tata ruang wilayah tangkapan air, tata kelola lahan gambut).
- **Klaster 2 — Risiko Kemanusiaan Akut & Pengungsian Massal**:
  - Karakteristik: Frekuensi insiden moderat, namun setiap insiden menimbulkan dampak pengungsian warga yang signifikan (rata-rata >20 ribu jiwa).
  - Rekomendasi: Kesiapsiagaan logistik evakuasi, shelter darurat ramah kelompok rentan, dan simulasi tanggap bencana berkala.
- **Klaster 3 — Risiko Katastropik & Fatalitas Ekstrem**:
  - Karakteristik: Kejadian sporadis dengan daya rusak sangat mematikan (**rata-rata fatalitas 117,88 korban jiwa per wilayah** dan kerugian material parah). Merepresentasikan bencana geologis/vulkanik dan tanah longsor curam.
  - Rekomendasi: Zonasi ketat Kawasan Rawan Bencana (KRB), audit struktur tahan gempa fasilitas umum, dan pemasangan EWS berbasis sensor IoT.

---

## 5. Visualisasi Hasil Pemetaan
File visualisasi berkualitas tinggi tersimpan pada folder `reports/figures/`:
1. `clustering_metrics_evaluation.png`: Evaluasi multi-metrik algoritma.
2. `map_clustering_indonesia.png`: Peta sebaran spasial klaster risiko di seluruh Indonesia.
3. `pca_clusters_projection.png`: Proyeksi 2D PCA pemisahan klaster.
4. `cluster_risk_profiles_radar.png`: Radar chart perbandingan multi-dimensi indikator dampak.
5. `cluster_feature_distribution.png`: Diagram batang komparasi rata-rata indikator per klaster.
6. `cluster_disaster_type_breakdown.png`: Proporsi jenis bencana dominan per klaster.
7. `spatial_dbscan_hotspots_map.png`: Analisis hotspot kepadatan geografis spasial.
