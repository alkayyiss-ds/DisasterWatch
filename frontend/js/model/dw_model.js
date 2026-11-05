/* ============================================================
   DisasterWatch — Model Prediksi Dampak di browser (tanpa backend)
   ------------------------------------------------------------
   Menjalankan Random Forest yang sama dengan backend/app.py langsung di JavaScript.
   Butuh dua file data yang di-generate oleh `python backend/export_js_model.py`
   (otomatis ikut dijalankan oleh `python backend/export_static.py`):
     js/model/rf_forest.js  → window.DW_RF_FOREST  (300 pohon keputusan)
     js/model/dw_lookup.js  → window.DW_LOOKUP     (provinsi, riwayat, estimasi, klaster, aturan mitigasi)

   API:
     DWModel.prediksi(body)   ≈ POST /api/prediksi (keluaran sama persis)
       body = { jenis_bencana, provinsi, bulan, kepadatan? }
       → { tingkat, label, probabilitas[%], korban, terdampak, rusak, rentang, basis_estimasi, n_historis }
       Input tidak dikenal → melempar DWModel.InputError (setara HTTP 400).
     DWModel.mitigasi(tingkat, jenis, kepadatan, provinsi)
       → { klaster, rekomendasi[] }  aturan dari backend/mitigasi.py + klaster dominan provinsi
     DWModel.opsi()           → daftar jenis bencana, provinsi, bulan, kepadatan untuk dropdown
     DWModel.info()           → nama model, metrik, jumlah pohon
   ============================================================ */
