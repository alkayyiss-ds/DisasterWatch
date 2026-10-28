# DisasterWatch

Analisis dan pemantauan data bencana Indonesia bersumber dari **Geoportal Data Bencana Indonesia (BNPB)** — <https://gis.bnpb.go.id>.

## Status

Tahap 1 — **download data** ✅ (selesai)

## Dataset

| Item | Nilai |
|---|---|
| Sumber | Geoportal Kebencanaan Indonesia — BNPB |
| Halaman | https://gis.bnpb.go.id (menu **Data Bencana**) |
| Endpoint | `https://gis.bnpb.go.id/databencana/src/index.php?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD` |
| Format | GeoJSON (`FeatureCollection`) + turunan CSV |
| Periode | **1 Januari 2015 – 28 Oktober 2026** (data tersedia sampai 27 Oktober 2026) |
| Jumlah kejadian | **44.290** baris |
| Cakupan | 78 nama provinsi historis, 526 kabupaten/kota |
| Jumlah atribut | 98 atribut + geometri titik (lon/lat) |

### Ringkasan angka

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

### Sebaran jenis bencana

| Jenis | Jumlah |
|---|---:|
| KEBAKARAN HUTAN DAN LAHAN | 1.041 |
| BANJIR | 14.189 |
| CUACA EKSTREM | 12.262 |
| TANAH LONGSOR | 8.035 |
| KEBAKARAN HUTAN DAN LAHAN | 7.953 |
| KEKERINGAN | 764 |
| GEMPABUMI | 559 |
| GELOMBANG PASANG DAN ABRASI | 372 |
| ERUPSI GUNUNG API | 142 |
| TSUNAMI | 9 |
| GEMPA BUMI DAN TSUNAMI | 5 |

## Struktur project

```
DisasterWatch/
├─ data/
│  ├─ raw/
│  │  └─ bnpb_bencana_2015-01-01_2026-10-28.geojson   # respons mentah API
│  └─ processed/
│     ├─ bnpb_bencana_2015-01-01_2026-10-28.csv       # tabel siap analisis
│     └─ metadata.json                                # provenance + ringkasan
├─ scripts/
│  └─ download_bnpb.py                                # downloader (Python stdlib)
└─ README.md
```

## Cara mengunduh ulang

Tidak butuh dependensi eksternal (hanya Python 3.10+).

```powershell
python scripts/download_bnpb.py
# atau rentang lain:
python scripts/download_bnpb.py --start 2015-01-01 --end 2026-10-28
```

Untuk rentang panjang, script mengambil data per bulan, menyimpan cache di
`data/raw/.chunks/`, lalu menggabungkannya. Script akan menimpa file dengan nama
sesuai rentang tanggal, menulis ulang CSV, dan memperbarui metadata.

## Kamus data (kolom CSV)

**Identitas & waktu**
`id_prov`, `id_kab`, `provinsi`, `kabkot`, `id_jenis_bencana`, `kejadian`,
`nama_kejadian`, `tahun`, `bulan`, `tanggal`, `jam`, `tanggal_input`,
`tanggal_update`, `tanggal_status`, `kib`, `dsp`, `kode_bps`, `kode_kemdagri`

**Lokasi**
`lokasi`, `alamat_lengkap`, `desa`, `desa_terdampak`, `longitude`, `latitude`,
`lng_prov`, `lat_prov`, `geometry_lon`, `geometry_lat`

**Korban jiwa & pengungsian**
`meninggal`, `hilang`, `terluka`, `menderita`, `mengungsi`, `menderita_mengungsi`, `md_hlg`

**Kerusakan**
- Rumah: `rumah_rusak_berat`, `rumah_rusak_sedang`, `rumah_rusak_ringan`, `rumah_rusak`
- Fasilitas: `pendidikan_rusak*`, `peribadatan_rusak*`, `kesehatan_rusak*`,
  `kantor_rusak*`, `fasum_rusak*`, `jembatan_rusak*`, `pabrik_rusak*`, `kios_rusak*`
  (masing-masing punya varian `_berat`, `_sedang`, `_ringan`, dan total)
- Lahan: `sawah`, `kebun`, `lahan`, `hutan`, `kolam`, `irigasi`, `terendam`, `jalan`

**Narasi & bantuan**
`keterangan`, `penyebab`, `kronologis`, `sumber`, `link_dokumentasi`,
`kerugian_juta`, `input_oleh`,
`bantuan_bnpb`, `bantuan_kl`, `bantuan_pemprov_pemda`, `bantuan_lainnya`

**Agregasi/flag**
`flag`, `flag_kab`, `flag_prop`, `flag_nas`, `tgl`, `jumlah_kejadian`,
`jml_bencana`, `jml_bcn_prov`, `jml_bcn_kabkot`, `data_update`

## Catatan kualitas data

- Satu baris = satu **laporan kejadian** per kabupaten/kota per tanggal, bukan
  satu bencana unik. Nilai `jumlah_kejadian` bisa lebih dari 1.
- Terdapat **9 grup duplikat** (tanggal + kabupaten + jenis + lokasi sama) —
  kemungkinan laporan ganda; perlu deduplikasi saat analisis.
- Banyak atribut korban/kerusakan bernilai kosong (`null`) karena pelaporan
  bertahap; gunakan `0` secara hati-hati saat agregasi.
- Data `2026-10-21` adalah batas atas permintaan; sumber terus diperbarui
  (halaman tabel BNPB saat ini memuat data hingga 27 Okt 2026).
- Endpoint alternatif (tabel resmi): `POST https://gis.bnpb.go.id/databencana/tabel/pencarian.php`
  dengan `tgl_awal`, `tgl_akhir`, `s_kejadian` (format `YYYY-MM-DD`) — menghasilkan
  2.260 baris yang sama, tetapi hanya 16 kolom ringkas.
