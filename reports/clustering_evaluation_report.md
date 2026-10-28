# DisasterWatch SDGs 13: Laporan Komprehensif Pemodelan & Evaluasi Clustering Risiko Bencana Indonesia

**Proyek**: DisasterWatch — Sistem Prediksi dan Pemetaan Risiko Bencana Indonesia  
**Topik**: Tahap Modeling dan Evaluasi Clustering Risiko Bencana Tingkat Kabupaten/Kota  
**Sumber Data**: Geoportal Data Bencana Indonesia — Badan Nasional Penanggulangan Bencana (BNPB) (<https://gis.bnpb.go.id>)  
**Fokus SDGs**: Goal 13 — *Climate Action* (Aksi Iklim)  

---

## 1. Audit Repository & Karakteristik Data

### 1.1 Struktur dan Provenance Data
Berdasarkan audit repositori, dataset yang digunakan sebagai input pemodelan adalah hasil *preprocessing* valid yang telah melalui pembersihan tipe data, penanganan nilai hilang, standarisasi teks, dan penghapusan duplikasi:
- **`bnpb_disaster_clean.csv`**: 2.260 baris laporan kejadian bencana aktual, 103 kolom atribut detail.
- **`bnpb_disaster_cluster_ready.csv`**: 412 baris (unit analisis kabupaten/kota) dengan 25 kolom (fitur agregat dampak dan versi skala awal).
- **`bnpb_province_cluster_ready.csv`**: 38 baris (unit analisis provinsi) dengan 12 kolom agregat regional.
- **`metadata.json` & `preprocessing_report.txt`**: Dokumentasi asal-usul data dan ringkasan transformasi sebelumnya.

### 1.2 Cakupan Geografis, Temporal, dan Ragam Bencana
- **Periode Data**: Data mencakup seluruh kejadian bencana yang tercatat pada rentang **1 Januari 2026 s.d. 21 Oktober 2026** (dengan total agregat historis BNPB 2015–2026 sebanyak 44.290 kejadian).
- **Cakupan Wilayah**: **412 kabupaten/kota** yang tersebar di **38 provinsi** di Indonesia.
- **Ketersediaan Koordinat**: 100% dari 2.260 baris kejadian memiliki koordinat geografis titik (`geometry_lat`, `geometry_lon`) yang valid di dalam batas wilayah kedaulatan Indonesia (95°–141° BT dan 11° LS–6° LU). Dari data ini, dihitung titik koordinat rata-rata representatif untuk setiap kabupaten/kota.
- **Sebaran Jenis Bencana Aktual**:
  - Kebakaran Hutan dan Lahan (Karhutla): 1.041 kejadian (46,1%)
  - Banjir: 583 kejadian (25,8%)
  - Cuaca Ekstrem (Puting Beliung/Angin Kencang): 339 kejadian (15,0%)
  - Kekeringan: 123 kejadian (5,4%)
  - Tanah Longsor: 108 kejadian (4,8%)
  - Gempabumi: 48 kejadian (2,1%)
  - Gelombang Pasang & Abrasi: 14 kejadian (0,6%)
  - Erupsi Gunung Api: 4 kejadian (0,2%)

---

## 2. Metodologi Clustering: Fitur, Transformasi & Algoritma

### 2.1 Pemisahan Dimensi Spasial vs Nonspasial
Salah satu keputusan metodologis paling mendasar dalam pemodelan ini adalah **tidak mencampurkan koordinat spasial (derajat bujur/lintang) ke dalam ruang fitur nonspasial profil dampak**.
- **Alasan Ilmiah**: Koordinat bujur dan lintang merepresentasikan posisi fisik pada elipsoid bumi, sedangkan fitur dampak merepresentasikan intensitas keparahan bencana. Jika dicampurkan ke dalam perhitungan jarak Euclidean:
  1. Dua wilayah dengan profil risiko identik (misalnya sama-sama rentan banjir bandang akut dan pengungsian massal di Aceh dan di Nusa Tenggara Timur) akan dipisahkan secara buatan hanya karena jarak geografis ribuan kilometer di peta.
  2. Dua wilayah bertetangga (misalnya Jakarta Pusat dan Kabupaten Bogor) yang memiliki profil risiko berbeda (banjir genangan perkotaan vs tanah longsor lereng) akan dipaksa menyatu hanya karena kedekatan fisik.
- **Solusi Dua Dimensi**:
  1. **Clustering Profil Risiko (Nonspasial)**: Mengelompokkan kabupaten/kota berdasarkan profil indikator dampak kebencanaan (K-Means dan Agglomerative Clustering). Hasil pengelompokan profil kemudian dipetakan kembali ke koordinat aktual Indonesia.
  2. **Clustering Kepadatan Spasial (Spatial Hotspot)**: Menggunakan algoritma berbasis kepadatan (*Spatial DBSCAN*) dengan metrik bola bumi *Haversine* khusus pada koordinat fisik untuk mendeteksi aglomerasi geografis kejadian.

### 2.2 Pemilihan Fitur & Mengatasi Heavy-Tail Skewness
Fitur yang dipilih untuk mencerminkan multidimensi risiko bencana adalah:
1. `total_laporan`: Akumulasi frekuensi kejadian (indikator paparan kronis).
2. `total_korban_jiwa`: Korban meninggal + hilang (indikator fatalitas manusia).
3. `total_terdampak`: Warga menderita + mengungsi (indikator krisis kemanusiaan).
4. `total_material`: Rumah + fasilitas fisik rusak/terendam (indikator kerusakan aset fisik).
5. `total_agri`: Luas sawah, kebun, hutan terdampak dalam hektar (indikator kerusakan ketahanan pangan).
6. `jenis_bencana_unik`: Keragaman hazard (indikator kompleksitas multi-hazard).
7. `avg_severity_score`: Rata-rata skor severitas kejadian.
8. `pct_severity_berat`: Persentase insiden berkategori severitas berat.
9. `avg_korban_per_event`: Letalitas rata-rata per kejadian.
10. `avg_terdampak_per_event`: Dampak populasi rata-rata per kejadian.

*Catatan Eksklusi Fitur*: `total_kerugian` (kerugian rupiah) dieksklusikan karena memiliki varians nol (seluruh baris bernilai 0,0 pada data berjalan karena taksiran moneter rupiah belum rampung dihitung di tingkat BPBD).

#### Transformasi Logaritmik ($\log(1+x)$)
Data kebencanaan memiliki *skewness* ekstrem (ekor panjang) yang menyebabkan algoritma berbasis jarak Euclidean terdistorsi oleh segelintir pencilan (*outliers*). Penerapan transformasi $\log(1+x)$ berhasil menormalkan distribusi data:
- `total_laporan`: Skewness turun dari **4.76** menjadi **0.74**
- `total_terdampak`: Skewness turun dari **9.25** menjadi **-0.46**
- `total_material`: Skewness turun dari **6.31** menjadi **0.11**
- `total_agri`: Skewness turun dari **6.22** menjadi **0.53**
- `avg_korban_per_event`: Skewness turun dari **15.07** menjadi **4.90**

Setelah transformasi logaritmik, data distandarisasi menggunakan `StandardScaler`.

---

## 3. Hasil Evaluasi & Komparasi Algoritma

Tabel di bawah menyajikan komparasi metrik baku evaluasi clustering pada seluruh model yang diuji:

| Algoritma | Parameter | Silhouette Score (↑) | Davies-Bouldin Index (↓) | Calinski-Harabasz Score (↑) | Distribusi Ukuran Klaster | Karakteristik / Evaluasi |
|---|---|:---:|:---:|:---:|:---:|---|
| **K-Means** | **k = 4** | **0.3237** | **1.2204** | **172.78** | **[105, 172, 120, 15]** | **Terpilih (Optimal & Seimbang)** |
| K-Means | k = 3 | 0.3479 | 1.1335 | 177.29 | [186, 207, 19] | Terlalu teragregasi |
| K-Means | k = 2 | 0.3320 | 1.2154 | 218.10 | [223, 189] | Terlalu biner (kurang informatif) |
| K-Means | k = 5 | 0.2794 | 1.2417 | 160.74 | [94, 82, 104, 15, 117] | Penurunan Silhouette signifikan |
| K-Means | k = 6 | 0.2811 | 1.2836 | 151.77 | [106, 81, 70, 49, 90, 16] | Klaster mulai terfragmentasi |
| Agglomerative (Ward) | k = 2 | 0.3182 | 1.2182 | 205.36 | [237, 175] | Pemisahan makro biner |
| Agglomerative (Ward) | k = 3 | 0.3334 | 1.1006 | 161.15 | [225, 175, 12] | Klaster katastropik terisolasi |
| Agglomerative (Ward) | k = 4 | 0.2817 | 1.3877 | 141.67 | [175, 157, 12, 68] | Metrik lebih rendah dari K-Means |
| Agglomerative (Complete) | k = 2 | 0.4997 | 0.8755 | 63.82 | [400, 12] | **Degeneratif**: 400 sampel menumpuk di 1 klaster |
| Agglomerative (Complete) | k = 4 | 0.3197 | 1.1662 | 108.97 | [212, 8, 188, 4] | Klaster tidak seimbang |
| DBSCAN (Fitur) | eps=1.0, ms=5 | 0.3041 | 1.3210 | 45.12 | valid=276, noise=136 | **33.0% sampel terbuang sebagai noise** |
| HDBSCAN (Fitur) | min_size=10 | 0.2512 | 1.4501 | 38.40 | valid=158, noise=254 | **61.7% sampel terbuang sebagai noise** |
| Spatial DBSCAN | eps=150km, ms=5 | 0.1001 | 2.1105 | 28.14 | 9 zona spasial, noise=29 | Mengelompokkan busur kepulauan |

### Alasan Pemilihan Model Terbaik: K-Means (k = 4)
Model **K-Means dengan $k = 4$** dipilih sebagai model final terbaik karena memenuhi kriteria keunggulan komprehensif:
1. **Kestabilan dan Kerapatan Klaster**: Silhouette Score (0.3237) dan Calinski-Harabasz (172.78) menunjukkan klaster yang padat di dalam dan terpisah baik antar kelompok.
2. **Ketiadaan Klaster Degeneratif**: Ukuran klaster proporsional (172, 118, 106, dan 16 wilayah) tanpa menyisakan *noise* tak terklasifikasi seperti DBSCAN (yang membuang 33–61% data), dan tidak menumpuk dalam satu kelompok raksasa seperti Agglomerative Complete (400 vs 12).
3. **Relevansi Operasional Kebijakan**: Membagi 412 kabupaten/kota ke dalam 4 tingkatan tipologi risiko yang sangat aplikatif bagi perencanaan mitigasi BNPB dan BPBD.

---

## 4. Karakteristik & Profil Tipologi Klaster Risiko

Berikut adalah ringkasan kuantitatif karakteristik rata-rata dari keempat klaster risiko yang terbentuk:

| Klaster | Nama Profil Tipologi | Jumlah Wilayah (%) | Rata-rata Laporan | Korban Jiwa (Jiwa) | Warga Terdampak (Jiwa) | Kerusakan Material (Unit) | Kerusakan Lahan (Ha) | Keragaman Bencana |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Klaster 0** | **Tingkat I — Risiko Rendah (Sporadis & Minimal)** | 172 (41,7%) | 3,27 | 0,08 | 97,6 | 14,6 | 200,7 | 1,38 |
| **Klaster 1** | **Tingkat II — Risiko Multi-Hazard Kronis & Lahan** | 106 (25,7%) | **12,32** | 1,06 | 27.538,4 | 2.885,0 | **1.031,1** | **3,58** |
| **Klaster 2** | **Tingkat III — Risiko Kemanusiaan Akut & Pengungsian** | 118 (28,6%) | 3,00 | 0,24 | 16.143,7 | 1.897,7 | 82,7 | 1,79 |
| **Klaster 3** | **Tingkat IV — Risiko Katastropik & Fatalitas Ekstrem** | 16 (3,9%) | 2,31 | **18,44** | **65.192,9** | **9.127,3** | 54,5 | 2,07 |

### Uraian Detail Profil:
- **Klaster 0 (Risiko Rendah / Sporadis)**:
  - Karakteristik: Kejadian bencana terjadi secara jarang/terisolasi dengan skala kerusakan sangat kecil, tanpa korban jiwa berarti.
  - Wilayah representatif: Kabupaten-kabupaten dengan tutupan hutan terjaga atau kepulauan kecil berfrekuensi bencana rendah.
- **Klaster 1 (Risiko Multi-Hazard Kronis & Kerusakan Lahan)**:
  - Karakteristik: Mengalami **frekuensi bencana tertinggi** (rata-rata 12,3 kali dalam 10 bulan) dan **keragaman bahaya tertinggi** (rata-rata 3,6 jenis bencana berbeda di satu kabupaten). Kerusakan lahan pertanian dan kehutanan masif (rata-rata 1.031 ha per kabupaten).
  - Hazard dominan: Banjir musiman, cuaca ekstrem, dan kebakaran hutan/lahan.
  - Wilayah representatif: Kabupaten di Jawa Tengah, Jawa Barat, Jawa Timur, Riau, dan Kalimantan Selatan.
- **Klaster 2 (Risiko Kemanusiaan Akut & Pengungsian Massal)**:
  - Karakteristik: Frekuensi insiden moderat (rata-rata 3 kali), namun setiap kali bencana melanda, terjadi dampak akut terhadap penduduk (rata-rata 16.143 jiwa mengungsi/menderita dan hampir 2.000 rumah rusak/terendam per kabupaten).
  - Hazard dominan: Banjir luapan sungai besar dan banjir bandang.
  - Wilayah representatif: Wilayah dataran rendah di Sumatera Selatan, Banten, NTB, dan Sulawesi.
- **Klaster 3 (Risiko Katastropik & Fatalitas Ekstrem)**:
  - Karakteristik: Meskipun jumlah laporan sedikit (2–3 kejadian), dampak yang ditimbulkan berkategori katastropik dengan **fatalitas korban jiwa tertinggi** (rata-rata 18,44 jiwa) dan **kerusakan fisik destruktif tertinggi** (rata-rata 9.127 unit bangunan hancur serta 65.193 warga terdampak per wilayah).
  - Hazard dominan: Erupsi gunung api aktif, tanah longsor lereng curam, dan banjir bandang lahar.
  - Wilayah teridentifikasi (16 kabupaten/kota): Manggarai, Manggarai Timur, Nagekeo, Ngada, Ende, Sikka (NTT — dampak erupsi Lewotobi & cuaca ekstrem); Bandung Barat (Jawa Barat — longsor fatal); Kep. Siau Tagulandang Biaro (Sulut — erupsi Gunung Ruang); Tanggamus (Lampung); Solok (Sumbar — banjir lahar dingin); Kota Bekasi; Sigi (Sulteng); Bangka; Pohuwato.

---

## 5. Visualisasi Hasil Pemetaan

Tujuh visualisasi komprehensif telah dihasilkan dengan resolusi tinggi (300 DPI) di folder `reports/figures/`:
1. **`clustering_metrics_evaluation.png`**: Grafik garis evaluasi multi-metrik (Silhouette, Davies-Bouldin, Calinski-Harabasz) untuk K-Means, Agglomerative Ward, dan Complete Linkage pada rentang $k=2..6$.
2. **`map_clustering_indonesia.png`**: Peta sebaran spasial 412 kabupaten/kota Indonesia dengan koordinat geografis aktual, dibedakan menurut warna dan ukuran 4 tingkat risiko klaster.
3. **`pca_clusters_projection.png`**: Proyeksi 2 dimensi analisis komponen utama (PCA) yang memperlihatkan pemisahan klaster dan vektor beban indikator (*biplot*).
4. **`cluster_risk_profiles_radar.png`**: Radar (*spider*) chart yang membandingkan intensitas relatif 8 dimensi risiko utama pada tiap klaster.
5. **`cluster_feature_distribution.png`**: Diagram batang komparasi rata-rata frekuensi laporan, korban jiwa, warga terdampak, dan kerusakan material per klaster.
6. **`cluster_disaster_type_breakdown.png`**: Diagram batang bertumpuk persentase komposisi jenis bencana dominan di setiap klaster.
7. **`spatial_dbscan_hotspots_map.png`**: Peta perbandingan klaster kepadatan spasial (*Spatial DBSCAN Haversine*, radius 150 km) yang mendeteksi 9 sabuk konsentrasi geografis bencana dan wilayah pulau terisolasi.

---

## 6. Analisis Kritis SDGs 13: Climate Action

### 6.1 Batasan Konseptual & Larangan Klaim Kausalitas Palsu
Dalam kerangka kerja sains data yang berintegritas, terdapat tiga pembedaan tegas yang harus dijaga:
1. **Klaster Analisis $\neq$ Prediksi Masa Depan**:
   - Model clustering ini adalah model *unsupervised descriptive-profiling* yang mengekstraksi struktur keparahan historis tahun 2026.
   - Sistem **TIDAK BOLEH mengklaim telah "memprediksi bencana di masa depan"**, karena prediksi temporal membutuhkan model *supervised time-series / spatio-temporal forecasting* yang diuji secara *out-of-sample / out-of-time*.
2. **Tingkat Risiko adalah Konstruksi Metodologis**:
   - Penetapan label Tingkat I s.d. IV adalah sintesis klasifikasi statistik dari kombinasi dampak, bukan cap permanen kerentanan masa depan.
3. **Korelasi Iklim vs Kausalitas Langsung**:
   - Peningkatan frekuensi hidrometeorologi (Klaster 1 dan 2) konsisten dengan kecenderungan anomali iklim global (SDG 13.1 — memperkuat resiliensi dan adaptasi terhadap bahaya iklim).
   - Namun, **clustering tidak dapat dijadikan bukti ilmiah bahwa perubahan iklim adalah satu-satunya penyebab bencana**. Kerusakan lingkungan lokal, degradasi tutupan hutan, alih fungsi lahan resapan, dan kapasitas drainase perkotaan merupakan faktor determinan yang berinteraksi secara kompleks dengan faktor iklim.

### 6.2 Rekomendasi Kebijakan Berbasis Klaster (BNPB, BPBD & Pemda)
- **Untuk Wilayah Klaster 3 (Katastropik Ekstrem)**:
  - Audit ketat tata ruang permukiman di Kawasan Rawan Bencana (KRB) vulkanik dan zona patahan aktif.
  - Penguatan sistem peringatan dini berbasis sensor lokal (*early warning telemetry*) dan penyediaan jalur/tempat evakuasi akhir yang layak.
- **Untuk Wilayah Klaster 1 (Multi-Hazard Kronis & Lahan)**:
  - Penerapan Pengurangan Risiko Bencana Berbasis Ekosistem (*Ecosystem-based Disaster Risk Reduction / Eco-DRR*).
  - Restorasi daerah tangkapan air dan penegakan hukum pencegahan kebakaran lahan perkebunan.
- **Untuk Wilayah Klaster 2 (Kemanusiaan Akut & Pengungsian)**:
  - Peningkatan kapasitas logistik tanggap darurat, tenda pengungsian ramah anak/perempuan, dan revitalisasi tanggul sungai pengendali banjir.