(function (root) {
  'use strict';

  var ready = null;   // indeks & pohon yang sudah disiapkan (dibuat saat pertama dipakai)

  function InputError(message) {
    this.name = 'InputError';
    this.message = message;
    this.status = 400;
  }
  InputError.prototype = Object.create(Error.prototype);
  InputError.prototype.constructor = InputError;

  // ── Persiapan: indeks pencarian & pohon dalam typed array ───────────────────
  function init() {
    if (ready) return ready;
    var F = root.DW_RF_FOREST, L = root.DW_LOOKUP;
    if (!F || !L) throw new Error('Data model belum dimuat. Pastikan js/model/rf_forest.js dan js/model/dw_lookup.js dimuat sebelum dw_model.js.');

    var idx = {};
    F.fitur.nama.forEach(function (n, i) { idx[n] = i; });

    // Pohon: anak >= 0 → node internal, anak < 0 → daun ke-(~anak).
    // Peluang daun dihitung sama seperti scikit-learn: jumlah per kelas / total, lalu dinormalisasi lagi.
    var pohon = F.pohon.map(function (p) {
      var nDaun = p.v.length / 4, proba = new Float64Array(p.v.length);
      for (var d = 0; d < nDaun; d++) {
        var c = p.v.slice(d * 4, d * 4 + 4), w = c[0] + c[1] + c[2] + c[3];
        var q = c.map(function (x) { return x / w; });
        var s = q[0] + q[1] + q[2] + q[3];
        if (s === 0) s = 1;
        for (var k = 0; k < 4; k++) proba[d * 4 + k] = q[k] / s;
      }
      return { root: p.root, f: Int32Array.from(p.f), t: Float64Array.from(p.t),
               l: Int32Array.from(p.l), r: Int32Array.from(p.r), proba: proba };
    });

    // Indeks nama → sama dengan PROV_INDEX & JENIS_INDEX di backend/app.py (huruf besar)
    var provIndex = {}, jenisIndex = {};
    L.provinsi.forEach(function (p) {
      provIndex[String(p.provinsi).toUpperCase()] = p;
      provIndex[String(p.label).toUpperCase()] = p;
    });
    Object.keys(L.jenis_label).forEach(function (k) { jenisIndex[k] = k; });
    Object.keys(L.jenis_label).forEach(function (k) { jenisIndex[L.jenis_label[k].toUpperCase()] = k; });
    Object.keys(L.jenis_alias).forEach(function (a) { jenisIndex[a.toUpperCase()] = L.jenis_alias[a]; });

    ready = { F: F, L: L, idx: idx, nFitur: F.fitur.nama.length, pohon: pohon, provIndex: provIndex, jenisIndex: jenisIndex };
    return ready;
  }

  // ── Pembulatan seperti Python round(): nilai biner eksak, tepat di tengah → ke angka genap ──
  function pyRound(x, d) {
    d = d || 0;
    var full = x.toFixed(Math.min(100, d + 60));
    var dot = full.indexOf('.');
    if (/^50*$/.test(full.slice(dot + 1 + d))) {
      var kept = full.slice(0, d ? dot + 1 + d : dot);
      if (Number(kept.slice(-1)) % 2 === 0) return Number(kept);
      return Number((Number(kept) + (x < 0 ? -1 : 1) * Math.pow(10, -d)).toFixed(d));
    }
    return Number(x.toFixed(d));
  }

  // ── Fitur & Random Forest ───────────────────────────────────────────────────
  function barisFitur(kejadian, prov, bulan, tahun) {
    var R = ready, F = R.F, L = R.L, x = new Float64Array(R.nFitur);
    var kat = { kejadian: kejadian, region: prov.region, provinsi: prov.provinsi };
    Object.keys(F.fitur.kategorikal).forEach(function (kol) {
      var i = R.idx['cat__' + kol + '_' + kat[kol]];
      if (i !== undefined) x[i] = 1;                 // kategori tak dikenal → semua 0 (handle_unknown='ignore')
    });
    var pid = String(prov.id_prov), riw = L.riwayat;
    var hp = riw.prov[pid] || riw.empty, ht = riw.provtype[pid + '|' + kejadian] || riw.empty;
    var bf = F.bulan_fitur[bulan - 1];
    var num = {
      lon: prov.lon, lat: prov.lat,
      month_sin: bf.month_sin, month_cos: bf.month_cos, musim_hujan: bf.musim_hujan,
      year: tahun, era_2024: tahun >= 2024 ? 1 : 0,
      prov_log_n: hp.log_n, prov_sev_mean: hp.sev_mean, prov_berat_rate: hp.berat_rate,
      provtype_log_n: ht.log_n, provtype_sev_mean: ht.sev_mean, provtype_berat_rate: ht.berat_rate
    };
    F.fitur.numerik.forEach(function (kol) { x[R.idx['num__' + kol]] = num[kol]; });
    for (var i = 0; i < x.length; i++) x[i] = Math.fround(x[i]);   // scikit-learn membandingkan fitur dalam float32
    return x;
  }

  function predictProba(x) {
    var pohon = init().pohon, out = [0, 0, 0, 0];
    for (var p = 0; p < pohon.length; p++) {
      var tr = pohon[p], n = tr.root;
      while (n >= 0) n = x[tr.f[n]] <= tr.t[n] ? tr.l[n] : tr.r[n];
      var d = ~n * 4;
      for (var k = 0; k < 4; k++) out[k] += tr.proba[d + k];
    }
    return out.map(function (v) { return v / pohon.length; });
  }

  // ── Estimasi dampak (sama dengan cari_estimasi di backend/app.py) ────────────
  function cariEstimasi(pid, kejadian, tingkat) {
    var est = ready.L.estimasi, minN = ready.L.min_n_estimasi;
    var urutan = [['2024+', 'prov_jenis', pid + '|' + kejadian + '|' + tingkat, 'provinsi & jenis (2024+)'],
                  ['semua', 'prov_jenis', pid + '|' + kejadian + '|' + tingkat, 'provinsi & jenis (2015-sekarang)'],
                  ['2024+', 'jenis', kejadian + '|' + tingkat, 'jenis bencana nasional (2024+)'],
                  ['semua', 'jenis', kejadian + '|' + tingkat, 'jenis bencana nasional (2015-sekarang)']];
    for (var i = 0; i < urutan.length; i++) {
      var u = urutan[i], s = ((est[u[0]] || {})[u[1]] || {})[u[2]];
      if (s && (s.n || 0) >= minN) return { s: s, basis: u[3] };
    }
    return null;
  }

  // ── Input (aturan sama dengan backend/app.py) ───────────────────────────────
  function cariJenis(v) { return init().jenisIndex[String(v == null ? '' : v).trim().toUpperCase()]; }
  function cariProvinsi(v) { return init().provIndex[String(v == null ? '' : v).trim().toUpperCase()]; }
  function bacaBulan(v) {
    var b = String(v == null ? '' : v).trim(), BULAN = init().L.bulan;
    if (/^\d+$/.test(b) && +b >= 1 && +b <= 12) return +b;
    var cap = b.charAt(0).toUpperCase() + b.slice(1).toLowerCase();
    var i = BULAN.indexOf(cap);
    if (i < 0) throw new InputError('Bulan tidak dikenal: ' + v);
    return i + 1;
  }

  // ── API publik ──────────────────────────────────────────────────────────────
  function prediksi(body) {
    var R = init(), L = R.L;
    body = body || {};
    var kejadian = cariJenis(body.jenis_bencana);
    if (kejadian === undefined) throw new InputError('Jenis bencana tidak dikenal: ' + body.jenis_bencana);
    var prov = cariProvinsi(body.provinsi);
    if (!prov) throw new InputError('Provinsi tidak dikenal: ' + body.provinsi);
    var bulan = bacaBulan(body.bulan);
    var tahun = Math.max(new Date().getFullYear(), R.F.tahun_domain);

    var proba = predictProba(barisFitur(kejadian, prov, bulan, tahun));
    var tingkat = 0;
    for (var k = 1; k < proba.length; k++) if (proba[k] > proba[tingkat]) tingkat = k;   // argmax, ambil yang pertama

    var hasil = {
      tingkat: tingkat,
      label: L.kelas[tingkat],
      probabilitas: proba.map(function (p) { return pyRound(p * 100); }),
      korban: 0, terdampak: 0, rusak: 0, rentang: null,
      basis_estimasi: 'tidak ada data historis yang cukup',
      n_historis: 0
    };
    var hit = cariEstimasi(String(prov.id_prov), kejadian, tingkat);
    if (hit) {
      var s = hit.s, r = function (q, f) { return pyRound(s[q][f]); };
      hasil.korban = r('korban_jiwa', 'median');
      hasil.terdampak = r('terdampak', 'median');
      hasil.rusak = r('kerusakan', 'median');
      hasil.rentang = { korban: [r('korban_jiwa', 'p25'), r('korban_jiwa', 'p75')],
                        terdampak: [r('terdampak', 'p25'), r('terdampak', 'p75')],
                        rusak: [r('kerusakan', 'p25'), r('kerusakan', 'p75')] };
      hasil.basis_estimasi = hit.basis;
      hasil.n_historis = s.n;
    }
    return hasil;
  }

  function profilKlaster(idProv) {
    var k = init().L.klaster;
    if (!k || !k.tersedia) return null;
    var p = k.provinsi[String(idProv)];
    if (!p) return null;
    var nama = k.nama[String(p.dominan)];
    return { klaster: p.dominan, nama: nama.nama, pendek: nama.pendek, n_wilayah: p.n_wilayah, distribusi: p.distribusi };
  }

  /* Rekomendasi mitigasi berbasis aturan (port dari backend/mitigasi.py):
     tingkat dampak + jenis bencana + kepadatan penduduk + 2 butir dari klaster dominan provinsi. */
  function mitigasi(tingkat, jenis, kepadatan, provinsi, maks) {
    var M = init().L.mitigasi, kandidat = [];
    var kejadian = cariJenis(jenis), prov = cariProvinsi(provinsi);
    var klaster = prov ? profilKlaster(prov.id_prov) : null;
    maks = maks || 6;
    kandidat.push(Object.assign({}, M.per_tingkat[String(tingkat)], { sumber: 'Tingkat dampak', urgent: tingkat >= 2 }));
    (M.per_jenis[kejadian] || []).forEach(function (i) {
      kandidat.push(Object.assign({}, i, { sumber: 'Jenis bencana', urgent: tingkat === 3 }));
    });
    if (kepadatan && M.per_kepadatan[kepadatan]) {
      kandidat.push(Object.assign({}, M.per_kepadatan[kepadatan],
        { sumber: 'Kepadatan penduduk', urgent: kepadatan !== 'Rendah' && tingkat >= 2 }));
    }
    if (klaster) {
      (M.per_klaster[String(klaster.klaster)] || []).slice(0, 2).forEach(function (i) {
        kandidat.push(Object.assign({}, i, { sumber: 'Profil klaster', urgent: klaster.klaster >= 2 && tingkat >= 2 }));
      });
    }
    var hasil = [], seen = {};
    kandidat.forEach(function (k) { if (!seen[k.t]) { seen[k.t] = true; hasil.push(k); } });
    return { klaster: klaster, rekomendasi: hasil.slice(0, maks) };
  }

  function opsi() {
    var L = init().L;
    return {
      // urutan & cakupan sama dengan export_static.py (gabungan "Gempa bumi & tsunami" hanya 5 laporan → tidak ditampilkan)
      jenis: Object.keys(L.jenis_label).filter(function (k) { return k !== 'GEMPA BUMI DAN TSUNAMI'; })
                                        .map(function (k) { return { kode: k, label: L.jenis_label[k] }; }),
      provinsi: L.provinsi.map(function (p) { return { kode: p.provinsi, label: p.label, id_prov: p.id_prov }; }),
      bulan: L.bulan.slice(),
      kepadatan: L.kepadatan.slice()
    };
  }

  function info() {
    var R = init();
    return { versi: R.F.versi, nama_model: R.F.nama_model, n_pohon: R.F.n_pohon, tahun_domain: R.F.tahun_domain,
             n_fitur: R.F.fitur.nama.length, metrik: R.L.model };
  }

  root.DWModel = { prediksi: prediksi, mitigasi: mitigasi, opsi: opsi, info: info, predictProba: predictProba,
                   InputError: InputError, _pyRound: pyRound };
})(typeof window !== 'undefined' ? window : globalThis);
