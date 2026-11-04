"""
Basis aturan rekomendasi mitigasi (rule-based, BUKAN keluaran model ML).

Rekomendasi disusun dari empat sumber:
  1. tingkat dampak terprediksi (keluaran Random Forest)
  2. jenis bencana
  3. kepadatan penduduk (input pengguna; tidak dipakai model)
  4. profil klaster risiko dominan di provinsi (hasil K-Means rekan)
Daftar per klaster sama dengan yang sebelumnya ada di frontend/js/app.js.
"""
from __future__ import annotations

PER_TINGKAT = {
    3: {"t": "Aktifkan posko & status siaga darurat",
        "d": "Siapkan posko tanggap darurat, TRC BPBD, dan logistik pengungsian sejak laporan pertama masuk."},
    2: {"t": "Siaga BPBD & pra-posisi logistik",
        "d": "Siagakan TRC dan geser stok logistik ke kecamatan terdekat sebelum dampak meluas."},
    1: {"t": "Kaji cepat (rapid assessment) di lokasi",
        "d": "Verifikasi kerusakan dan warga terdampak dalam 24 jam pertama untuk mencegah eskalasi."},
    0: {"t": "Pencegahan & pemantauan rutin",
        "d": "Lanjutkan pemantauan dan pencegahan; dampak terhadap warga dan rumah biasanya kecil."},
}

PER_JENIS = {
    "BANJIR": [
        {"t": "Pantau tinggi muka air & peringatan dini banjir", "d": "Hubungkan pos pantau sungai dan info BMKG ke grup warga di bantaran sungai."},
        {"t": "Normalisasi sungai & drainase", "d": "Bersihkan sedimen dan sampah di saluran sebelum puncak musim hujan."},
    ],
    "TANAH LONGSOR": [
        {"t": "Pemetaan & pemantauan lereng rawan", "d": "Tandai zona merah longsor dan pasang alat pantau retakan/curah hujan sederhana."},
        {"t": "Relokasi & penguatan lereng", "d": "Pindahkan rumah dari tebing curam; tanam vegetasi berakar dalam dan buat terasering."},
    ],
    "GEMPABUMI": [
        {"t": "Audit bangunan tahan gempa", "d": "Prioritaskan sekolah, puskesmas, dan kantor pemerintahan untuk retrofit struktur."},
        {"t": "Latihan evakuasi gempa", "d": "Simulasi rutin drop–cover–hold dan titik kumpul terbuka di tiap desa."},
    ],
    "KEBAKARAN HUTAN DAN LAHAN": [
        {"t": "Patroli titik panas & pemadaman dini", "d": "Pantau hotspot satelit harian dan siagakan Masyarakat Peduli Api."},
        {"t": "Pembasahan gambut & layanan ISPA", "d": "Sekat kanal untuk menjaga gambut tetap basah; siapkan masker dan posko kesehatan."},
    ],
    "CUACA EKSTREM": [
        {"t": "Sebarkan peringatan dini cuaca BMKG", "d": "Teruskan peringatan angin kencang/hujan lebat ke tingkat desa dalam hitungan jam."},
        {"t": "Pangkas pohon rawan & periksa atap", "d": "Kurangi risiko pohon tumbang dan atap terbang di permukiman padat."},
    ],
    "KEKERINGAN": [
        {"t": "Distribusi air bersih", "d": "Jadwalkan droping air dan perbaiki sumur bor di desa rawan kekeringan."},
        {"t": "Embung & penampungan air hujan", "d": "Bangun cadangan air untuk pertanian sebelum puncak kemarau."},
    ],
    "GELOMBANG PASANG DAN ABRASI": [
        {"t": "Peringatan gelombang tinggi untuk nelayan", "d": "Sebarkan prakiraan gelombang BMKG ke TPI dan kelompok nelayan."},
        {"t": "Mangrove & pemecah gelombang", "d": "Rehabilitasi sabuk hijau pantai untuk menahan abrasi."},
    ],
    "ERUPSI GUNUNG API": [
        {"t": "Patuhi radius bahaya PVMBG", "d": "Kosongkan zona bahaya sesuai status gunung api dan siapkan jalur evakuasi."},
        {"t": "Masker & logistik pengungsian", "d": "Siapkan masker abu vulkanik serta kebutuhan pengungsi jangka menengah."},
    ],
    "TSUNAMI": [
        {"t": "Jalur & bangunan evakuasi vertikal", "d": "Pastikan rambu evakuasi dan tempat evakuasi sementara di pesisir."},
        {"t": "Sirene peringatan dini tsunami", "d": "Uji sirene secara berkala dan latih warga merespons dalam 10 menit."},
    ],
}
PER_JENIS["GEMPA BUMI DAN TSUNAMI"] = PER_JENIS["GEMPABUMI"][:1] + PER_JENIS["TSUNAMI"][:1]

