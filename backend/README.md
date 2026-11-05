# DisasterWatch — Backend & Model Prediksi Dampak

Folder ini berisi model klasifikasi terbaik (**Random Forest**) untuk halaman **Prediksi Dampak**, API **FastAPI**,
dan skrip yang mengekspor semuanya menjadi file statis agar dashboard (`frontend/dashboard.html`) bisa di-deploy
**tanpa server backend**.

```
backend/
├─ dw_model.py          # pembersihan data, label severity, fitur (dipakai pelatihan & prediksi)
├─ train_model.py       # melatih, mengevaluasi, dan menyimpan model ke backend/models/
├─ mitigasi.py          # basis aturan rekomendasi mitigasi
├─ export_static.py     # data dashboard → frontend/data/*.json, lalu memanggil export_js_model.py
├─ export_js_model.py   # model Random Forest → frontend/js/model/*.js (prediksi di browser)
├─ app.py               # API FastAPI (opsional): /api/dashboard-data, /api/prediksi
├─ extra_api.py         # API tambahan: overview, klaster, tren, laporan, unduh
├─ requirements.txt
├─ models/              # dibuat otomatis oleh train_model.py (tidak di-commit)
└─ tests/               # test_api.py (API) & test_js_model.py (model JavaScript = API)
```

## Cara menjalankan

Dari **root repo** (folder yang berisi `backend/`, `frontend/`, `data/`):

```powershell
# 1. Virtual environment (sekali saja)
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Latih model (±40 detik) → backend/models/
python backend/train_model.py

# 3. Buat file statis untuk dashboard: frontend/data/*.json + frontend/js/model/*.js
python backend/export_static.py

# 4. Buka dashboard (server statis apa saja)
cd frontend ; python -m http.server 8001     # http://localhost:8001/dashboard.html
```

Untuk deploy, unggah folder `frontend/` ke GitHub Pages, Netlify, atau Vercel. Halaman lain membaca
`frontend/data/*.json` lewat `fetch`, jadi dashboard perlu dibuka lewat http(s), bukan `file://`.
Halaman Prediksi Dampak sendiri tetap berjalan meskipun dibuka langsung dari file.

API FastAPI tidak wajib untuk dashboard, tetapi berguna untuk pengujian dan dokumentasi:

```powershell
uvicorn backend.app:app --reload --port 8000  # http://localhost:8000/docs
```

Uji otomatis: `pytest backend/tests -q` (tes model JavaScript butuh Node.js; tanpa Node tes itu dilewati).

## Endpoint API

| Metode | Path | Fungsi |
|---|---|---|
| GET | `/api/dashboard-data` | KPI, top provinsi, komposisi jenis, faktor risiko model |
| GET | `/api/overview?tahun=&jenis=&provinsi=&dari=` | ringkasan Overview & Peta (tahun=0 terbaru, tahun<0 semua tahun) |
| GET | `/api/extra` | klaster risiko & jenis dominan |
| GET | `/api/tren?seri=&model=&horizon=` | aktual, uji, dan prediksi tren bulanan |
| GET | `/api/laporan`, `/api/unduh/{kode}` | daftar & unduhan file laporan |
| POST | `/api/prediksi` | tingkat dampak (Random Forest) + estimasi korban/terdampak/kerusakan |

Contoh `POST /api/prediksi`:

```json
{ "jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": "Januari", "kepadatan": "Sedang" }
```

```json
{ "tingkat": 3, "label": "Berat", "probabilitas": [4, 2, 34, 60],
  "korban": 0, "terdampak": 3151, "rusak": 613,
  "rentang": { "korban": [0, 0], "terdampak": [944, 13417], "rusak": [185, 2402] },
  "basis_estimasi": "provinsi & jenis (2024+)", "n_historis": 179 }
```

`jenis_bencana` menerima kode BNPB (`BANJIR`), label (`Banjir`, `Karhutla`), atau alias (`gempa`, `longsor`).
`provinsi` menerima nama (`Jawa Tengah` / `JAWA TENGAH`). `bulan` menerima nama atau angka 1–12.
Input yang tidak dikenal menghasilkan HTTP 400.

## Model

