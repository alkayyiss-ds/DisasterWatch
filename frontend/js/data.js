/* data.js — membaca data/*.json hasil export_static.py. Menggantikan backend FastAPI. */
(function (g) {
  'use strict';
  var BASE = 'data/', cache = {};
  var BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
  var BLN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
  var SEV = ['Tanpa Dampak', 'Ringan', 'Sedang', 'Berat'];

  function load(name) {
    return cache[name] || (cache[name] = fetch(BASE + name + '.json').then(function (r) {
      if (!r.ok) throw new Error('Gagal memuat ' + BASE + name + '.json (HTTP ' + r.status + '). Jalankan export_static.py dan buka lewat server.');
      return r.json();
    }));
  }
  function pct(cur, prev) { return prev === 0 ? null : Math.round((cur - prev) / prev * 1000) / 10; }
  function quant(sorted, q) {
    if (!sorted.length) return 0;
    var pos = (sorted.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  }
  function top(map, k) {
    return Object.keys(map).map(function (x) { return [+x, map[x]]; }).sort(function (a, b) { return b[1] - a[1]; }).slice(0, k);
  }

  function overview(q) {
    return Promise.all([load('meta'), load('agg'), load('kab')]).then(function (a) {
      var meta = a[0], A = a[1], K = a[2], last = meta.terakhir;
      var tahun = q.tahun || last.tahun, dari = q.dari || 0;
      var jk = meta.jenis.map(function (j) { return j.kode; }), pk = meta.provinsi.map(function (p) { return p.kode; });
      var okJ = function (j) { return q.jenis === 'semua' || jk[j] === q.jenis; };
      var okP = function (p) { return q.provinsi === 'semua' || pk[p] === q.provinsi; };
      var cut = tahun < last.tahun ? 12 : tahun === last.tahun ? last.bulan_lengkap : 0;

      var tot = 0, men = 0, rum = 0, mo = new Array(12).fill(0), byJ = {}, byP = {};
      var cur = { n: 0, m: 0, r: 0 }, prev = { n: 0, m: 0, r: 0 };
      for (var i = 0; i < A.y.length; i++) {
        if (!okJ(A.j[i]) || !okP(A.p[i])) continue;
        if (tahun > 0 && cut) {
          var tgt = A.y[i] === tahun && A.mo[i] <= cut ? cur : A.y[i] === tahun - 1 && A.mo[i] <= cut ? prev : null;
          if (tgt) { tgt.n += A.n[i]; tgt.m += A.m[i]; tgt.r += A.r[i]; }
        }
        if (tahun < 0 ? A.y[i] < dari : A.y[i] !== tahun) continue;
        tot += A.n[i]; men += A.m[i]; rum += A.r[i]; mo[A.mo[i] - 1] += A.n[i];
        byJ[A.j[i]] = (byJ[A.j[i]] || 0) + A.n[i]; byP[A.p[i]] = (byP[A.p[i]] || 0) + A.n[i];
      }
      var vals = Object.keys(byP).map(function (k) { return byP[k]; }).sort(function (x, y) { return x - y; });
      var q1 = quant(vals, 1 / 3), q2 = quant(vals, 2 / 3);
      var peta = [];
      Object.keys(byP).forEach(function (k) {
        var p = meta.provinsi[k]; if (p.lat == null || p.lng == null) return;
        var n = byP[k]; peta.push({ nama: p.label, lat: p.lat, lng: p.lng, n: n, risiko: n >= q2 ? 'tinggi' : n >= q1 ? 'sedang' : 'rendah' });
      });
      var kab = {};
      var idp = q.provinsi === 'semua' ? null : meta.provinsi[pk.indexOf(q.provinsi)].id_prov;
      for (var s = 0; s < K.y.length; s++) {
        if (!okJ(K.j[s]) || (idp !== null && K.kab[K.k[s]].prov !== idp)) continue;
        if (tahun < 0 ? K.y[s] < dari : K.y[s] !== tahun) continue;
        kab[K.k[s]] = (kab[K.k[s]] || 0) + K.n[s];
      }
      var hasTrend = tahun > 0 && cut > 0;
      return {
        tahun: tahun, pembanding: hasTrend ? 'Jan–' + BLN[cut - 1] : '',
        kpi: { total: tot, meninggal: men, rumah: rum, prov: Object.keys(byP).length },
        trend: { total: hasTrend ? pct(cur.n, prev.n) : null, meninggal: hasTrend ? pct(cur.m, prev.m) : null, rumah: hasTrend ? pct(cur.r, prev.r) : null },
        monthly: { labels: BLN, values: mo },
        komposisi: { labels: top(byJ, 99).map(function (x) { return meta.jenis[x[0]].label; }), values: top(byJ, 99).map(function (x) { return x[1]; }) },
        topProvinsi: top(byP, 5).map(function (x) { return { provinsi: meta.provinsi[x[0]].label, jumlah_kejadian: x[1] }; }),
        petaTitik: peta,
        topKab: top(kab, 5).map(function (x) { return { nama: K.kab[x[0]].nama, n: x[1] }; })
      };
    });
  }

  function dashboard() {
    return load('meta').then(function (m) {
      return { kpi: { akurasi: m.akurasi == null ? 0 : Math.round(m.akurasi * 1000) / 10, wilayah: m.wilayah }, feature: m.faktor };
    });
  }
  function extra() { return load('extra'); }
  function laporan() { return load('laporan'); }

  function tren(q) {
    return load('tren').then(function (T) {
      var seri = (q.seri || 'NASIONAL').toUpperCase(), S = T.seri[seri];
      if (!S) throw new Error('Seri tidak dikenal: ' + seri);
      var best = S.models.filter(function (m) { return m.terbaik; })[0];
      var row = q.model === 'auto' ? best : S.models.filter(function (m) { return m.kode === q.model; })[0];
      if (!row) throw new Error('Model tidak ada untuk ' + seri + ': ' + q.model);
      var h = Math.max(1, q.horizon || 12), cut = function (o) { var r = {}; Object.keys(o).forEach(function (k) { r[k] = o[k].slice(0, h); }); return r; };
      return {
        seri: seri, nama: S.nama, rata: S.rata, kecil: S.kecil,
        opsi: { seri: T.opsi, model: [{ kode: 'auto', label: 'Otomatis (terbaik)' }].concat(S.models.map(function (m) { return { kode: m.kode, label: m.label }; })) },
        model: { kode: row.kode, label: row.label, terbaik: row.terbaik, terbaik_label: best.label, mae: row.mae, rmse: row.rmse, mape: row.mape },
        tabel: S.models.slice().sort(function (a, b) { return a.mae - b.mae; }).map(function (m) { return { label: m.label, mae: m.mae, rmse: m.rmse, mape: m.mape, terbaik: m.terbaik }; }),
        aktual: S.aktual, uji: row.uji, prediksi: cut(row.fc), musiman: S.musiman
      };
    });
  }

  /* Prediksi Dampak: model Random Forest dijalankan langsung di browser (js/model/dw_model.js).
     Jika file model tidak dimuat, pakai tabel hasil model yang sudah dihitung (data/prediksi.json). */
  function prediksi(b) {
    if (g.DWModel) return Promise.resolve().then(function () { return g.DWModel.prediksi(b); });
    return load('prediksi').then(function (P) {
      var bn = BULAN.indexOf(b.bulan) + 1;
      var e = bn ? P[b.jenis_bencana + '|' + b.provinsi + '|' + bn] : null;
      if (!e) throw new Error('Kombinasi tidak tersedia: ' + b.jenis_bencana + ' / ' + b.provinsi + ' / ' + b.bulan);
      return {
        tingkat: e.t, label: SEV[e.t], probabilitas: e.p,
        korban: e.e ? e.e[0] : 0, terdampak: e.e ? e.e[1] : 0, rusak: e.e ? e.e[2] : 0,
        rentang: e.g ? { korban: [e.g[0], e.g[1]], terdampak: [e.g[2], e.g[3]], rusak: [e.g[4], e.g[5]] } : null,
        basis_estimasi: e.b, n_historis: e.n
      };
    });
  }

  g.DW = { overview: overview, dashboard: dashboard, extra: extra, laporan: laporan, tren: tren, prediksi: prediksi };
})(typeof window !== 'undefined' ? window : globalThis);