PER_KEPADATAN = {
    "Tinggi": {"t": "Prioritaskan evakuasi kawasan padat",
               "d": "Hitung kapasitas shelter dan buka jalur evakuasi alternatif agar tidak terjadi penumpukan."},
    "Sangat tinggi": {"t": "Prioritaskan evakuasi kawasan padat",
                      "d": "Hitung kapasitas shelter dan buka jalur evakuasi alternatif agar tidak terjadi penumpukan."},
    "Rendah": {"t": "Jangkauan logistik ke wilayah terpencil",
               "d": "Siapkan rute dan moda distribusi bantuan untuk permukiman yang tersebar dan jauh."},
}

PER_KLASTER = {
    0: [
        {"t": "Sosialisasi & edukasi kebencanaan", "d": "Program rutin di sekolah & komunitas untuk meningkatkan literasi risiko."},
        {"t": "Pemeliharaan drainase & saluran air", "d": "Pembersihan berkala untuk mencegah genangan saat musim hujan."},
        {"t": "Monitoring & deteksi dini sederhana", "d": "Pemantauan cuaca dan titik rawan bersama babinsa/karang taruna."},
    ],
    1: [
        {"t": "Diversifikasi mata pencaharian", "d": "Mengurangi ketergantungan pada sektor pertanian yang rentan bencana."},
        {"t": "Asuransi pertanian & perlindungan sosial", "d": "Perluas cakupan asuransi lahan dan kompensasi kerusakan."},
        {"t": "Perbaikan tata guna lahan & DAS", "d": "Reboisasi dan pengelolaan DAS untuk cegah banjir/longsor."},
        {"t": "Sistem peringatan dini hidrometeorologi", "d": "Integrasi info BMKG ke level desa dan grup komunikasi warga."},
        {"t": "Penguatan bangunan tahan bencana", "d": "Retrofit rumah & fasilitas publik di zona rawan."},
    ],
    2: [
        {"t": "Rencana kontingensi & jalur evakuasi", "d": "Peta evakuasi, titik kumpul, dan latihan simulasi rutin."},
        {"t": "Stok logistik darurat wilayah", "d": "Gudang logistik di level kabupaten dengan buffer 7 hari."},
        {"t": "Tim reaksi cepat (TRC) terlatih", "d": "Pelatihan SAR dasar untuk relawan dan aparat desa."},
        {"t": "Kampanye kesehatan & sanitasi darurat", "d": "Cegah penyakit pasca-bencana, terutama di pengungsian."},
    ],
    3: [
        {"t": "Evakuasi dini & shelter terstruktur", "d": "Zonasi evakuasi, shelter permanen di luar zona bahaya, simulasi wajib."},
        {"t": "Sistem peringatan dini multi-bahaya", "d": "Integrasi sensor gempa, tsunami, cuaca ekstrem ke sirene desa."},
        {"t": "Mitigasi struktural prioritas", "d": "Tanggul, dam, atau retrofitting fasilitas vital sesuai jenis ancaman."},
        {"t": "Koordinasi lintas sektor 24/7", "d": "Pusat komando BNPB-BPBD-TNI-Polri dengan protokol respons cepat."},
        {"t": "Pendidikan risiko katastropik", "d": "Kurikulum khusus kesiapsiagaan bencana untuk warga di zona merah."},
    ],
}


def jumlah_rekomendasi() -> int:
    """Jumlah rekomendasi unik dalam basis aturan (untuk KPI halaman)."""
    items = [i["t"] for i in PER_TINGKAT.values()]
    items += [i["t"] for v in PER_JENIS.values() for i in v]
    items += [i["t"] for i in PER_KEPADATAN.values()]
    items += [i["t"] for v in PER_KLASTER.values() for i in v]
    return len(set(items))


def rekomendasi(kelas: int, kejadian: str, kepadatan: str | None, klaster: int | None, maks: int = 6) -> list[dict]:
    """Gabungkan rekomendasi dari keempat sumber, tanpa duplikat, paling banyak `maks` butir."""
    kandidat = [{**PER_TINGKAT[kelas], "sumber": "Tingkat dampak", "urgent": kelas >= 2}]
    kandidat += [{**i, "sumber": "Jenis bencana", "urgent": kelas == 3} for i in PER_JENIS.get(kejadian, [])]
    if kepadatan in PER_KEPADATAN:
        kandidat.append({**PER_KEPADATAN[kepadatan], "sumber": "Kepadatan penduduk",
                         "urgent": kepadatan != "Rendah" and kelas >= 2})
    if klaster is not None:
        kandidat += [{**i, "sumber": "Profil klaster", "urgent": klaster >= 2 and kelas >= 2}
                     for i in PER_KLASTER.get(klaster, [])[:2]]
    hasil, seen = [], set()
    for k in kandidat:
        if k["t"] not in seen:
            seen.add(k["t"])
            hasil.append(k)
    return hasil[:maks]