| Aspek | Keterangan |
|---|---|
| Algoritma | `RandomForestClassifier` (300 pohon, `max_features="sqrt"`, `min_samples_leaf` dipilih dari {5, 10, 20} berdasarkan MSE validation) |
| Target | tingkat dampak: Tanpa Dampak / Ringan / Sedang / Berat (aturan sama dengan `preprocessing_disaster.ipynb`) |
| Data | 44.161 laporan BNPB 2015–2026 setelah deduplikasi |
| Fitur | jenis bencana; provinsi, region & titik pusat provinsi; bulan (sin/cos) & musim hujan; tahun & era pelaporan 2024+; riwayat keparahan laporan **sebelumnya** di provinsi dan provinsi × jenis bencana |
| Evaluasi (uji 20%) | accuracy **0,697**, balanced accuracy 0,686, F1-macro 0,681, MSE 0,407 (baseline "jenis bencana saja" 0,665) |

Angka lengkap tersimpan di `backend/models/model_meta.json` setiap kali model dilatih ulang.

**Bedanya dengan Random Forest di `notebook/modelling_classification.ipynb`** (accuracy 0,701): notebook memakai fitur
tingkat kab/kota dan koordinat titik kejadian. Halaman Prediksi Dampak hanya memiliki input jenis bencana, provinsi, dan bulan,
sehingga model deployment memakai fitur tingkat provinsi. Akurasinya turun sedikit (0,697), tetapi model ini bisa dipakai
langsung dari input halaman.

## Model versi JavaScript (Prediksi Dampak tanpa server)

```
frontend/js/model/
├─ rf_forest.js   # 300 pohon Random Forest (di-generate, ±1,8 MB; ±620 KB setelah gzip)
├─ dw_lookup.js   # provinsi, riwayat, estimasi dampak, klaster, aturan mitigasi.py (di-generate)
└─ dw_model.js    # logika prediksi: fitur → 300 pohon → peluang kelas → estimasi & mitigasi (ditulis manual)
```

- `DWModel.prediksi(body)` menghasilkan JSON yang **sama persis** dengan `POST /api/prediksi`.
  `frontend/js/data.js` memakainya untuk halaman Prediksi Dampak. Jika folder `js/model/` tidak ada,
  halaman kembali memakai tabel `frontend/data/prediksi.json`.
- `DWModel.mitigasi(tingkat, jenis, kepadatan, provinsi)` menyusun rekomendasi dengan aturan `mitigasi.py`
  (tingkat dampak, jenis bencana, kepadatan, dan klaster dominan provinsi).
- `export_js_model.py` menjalankan setiap pohon untuk seluruh input halaman
  (10 jenis × 38 provinsi × 12 bulan = 4.560 kombinasi) dan membuang cabang yang tidak pernah dilalui,
  sehingga node berkurang dari ±849 ribu menjadi ±103 ribu. Ambang split dan isi daun tidak diubah,
  dan skrip memverifikasi bahwa peluangnya sama dengan model asli sebelum menulis file.
- `DW_JS_FULL=1 pytest backend/tests/test_js_model.py` membandingkan JavaScript dengan API untuk ke-4.560 kombinasi.
- Model di browser memprediksi untuk tahun data terakhir (2026) ke atas, sama dengan API yang memakai tahun berjalan.

## Batasan yang perlu diketahui

- **Kepadatan penduduk tidak dipakai model**, karena tidak ada di data BNPB. Input ini hanya memengaruhi rekomendasi mitigasi
  (mis. "Prioritaskan evakuasi kawasan padat"). Untuk memakainya sebagai fitur, tambahkan data kepadatan BPS per provinsi/kab-kota.
- **Estimasi korban/terdampak/kerusakan bukan keluaran model.** Angkanya adalah median (dan rentang kuartil) dari minimal 5 laporan
  historis dengan jenis bencana dan tingkat dampak yang sama, diutamakan dari provinsi yang sama dan sejak 2024 (era pelaporan terbaru).
- **Rekomendasi mitigasi berbasis aturan** (`mitigasi.py`), bukan keluaran model ML.
- **Profil klaster provinsi** diambil dari `bnpb_disaster_clusters.csv`. File itu berisi 1.041 baris untuk 526 `id_kab` unik
  (nama kab/kota tercatat ganda dengan kapitalisasi berbeda, dan 348 kab/kota mendapat klaster berbeda di baris duplikatnya).
  Model memakai satu baris per `id_kab`, yaitu baris dengan `total_laporan` terbanyak. Sebaiknya normalisasi nama kab/kota
  dilakukan di tahap clustering.
- Versi scikit-learn saat melatih dan menjalankan server harus sama. Jika berbeda, jalankan ulang `train_model.py`.
