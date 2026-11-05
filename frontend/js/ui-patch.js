/* ui-patch.js — perbaikan UI/UX tanpa mengubah ID yang dipakai app.js (muat SETELAH app.js) */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var PROVINSI = ["Aceh","Bali","Banten","Bengkulu","DI Yogyakarta","DKI Jakarta","Gorontalo","Jambi","Jawa Barat",
    "Jawa Tengah","Jawa Timur","Kalimantan Barat","Kalimantan Selatan","Kalimantan Tengah","Kalimantan Timur",
    "Kalimantan Utara","Kepulauan Bangka Belitung","Kepulauan Riau","Lampung","Maluku","Maluku Utara",
    "Nusa Tenggara Barat","Nusa Tenggara Timur","Papua","Papua Barat","Papua Barat Daya","Papua Pegunungan",
    "Papua Selatan","Papua Tengah","Riau","Sulawesi Barat","Sulawesi Selatan","Sulawesi Tengah",
    "Sulawesi Tenggara","Sulawesi Utara","Sumatera Barat","Sumatera Selatan","Sumatera Utara"];
  var JENIS = ["Banjir","Cuaca ekstrem","Tanah longsor","Karhutla","Kekeringan","Gempa bumi",
    "Gelombang pasang & abrasi","Erupsi gunung api","Tsunami"];

  function fillSelect(id, items) {
    var sel = document.getElementById(id);
    if (!sel) return;
    var cur = sel.value;
    sel.innerHTML = '';
    items.forEach(function (t) { var o = document.createElement('option'); o.textContent = t; sel.appendChild(o); });
    if (items.indexOf(cur) > -1) sel.value = cur;
  }

  var JENIS_KODE = ["BANJIR","CUACA EKSTREM","TANAH LONGSOR","KEBAKARAN HUTAN DAN LAHAN","KEKERINGAN","GEMPABUMI",
    "GELOMBANG PASANG DAN ABRASI","ERUPSI GUNUNG API","TSUNAMI"];
  function fillKV(id, pairs) {
    var sel = document.getElementById(id); if (!sel) return;
    var cur = sel.value; sel.innerHTML = '';
    pairs.forEach(function (p) { var o = document.createElement('option'); o.value = p[0]; o.textContent = p[1]; sel.appendChild(o); });
    if (cur) sel.value = cur;
  }
  function fixFilters() {
    var jn = [["semua", "Semua bencana"]].concat(JENIS.map(function (n, i) { return [JENIS_KODE[i], n]; }));
    var pv = [["semua", "Semua provinsi"]].concat(PROVINSI.map(function (n) {
      return [n === "DI Yogyakarta" ? "DAERAH ISTIMEWA YOGYAKARTA" : n.toUpperCase(), n]; }));
    fillKV('f-jenis', jn); fillKV('map-filter-jenis', jn); fillKV('f-prov', pv);
  }

  function fixPrediksiForm() {
    fixFilters();
    fillSelect('sim-jenis', JENIS);    // semua jenis yang dikenal model
    fillSelect('sim-prov', PROVINSI);  // 38 provinsi, bukan hanya 6
  }

  function fixTren() {
    var p = $('#p-tren'); if (!p) return;
    // hapus gaya inline & penanda nomor dari catatan desain
    $$('.filterbar, .filter-group, .filter-group label, .filter-group select', p).forEach(function (e) { e.removeAttribute('style'); });
    $$('.filter-group label span', p).forEach(function (s) { s.remove(); });
    $$('h3 > span', p).forEach(function (s) { s.remove(); });
    $$('p', p).forEach(function (e) { if (/^Interaksi diharapkan/.test(e.textContent.trim())) e.remove(); else if (/^Tinggi batang/.test(e.textContent.trim())) e.textContent = 'Rata-rata laporan per bulan.'; });
    // catatan jenis frekuensi rendah: tampil hanya jika relevan
    var alert = $('.alert-card', p), jenis = $('.filter-group select', p);
    if (alert) {
      var b = $('b', alert); if (b) b.textContent = 'Catatan: jenis bencana berfrekuensi rendah';
      alert.hidden = true;
      if (jenis) jenis.addEventListener('change', function () {
        alert.hidden = !/tsunami|erupsi|gempa|kekeringan|gelombang/i.test(jenis.value);
      });
    }
  }

  function fixPengaturan() {
    $$('#p-pengaturan .setting-item').forEach(function (it) {
      var t = it.textContent;
      if (/Notifikasi Bencana Dini/.test(t)) { it.remove(); return; }   // tidak ada pengirim email di backend
      if (/Auto-refresh/.test(t)) {
        var b = $('b', it), d = $('span', it), i = $('input', it);
        if (b) b.textContent = 'Muat ulang data berkala';
        if (d) d.textContent = 'Ambil ulang data dari backend setiap 5 menit.';
        if (i) i.id = 'set-autorefresh';
      }
    });
    var last = $$('#p-pengaturan .setting-item').pop(); if (last) last.style.borderBottom = 'none';
  }

  function fixNotif() {
    var body = $('.notif-body'), dot = $('#btn-notif .dot'), btn = $('#btn-notif');
    if (!body) return;
    var items = [
      ['INFO DATA', 'Data BNPB tersedia sampai 28 Oktober 2026.'],
      ['CATATAN', 'Oktober 2026 belum lengkap, jadi tidak dipakai dalam analisis tren.']
    ];
    var trash = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';
    body.innerHTML = items.map(function (i) {
      return '<div class="notif-item unread"><div class="notif-dot"></div><div class="notif-content"><b>' + i[0] +
        '</b><p>' + i[1] + '</p></div><button type="button" class="notif-trash" aria-label="Hapus notifikasi">' + trash + '</button></div>';
    }).join('');
    function emptyCheck() {
      if (!$('.notif-item', body)) body.innerHTML = '<div class="notif-empty">Tidak ada pemberitahuan.</div>';
      if (dot && !$('.notif-item.unread', body)) dot.style.display = 'none';
    }
    body.addEventListener('click', function (e) {
      var t = e.target.closest('.notif-trash');
      if (t) { var it = t.closest('.notif-item'); if (it) it.remove(); emptyCheck(); }
    });
    if (btn) btn.addEventListener('click', function () {   // dianggap terbaca saat panel dibuka
      setTimeout(function () {
        $$('.notif-item.unread', body).forEach(function (n) { n.classList.remove('unread'); var d = $('.notif-dot', n); if (d) d.remove(); });
        if (dot) dot.style.display = 'none';
      }, 50);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { var c = $('#close-notif'); var pnl = $('#notif-panel'); if (c && pnl && pnl.style.display !== 'none') c.click(); }
    });
  }

  // Peta abu-abu & grafik 0-ukuran terjadi karena dibuat saat tab tersembunyi → paksa hitung ulang ukuran
  function refreshLayout() {
    [60, 350, 800].forEach(function (ms) { setTimeout(function () { window.dispatchEvent(new Event('resize')); }, ms); });
  }

  // Beri penjelasan pada grafik yang kosong, bukan sumbu 0–1 tanpa isi
  function markEmptyCharts() {
    if (typeof Chart === 'undefined' || !Chart.getChart) return;
    $$('.chart-wrap canvas').forEach(function (cv) {
      var wrap = cv.parentElement, ch = Chart.getChart(cv), old = $('.chart-empty', wrap);
      var empty = !ch || ch.data.datasets.every(function (d) {
        return !d.data || !d.data.length || d.data.every(function (v) { return !v; });
      });
      if (empty && !old) {
        var d = document.createElement('div'); d.className = 'chart-empty';
        d.innerHTML = '<b>Data belum tersedia</b><span>Grafik ini belum menerima data dari server atau berkas data.</span>';
        wrap.appendChild(d);
      } else if (!empty && old) old.remove();
    });
  }

  window.markEmptyCharts = markEmptyCharts;

  function init() {
    fixPrediksiForm(); fixTren(); fixNotif(); fixPengaturan();
    $$('.nav-item').forEach(function (n) {
      n.addEventListener('click', function () {
        $$('.nav-item').forEach(function (x) { x.removeAttribute('aria-current'); });
        n.setAttribute('aria-current', 'page');
        window.scrollTo({ top: 0 });
        var m = $('.main'); if (m && m.scrollTo) m.scrollTo({ top: 0 });
        refreshLayout();
        setTimeout(markEmptyCharts, 900);
      });
    });
    var on = $('.nav-item.on'); if (on) on.setAttribute('aria-current', 'page');
    setTimeout(markEmptyCharts, 1500);
    refreshLayout();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();