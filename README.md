# 🌋 DisasterWatch

**Platform Analitik dan Prediksi Dampak Bencana Indonesia** berbasis Machine Learning, dengan data historis dari [Geoportal Data Bencana Indonesia (BNPB)](https://gis.bnpb.go.id).

🌐 **Live Demo:** [https://disasterwatch-frontend.vercel.app/](https://disasterwatch-frontend.vercel.app/)

![Status](https://img.shields.io/badge/Status-Production-brightgreen)
![Architecture](https://img.shields.io/badge/Architecture-Zero--Backend-blue)
![Model](https://img.shields.io/badge/ML-Random%20Forest-orange)
[![Deploy](https://img.shields.io/badge/Deploy-Vercel-black)](https://disasterwatch-frontend.vercel.app/)

---

## 📑 Daftar Isi

- [Tentang Proyek](#-tentang-proyek)
- [Dataset](#-dataset)
- [Arsitektur Sistem](#️-arsitektur-sistem)
- [Struktur Project](#️-struktur-project)
- [Cara Menjalankan](#-cara-menjalankan)
- [Deploy ke Vercel](#-deploy-ke-vercel)
- [Halaman Dashboard](#-halaman-dashboard)
- [Hasil Modelling](#-hasil-modelling)
- [API FastAPI (Opsional)](#-api-fastapi-opsional)
- [Mengunduh Ulang Data](#-mengunduh-ulang-data)
- [Kamus Data](#-kamus-data)
- [Catatan Kualitas Data](#️-catatan-kualitas-data)
- [Tim Pengembang](#-tim-pengembang-kelompok-4)

---

## 📖 Tentang Proyek

DisasterWatch mengubah **44.290 laporan kejadian bencana (2015–2026)** menjadi wawasan interaktif dan prediktif. Proyek ini dikembangkan sebagai bagian dari tugas akhir (makalah) untuk menerapkan Machine Learning dalam mitigasi bencana di Indonesia.

### Fitur Utama

- 📊 **Dashboard Interaktif**: Overview, Peta Wilayah, Prediksi Dampak, Klaster Risiko, dan Tren & Prediksi.
- 🤖 **Machine Learning di Browser**: model Random Forest (300 pohon) berjalan langsung di JavaScript, tanpa server backend.
- 📈 **Time Series Forecasting**: prediksi jumlah kejadian 12 bulan ke depan dengan XGBoost.
- 🎯 **Clustering K-Means**: pengelompokan kabupaten/kota ke dalam 4 klaster risiko.
- 🗺️ **Peta Interaktif**: sebaran kejadian dengan Leaflet + OpenStreetMap.
- 🎨 **Glassmorphism UI/UX**: landing page dengan animasi scroll, dark mode, dan tema warna aksen.

---

## 📦 Dataset

| Item | Nilai |
|---|---|
| **Sumber** | Geoportal Kebencanaan Indonesia, BNPB |
| **URL** | <https://gis.bnpb.go.id> |
| **Endpoint** | `https://gis.bnpb.go.id/databencana/src/index.php?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD` |
| **Format** | GeoJSON (`FeatureCollection`) + turunan CSV |
| **Periode** | 1 Januari 2015 – 28 Oktober 2026 |
| **Jumlah kejadian** | 44.290 baris |
| **Cakupan** | 78 provinsi historis, 526 kabupaten/kota |
| **Atribut** | 98 atribut + geometri titik (lon/lat) |

### Ringkasan Angka

| Metrik | Total |
|---|---:|
| Kejadian | 44.290 |
| Meninggal | 11.795 |
| Hilang | 1.596 |
| Terluka | 79.244 |
| Menderita | 72.639.034 |
| Mengungsi | 5.794.858 |
| Rumah rusak | 1.395.089 |
| Rumah terendam | 8.930.793 |
| Lahan terdampak (ha) | 1.525.898,54 |

### Sebaran Jenis Bencana

| Jenis | Jumlah |
|---|---:|
| Banjir | 14.189 |
| Cuaca ekstrem | 12.262 |
| Tanah longsor | 8.035 |
| Kebakaran hutan dan lahan | 7.953 |
| Kekeringan | 764 |
| Gempabumi | 559 |
| Gelombang pasang dan abrasi | 372 |
| Erupsi gunung api | 142 |
| Tsunami | 9 |
| Gempa bumi dan tsunami | 5 |

---

## 🏗️ Arsitektur Sistem

Proyek ini menggunakan pendekatan **zero-backend**: semua komputasi (termasuk ML) dijalankan di browser pengguna. Server hanya menyajikan file statis (HTML, CSS, JS, JSON).

```text
┌─────────────────────────────────────────────────────────────┐
│            PIPELINE PYTHON (Offline, Developer)             │
│                                                             │
│  Data BNPB → Preprocessing → Training Model                 │
│                      ↓                                      │
│     export_static.py + export_js_model.py                   │
│                      ↓                                      │
│     frontend/data/*.json + frontend/js/model/*.js          │
└─────────────────────────────────────────────────────────────┘
                          ↓ (deploy)
┌─────────────────────────────────────────────────────────────┐
│               FRONTEND STATIS (Vercel CDN)                  │
│                                                             │
│  HTML + CSS + JS + JSON + Model Random Forest (di browser)  │
│                          ↓                                  │
│                   👤 Pengguna Akhir                         │
└─────────────────────────────────────────────────────────────┘
```

**Keunggulan:**

- 💰 Biaya hosting Rp 0 (Vercel/Netlify gratis)
- ⚡ Performa tinggi lewat CDN global
- 🔒 Tidak ada server backend yang perlu di-*maintain*
- 📱 Responsif di semua perangkat

---

## 🗂️ Struktur Project

```text
DisasterWatch/
├── backend/                      # Pipeline Python
│   ├── app.py                    # API FastAPI (opsional)
│   ├── train_model.py            # Training ML (Random Forest, XGBoost, SARIMA)
│   ├── export_static.py          # Generate frontend/data/*.json
│   ├── export_js_model.py        # Generate frontend/js/model/*.js
│   ├── dw_model.py               # Konstanta & helper bersama
│   ├── mitigasi.py               # Aturan rekomendasi mitigasi
│   ├── requirements.txt          # Dependensi Python
│   └── model/                    # Hasil training
│       ├── rf_severity.joblib
│       ├── model_meta.json
│       └── lookup.json
│
├── data/                         # Data mentah & hasil olahan
│   ├── raw/
│   │   └── bnpb_bencana_2015-01-01_2026-10-28.geojson
│   └── processed/
│       ├── bnpb_bencana_2015-01-01_2026-10-28.csv
│       ├── classification_*.csv
│       ├── korban_jiwa_*.csv
│       └── metadata.json
│
├── frontend/                     # Frontend statis (deploy ke Vercel)
│   ├── index.html                # Landing page (glassmorphism)
│   ├── dashboard.html            # Dashboard
│   ├── css/
│   │   ├── style.css
│   │   └── ui-patch.css
│   ├── js/
│   │   ├── app.js                # Logika UI/UX
│   │   ├── data.js               # Fetcher JSON
│   │   └── model/
│   │       ├── rf_forest.js      # 300 pohon Random Forest (±1,8 MB)
│   │       ├── dw_lookup.js      # Data lookup (±379 KB)
│   │       └── dw_model.js       # Logika prediksi
│   └── data/                     # Data statis (JSON)
│       ├── meta.json
│       ├── agg.json
│       ├── kab.json
│       ├── extra.json
│       ├── laporan.json
│       ├── tren.json
│       ├── prediksi.json
│       └── unduh/                # File CSV untuk diunduh pengguna
│
├── notebook/                     # Notebook eksplorasi & modelling
│   ├── eda_disaster.ipynb
│   ├── feature_engineering.ipynb
│   ├── modelling_classification.ipynb
│   └── modelling_classification_korban_jiwa.ipynb
│
├── reports/
│   └── figures/                  # clf_*.png, kj_*.png
│
├── scripts/
│   └── download_bnpb.py          # Downloader data BNPB
│
├── trend-modeling/               # Model time series (XGBoost, SARIMA)
├── .gitignore
└── README.md
```

---

## 🚀 Cara Menjalankan

### Prasyarat

- Python 3.10+
- pip
- Browser modern (Chrome, Firefox, Safari, Edge)

### 1. Clone Repository

```bash
git clone https://github.com/alkayyiss-ds/DisasterWatch.git
cd DisasterWatch
```

### 2. Buat Virtual Environment (opsional, disarankan)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependensi

```bash
pip install -r backend/requirements.txt
```

### 4. Generate Data Statis & Model JS

Jalankan langkah ini hanya jika data atau model berubah:

```bash
python backend/train_model.py      # Training model → backend/model/ (±40 detik)
python backend/export_static.py    # Generate frontend/data/*.json + frontend/js/model/*.js
```

> 💡 `export_static.py` sudah otomatis memanggil `export_js_model.py`, jadi tidak perlu dijalankan terpisah.

### 5. Jalankan Server Lokal

```bash
cd frontend
python -m http.server 8001
```

Buka <http://localhost:8001> di browser.

---

## 🌐 Deploy ke Vercel

1. Push kode ke GitHub.
2. Buka [vercel.com](https://vercel.com) dan login dengan GitHub.
3. Klik **Add New → Project**, lalu import repo `DisasterWatch`.
4. Isi konfigurasi berikut:

   | Pengaturan | Nilai |
   |---|---|
   | **Root Directory** | `frontend` ⚠️ wajib |
   | **Application Preset** | `Other` ⚠️ wajib |
   | **Build Command** | *(kosongkan)* |
   | **Output Directory** | *(kosongkan)* |

5. Klik **Deploy** dan tunggu sekitar 30 detik sampai URL aktif.

Versi yang sedang berjalan: <https://disasterwatch-frontend.vercel.app/>

Setiap `git push` ke `main` akan otomatis memicu re-deploy.

**Alternatif hosting:**

- **Netlify**: drag & drop folder `frontend/` ke [app.netlify.com/drop](https://app.netlify.com/drop).
- **GitHub Pages**: pindahkan isi `frontend/` ke root, lalu aktifkan Pages di Settings.

---

## 📊 Halaman Dashboard

| Halaman | Fungsi |
|---|---|
| **Overview** | Ringkasan KPI (total kejadian, korban, rumah rusak), tren bulanan, komposisi jenis bencana, peta sebaran, top 5 provinsi. |
| **Peta Wilayah** | Peta interaktif dengan titik risiko, filter periode/jenis, top kabupaten rawan, jenis bencana dominan per provinsi. |
| **Prediksi Dampak** | Simulasi prediksi tingkat dampak (Random Forest di browser), rekomendasi mitigasi, feature importance. |
| **Klaster Risiko** | 4 klaster risiko (Risiko Rendah, Multi-Bencana Kronis, Kemanusiaan Akut, Katastropik), perbandingan dampak, metrik evaluasi. |
| **Tren & Prediksi** | Grafik forecast 12 bulan (XGBoost), tabel evaluasi model, prediksi bulanan, unduh CSV. |
| **Laporan** | Pusat unduhan dataset dan hasil analisis. |
| **Pengaturan** | Tema warna aksen, dark mode, auto-refresh, profil pengguna. |

---

## 📈 Hasil Modelling

### Klasifikasi Tingkat Dampak (Random Forest)

| Metrik | Nilai |
|---|---|
| Akurasi | **69,68%** |
| Wilayah terklasifikasi | 526 kabupaten/kota |
| Faktor dominan #1 | Jenis bencana (50,9%) |
| Faktor dominan #2 | Riwayat wilayah (30,1%) |
| Faktor dominan #3 | Era pelaporan (14,1%) |

### Clustering Risiko (K-Means, k = 4)

| Klaster | Karakteristik | Jumlah Wilayah |
|---|---|---:|
| 0 | Risiko Rendah | 171 |
| 1 | Multi-Bencana Kronis | 413 |
| 2 | Kemanusiaan Akut | 380 |
| 3 | Katastropik | 77 |

### Time Series Forecasting (XGBoost)

| Metrik | Nilai |
|---|---|
| MAE | 65,0 |
| RMSE | 85,4 |
| MAPE | 29,8% |

---

## 🔌 API FastAPI (Opsional)

Dashboard berjalan *zero-backend*, tetapi API FastAPI tetap tersedia untuk riset atau pengujian:

```bash
uvicorn backend.app:app --reload --port 8000
```

Dokumentasi interaktif: <http://localhost:8000/docs>

Detail endpoint, model, dan batasannya ada di [`backend/README.md`](backend/README.md).

---

## 🔄 Mengunduh Ulang Data

Script `scripts/download_bnpb.py` hanya memakai Python standard library (tanpa dependensi eksternal):

```bash
python scripts/download_bnpb.py

# atau dengan rentang kustom
python scripts/download_bnpb.py --start 2015-01-01 --end 2026-10-28
```

Untuk rentang panjang, script mengunduh data per bulan, menyimpan cache di `data/raw/.chunks/`, lalu menggabungkannya.

---

## 📚 Kamus Data

Kolom pada file CSV, dikelompokkan berdasarkan kategori.

| Kategori | Kolom |
|---|---|
| **Identitas & waktu** | `id_prov`, `id_kab`, `provinsi`, `kabkot`, `id_jenis_bencana`, `kejadian`, `nama_kejadian`, `tahun`, `bulan`, `tanggal`, `jam`, `tanggal_input`, `tanggal_update`, `tanggal_status`, `kib`, `dsp`, `kode_bps`, `kode_kemdagri` |
| **Lokasi** | `lokasi`, `alamat_lengkap`, `desa`, `desa_terdampak`, `longitude`, `latitude`, `lng_prov`, `lat_prov`, `geometry_lon`, `geometry_lat` |
| **Korban jiwa & pengungsian** | `meninggal`, `hilang`, `terluka`, `menderita`, `mengungsi`, `menderita_mengungsi`, `md_hlg` |
| **Kerusakan rumah** | `rumah_rusak_berat`, `rumah_rusak_sedang`, `rumah_rusak_ringan`, `rumah_rusak` |
| **Kerusakan fasilitas** | `pendidikan_rusak*`, `peribadatan_rusak*`, `kesehatan_rusak*`, `kantor_rusak*`, `fasum_rusak*`, `jembatan_rusak*`, `pabrik_rusak*`, `kios_rusak*` |
| **Kerusakan lahan** | `sawah`, `kebun`, `lahan`, `hutan`, `kolam`, `irigasi`, `terendam`, `jalan` |
| **Narasi & bantuan** | `keterangan`, `penyebab`, `kronologis`, `sumber`, `link_dokumentasi`, `kerugian_juta`, `input_oleh`, `bantuan_bnpb`, `bantuan_kl`, `bantuan_pemprov_pemda`, `bantuan_lainnya` |
| **Agregasi & flag** | `flag`, `flag_kab`, `flag_prop`, `flag_nas`, `tgl`, `jumlah_kejadian`, `jml_bencana`, `jml_bcn_prov`, `jml_bcn_kabkot`, `data_update` |

---

## ⚠️ Catatan Kualitas Data

- Satu baris adalah satu **laporan kejadian** per kabupaten/kota per tanggal, bukan satu bencana unik. Nilai `jumlah_kejadian` bisa lebih dari 1.
- Terdapat **9 grup duplikat** (tanggal + kabupaten + jenis + lokasi sama), sehingga perlu deduplikasi saat analisis.
- Banyak atribut korban/kerusakan bernilai kosong (`null`) karena pelaporan bertahap. Gunakan pengisian `0` dengan hati-hati saat agregasi.
- Sumber data terus diperbarui oleh BNPB, sehingga angka dapat berbeda jika data diunduh ulang di kemudian hari.
- Endpoint alternatif (tabel resmi): `POST https://gis.bnpb.go.id/databencana/tabel/pencarian.php` dengan parameter `tgl_awal`, `tgl_akhir`, `s_kejadian`. Hasilnya 2.260 baris dengan 16 kolom ringkas.

---

## 👥 Tim Pengembang (Kelompok 4)

| Nama | NIM |
|---|---|
| Intan Dwi | 3324600006 |
| Linda Anggara Wati | 3324600008 |
| Shafa Dzia | 3324600017 |
| Kayla Nuansa | 3324600023 |
| Naufal Al-Kayyis | 3324600026 |

- **Mata Kuliah:** Presentasi Data & Storytelling
- **Dosen Pengampu:** Fitrah Maharani Humaira, S.Si., M.Kom.
- **Institusi:** Politeknik Elektronika Negeri Surabaya

---

## 📄 Lisensi

Proyek ini dikembangkan untuk keperluan akademik (tugas akhir/makalah). Data bersumber dari [BNPB](https://gis.bnpb.go.id) dan digunakan sesuai ketentuan yang berlaku.

---

## 🙏 Ucapan Terima Kasih

- **BNPB** atas penyediaan data terbuka kebencanaan Indonesia.
- **OpenStreetMap** atas *tile* peta gratis.
- **Chart.js, Leaflet.js, Scikit-Learn, XGBoost** sebagai library open-source yang menjadi tulang punggung proyek ini.