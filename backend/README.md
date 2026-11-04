# DisasterWatch — Backend Prediksi Dampak

API **FastAPI** yang menerapkan model klasifikasi terbaik (**Random Forest**) pada halaman
**Prediksi Dampak** di dashboard (`frontend/index.html`).

```
backend/
├─ app.py            # API + menyajikan folder frontend/
├─ dw_model.py       # pembersihan data, label severity, fitur (dipakai pelatihan & prediksi)
├─ train_model.py    # melatih, mengevaluasi, dan menyimpan model ke backend/models/
├─ mitigasi.py       # basis aturan rekomendasi mitigasi
├─ requirements.txt
├─ models/           # dibuat otomatis oleh train_model.py (tidak di-commit)
└─ tests/test_api.py
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

# 3. Jalankan server
uvicorn backend.app:app --reload --port 8000
```

Lalu buka:
- **http://localhost:8000**: dashboard; pilih menu *Prediksi Dampak*
- **http://localhost:8000/docs**: dokumentasi interaktif API (bisa mencoba prediksi langsung)

Jika langkah 2 terlewat, server otomatis melatih model saat pertama kali dijalankan.
`frontend/index.html` juga tetap bisa dibuka langsung dari file atau Live Server. Prediksi akan dipanggil
ke `http://localhost:8000` selama server berjalan. Jika server mati, halaman menampilkan petunjuk cara menyalakannya.

Uji otomatis: `pytest backend/tests -q`

## Endpoint

| Metode | Path | Fungsi |
|---|---|---|
| GET | `/api/health` | status server & versi model |
| GET | `/api/prediksi/meta` | opsi dropdown (10 jenis bencana, 38 provinsi, 12 bulan), metrik model, faktor risiko dominan, ringkasan klaster, nilai KPI |
| POST | `/api/prediksi` | prediksi tingkat dampak + estimasi korban/terdampak/kerusakan + profil klaster provinsi + rekomendasi mitigasi |

Contoh request `POST /api/prediksi`:

```json
{ "jenis_bencana": "Banjir", "provinsi": "Jawa Tengah", "bulan": "Januari", "kepadatan_penduduk": "Sedang" }
```

`jenis_bencana` menerima kode BNPB (`BANJIR`) atau label (`Banjir`, `Karhutla`, `Gempa bumi`). `provinsi`
menerima nama (`Jawa Tengah`/`JAWA TENGAH`) atau `id_prov` (`33`). `bulan` menerima nama atau angka 1–12.
`tahun` opsional (default tahun berjalan).

Potongan respons:

```json
{
  "prediksi": { "kelas": "Berat", "probabilitas": 0.60,
                "peluang": [{"kelas": "Tanpa Dampak", "p": 0.04}, {"kelas": "Ringan", "p": 0.02},
                            {"kelas": "Sedang", "p": 0.34}, {"kelas": "Berat", "p": 0.60}] },
  "estimasi": { "korban_jiwa": {"teks": "Umumnya 0 jiwa", "detail": "11% laporan serupa ada korban jiwa"},
                "terdampak":   {"teks": "~ 3.151 jiwa", "detail": "rentang umum 944–13.417"},
                "kerusakan":   {"teks": "~ 613 unit",   "detail": "rentang umum 185–2.402"},
                "basis": "Median dari 179 laporan banjir kategori \"Berat\" di Jawa Tengah (sejak 2024)" },
  "klaster_provinsi": { "klaster": 1, "pendek": "Tingkat II - Kronis/Multi-Hazard" },
  "mitigasi": [ { "t": "Aktifkan posko & status siaga darurat", "sumber": "Tingkat dampak", "urgent": true }, "..." ]
}
```

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

## Batasan yang perlu diketahui

- **Kepadatan penduduk tidak dipakai model**, karena tidak ada di data BNPB. Input ini hanya memengaruhi rekomendasi mitigasi
  (mis. "Prioritaskan evakuasi kawasan padat"). Untuk memakainya sebagai fitur, tambahkan data kepadatan BPS per provinsi/kab-kota.
- **Estimasi korban/terdampak/kerusakan bukan keluaran model.** Angkanya adalah median (dan rentang kuartil) dari laporan historis
  dengan jenis bencana dan kategori dampak yang sama, diutamakan dari provinsi yang sama dan sejak 2024 (era pelaporan terbaru).
- **Rekomendasi mitigasi berbasis aturan** (`mitigasi.py`), yang menggabungkan tingkat dampak terprediksi, jenis bencana,
  kepadatan, dan klaster dominan provinsi.
- **Profil klaster provinsi** diambil dari `bnpb_disaster_clusters.csv`. File itu berisi 1.041 baris untuk 526 `id_kab` unik
  (nama kab/kota tercatat ganda dengan kapitalisasi berbeda, dan 348 kab/kota mendapat klaster berbeda di baris duplikatnya).
  Backend memakai satu baris per `id_kab`, yaitu baris dengan `total_laporan` terbanyak. Sebaiknya normalisasi nama kab/kota
  dilakukan di tahap clustering.
- Versi scikit-learn saat melatih dan menjalankan server harus sama. Jika berbeda, jalankan ulang `train_model.py`.
