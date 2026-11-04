/* ============================================================
   DisasterWatch — ALL IN ONE SCRIPT (v6 FINAL)
   ============================================================ */
(function () {
  'use strict';

  var charts = {};
  var petaUtama = null; 
  var petaWilayah = null;

  // ==========================================
  // BACKEND API — PREDIKSI DAMPAK (Random Forest)
  // Saat dashboard dibuka dari server backend (http://localhost:8000) API dipanggil di origin yang sama.
  // Saat dibuka langsung dari file atau server lain (mis. Live Server), API dipanggil ke localhost:8000.
  // Ubah dengan mendefinisikan window.DW_API_BASE sebelum app.js dimuat bila backend berjalan di alamat lain.
  // ==========================================
  var API_BASE = window.DW_API_BASE || (location.protocol !== 'file:' && location.port === '8000' ? '' : 'http://localhost:8000');
  var FAKTOR = null;          // faktor risiko dominan dari /api/prediksi/meta
  var simTimer = null;        // debounce perubahan dropdown
  var simSeq = 0;             // abaikan respons lama bila pengguna mengganti pilihan dengan cepat
  var KLASTER_PILL = { 0: 'green', 1: 'blue', 2: 'orange', 3: 'red' };

  function apiGet(path) {
    return fetch(API_BASE + path).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
  }
  function apiPost(path, body) {
    return fetch(API_BASE + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.detail ? JSON.stringify(j.detail) : 'HTTP ' + r.status); return j; }); });
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function setText(id, txt) { var el = document.getElementById(id); if (el) el.textContent = txt; }

  function fillSelect(el, items) {
    // items: [{value, label}] — pertahankan pilihan saat ini (dicocokkan lewat label atau value)
    if (!el || !items || !items.length) return;
    var cur = (el.value || '').toLowerCase();
    var html = '', found = false;
    items.forEach(function (it) {
      var sel = !found && (String(it.value).toLowerCase() === cur || String(it.label).toLowerCase() === cur);
      if (sel) found = true;
      html += '<option value="' + esc(it.value) + '"' + (sel ? ' selected' : '') + '>' + esc(it.label) + '</option>';
    });
    el.innerHTML = html;
  }

  function showSimStatus(msg) {
    var el = document.getElementById('sim-status');
    if (!el) return;
    if (msg) { el.innerHTML = msg; el.hidden = false; } else { el.hidden = true; el.innerHTML = ''; }
  }

  function backendOfflineMsg() {
    return '<b>Backend prediksi belum terhubung.</b> Jalankan dari folder repo: <code>uvicorn backend.app:app --port 8000</code>, ' +
           'lalu buka <code>http://localhost:8000</code>.';
  }

  function loadPrediksiMeta() {
    return apiGet('/api/prediksi/meta').then(function (m) {
      fillSelect(document.getElementById('sim-jenis'), m.opsi.jenis_bencana);
      fillSelect(document.getElementById('sim-prov'), m.opsi.provinsi);
      fillSelect(document.getElementById('sim-bulan'), m.opsi.bulan);

      setText('kpi-akurasi', m.kpi.akurasi.toFixed(2).replace('.', ','));
      setText('kpi-wilayah', m.kpi.wilayah_terklasifikasi.toLocaleString('id-ID'));
      setText('kpi-tingkat', m.kpi.tingkat_risiko);
      setText('kpi-rekomendasi', m.kpi.rekomendasi_mitigasi);
      var mb = document.getElementById('model-badge');
      if (mb) mb.title = 'Akurasi ' + m.model.metrik.accuracy.toFixed(3) + ' · balanced accuracy ' + m.model.metrik.balanced_accuracy.toFixed(3) +
                         ' · MSE ' + m.model.metrik.mse.toFixed(4) + ' · data uji ' + m.model.metrik.n_uji.toLocaleString('id-ID') + ' laporan';

      FAKTOR = m.faktor_risiko;
      if (charts.feature) {
        charts.feature.data.labels = FAKTOR.map(function (f) { return f.faktor; });
        charts.feature.data.datasets[0].data = FAKTOR.map(function (f) { return Math.round(f.bobot * 1000) / 10; });
        charts.feature.update();
      }

      var tb = document.getElementById('klaster-ringkasan');
      if (tb && m.klaster.ringkasan.length) {
        tb.innerHTML = m.klaster.ringkasan.map(function (k) {
          return '<tr><td><span class="pill ' + (KLASTER_PILL[k.klaster] || 'blue') + '">' + esc(k.pendek) + '</span></td><td>' +
                 k.jumlah_wilayah.toLocaleString('id-ID') + '</td></tr>';
        }).join('');
        setText('klaster-sub', m.klaster.total_wilayah.toLocaleString('id-ID') + ' kab/kota unik per klaster risiko (K-Means)');
      }
      return m;
    });
  }

  function setupCharts() {
    if (typeof Chart === 'undefined') return;
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
    Chart.defaults.font.size = 11.5;
    Chart.defaults.color = '#667085';
    Chart.defaults.borderColor = '#F2F4F7';
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.plugins.tooltip.backgroundColor = '#0F1B2D';
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.titleFont = { size: 12, weight: '700' };
    Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
    Chart.defaults.plugins.tooltip.displayColors = false;
    Chart.defaults.animation.duration = 700;
  }

  function drawMonthly(data, label) {
    var ctx = document.getElementById('c-monthly');
    if (!ctx) return;
    var grad = ctx.getContext('2d').createLinearGradient(0, 0, 0, 280);
    grad.addColorStop(0, 'rgba(46,117,182,.25)');
    grad.addColorStop(1, 'rgba(46,117,182,0)');
    if (charts.monthly) charts.monthly.destroy();
    charts.monthly = new Chart(ctx, {
      type: 'line',
      data: {
        labels: ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'],
        datasets: [{ label: label || 'Kejadian 2026', data: data, borderColor: '#2E75B6', backgroundColor: grad, borderWidth: 2.5, pointBackgroundColor: '#fff', pointBorderColor: '#2E75B6', pointBorderWidth: 2.5, pointRadius: 4, pointHoverRadius: 6, tension: .35, fill: true }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
        plugins: { tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + c.parsed.y + ' kejadian'; } } } },
        scales: { x: { grid: { display: false }, ticks: { font: { size: 11, weight: '600' } } }, y: { beginAtZero: true, grid: { color: '#F2F4F7' }, ticks: { font: { size: 11 } } } }
      }
    });
  }

  function drawKomposisi(dataKomposisi) {
    var ctx = document.getElementById('c-komposisi');
    if (!ctx) return;
    var labels = dataKomposisi ? dataKomposisi.labels : (window.DATA_ASLI ? window.DATA_ASLI.komposisi.labels : []);
    var data = dataKomposisi ? dataKomposisi.data : (window.DATA_ASLI ? window.DATA_ASLI.komposisi.data : []);
    if (charts.komposisi) charts.komposisi.destroy();
    charts.komposisi = new Chart(ctx, {
      type: 'doughnut',
      data: { labels: labels, datasets: [{ data: data, backgroundColor: ['#FB5607','#3A86FF','#6C8EAD','#E9C46A','#8D6E63','#8338EC','#2A9D8F'], borderWidth: 0, hoverOffset: 8 }] },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '62%',
        plugins: {
          legend: { display: true, position: 'right', labels: { boxWidth: 10, boxHeight: 10, padding: 12, font: { size: 11.5, weight: '600' }, usePointStyle: true, pointStyle: 'rectRounded' } },
          tooltip: { callbacks: { label: function (c) { var total = data.reduce(function(a,b){return a+b;}, 0); return c.label + ': ' + c.parsed + ' (' + (c.parsed / total * 100).toFixed(1) + '%)'; } } }
        }
      }
    });
  }

  function drawOtherCharts() {
    var ctxD = document.getElementById('c-dominan');
    if (ctxD) {
      if (charts.dominan) charts.dominan.destroy();
      charts.dominan = new Chart(ctxD, {
        type: 'bar',
        data: { labels: ['Jawa Tengah','Jawa Timur','Jawa Barat','Sulawesi Selatan','Sulawesi Tengah'], datasets: [{ label: 'Banjir', data: [216,55,94,62,30], backgroundColor: '#3A86FF', borderRadius: 0, barThickness: 24 },{ label: 'Karhutla', data: [118,179,59,29,12], backgroundColor: '#FB5607', borderRadius: 0, barThickness: 24 },{ label: 'Tanah longsor', data: [59,42,83,53,68], backgroundColor: '#8D6E63', borderRadius: 0, barThickness: 24 }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 10, boxHeight: 10, padding: 14, font: { size: 11.5, weight: '600' }, usePointStyle: true, pointStyle: 'rectRounded' } } }, scales: { x: { stacked: true, grid: { color: '#F2F4F7' }, ticks: { font: { size: 11 } } }, y: { stacked: true, grid: { display: false }, ticks: { font: { size: 11.5, weight: '600' } } } } }
      });
    }

    var ctxF = document.getElementById('c-feature');
    if (ctxF) {
      if (charts.feature) charts.feature.destroy();
      // Data diisi dari /api/prediksi/meta (permutation importance model Random Forest)
      charts.feature = new Chart(ctxF, {
        type: 'bar',
        data: { labels: FAKTOR ? FAKTOR.map(function (f) { return f.faktor; }) : [],
                datasets: [{ data: FAKTOR ? FAKTOR.map(function (f) { return Math.round(f.bobot * 1000) / 10; }) : [],
                             backgroundColor: '#2E75B6', borderRadius: 6, barThickness: 18 }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: false },
                   tooltip: { callbacks: { label: function (c) { return c.parsed.x.toLocaleString('id-ID') + '% kontribusi'; } } } },
                   scales: { x: { beginAtZero: true, grid: { color: '#F2F4F7' }, ticks: { callback: function (v) { return v + '%'; } } }, y: { grid: { display: false } } } }
      });
    }

    var ctxC = document.getElementById('c-cluster-impact');
    if (ctxC) {
      if (charts.clusterImpact) charts.clusterImpact.destroy();
      charts.clusterImpact = new Chart(ctxC, {
        type: 'bar',
        data: { labels: ['Risiko Rendah','Multi-Bencana','Kemanusiaan Akut','Katastropik'], datasets: [{ label: 'Rata-rata Korban Jiwa', data: [0.07, 0.29, 0.38, 99.85], backgroundColor: '#D92D20', borderRadius: 6, barThickness: 22 }, { label: 'Rata-rata Terdampak', data: [45, 2563, 6817, 23422], backgroundColor: '#2E75B6', borderRadius: 6, barThickness: 22 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 10, boxHeight: 10, padding: 14, font: { size: 11.5, weight: '600' }, usePointStyle: true, pointStyle: 'rectRounded' } }, tooltip: { callbacks: { label: function (c) { var v = c.parsed.y; return c.dataset.label + ': ' + (v >= 1000 ? v.toLocaleString('id-ID') : v); } } } }, scales: { x: { grid: { display: false }, ticks: { font: { size: 11.5, weight: '600' } } }, y: { type: 'logarithmic', beginAtZero: false, grid: { color: '#F2F4F7' }, title: { display: true, text: 'Skala logaritmik' } } } }
      });
    }

    var ctxFo = document.getElementById('c-forecast');
    if (ctxFo) {
      if (charts.forecast) charts.forecast.destroy();
      var labels = []; for(let i=1; i<=12; i++) labels.push('2025-'+i.toString().padStart(2,'0')); for(let i=1; i<=12; i++) labels.push('2026-'+i.toString().padStart(2,'0')); for(let i=1; i<=12; i++) labels.push('2027-'+i.toString().padStart(2,'0'));
      var actualData = [471,391,423,164,233,181,351,279,205,215,277,247, 287,183,217,192,166,121,247,319,345,259, null, null].concat(new Array(12).fill(null));
      var testPredData = new Array(10).fill(null).concat([250,257,361,361,359,193,231,173,272,236,224,258]).concat(new Array(12).fill(null));
      var forecastData = new Array(22).fill(null).concat([254,238,272,187,233,183,146,141,218,292,284,244]);
      var upperData = new Array(22).fill(null).concat([421,405,439,354,401,350,313,308,385,459,451,412]);
      var lowerData = new Array(22).fill(null).concat([86,71,104,19,66,15,0,0,51,124,116,77]);

      charts.forecast = new Chart(ctxFo, {
        type: 'line', data: { labels: labels, datasets: [ { label: 'Batas Atas', data: upperData, borderColor: 'transparent', backgroundColor: 'rgba(58,134,255,0.1)', fill: '+1', pointRadius: 0 }, { label: 'Batas Bawah', data: lowerData, borderColor: 'transparent', backgroundColor: 'transparent', fill: false, pointRadius: 0 }, { label: 'Aktual', data: actualData, borderColor: '#1F3A5F', borderWidth: 2, pointRadius: 0, tension: 0.3 }, { label: 'Prediksi Uji', data: testPredData, borderColor: '#3A86FF', borderWidth: 2, borderDash: [5, 5], pointRadius: 0, tension: 0.3 }, { label: 'Ramalan Depan', data: forecastData, borderColor: '#3A86FF', borderWidth: 2, borderDash: [2, 3], pointRadius: 0, tension: 0.3 } ] },
        options: { responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c) { if (c.parsed.y === null) return null; return c.dataset.label + ': ' + c.parsed.y; } } } }, scales: { x: { grid: { display: false }, ticks: { font: { size: 10 }, maxTicksLimit: 10 } }, y: { beginAtZero: true, grid: { color: '#F2F4F7' }, ticks: { font: { size: 11 } } } } }
      });
    }

    var ctxSe = document.getElementById('c-seasonal');
    if (ctxSe) {
      if (charts.seasonal) charts.seasonal.destroy();
      charts.seasonal = new Chart(ctxSe, { type: 'bar', data: { labels: ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'], datasets: [{ data: [452.09, 482.36, 411.36, 279.45, 221.18, 195.27, 243.36, 257.45, 287.0, 310.64, 337.64, 330.55], backgroundColor: '#93B5E1', borderRadius: 4, barThickness: 18 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false }, ticks: {font: {size: 10}} }, y: { beginAtZero: true, grid: { color: '#F2F4F7' } } } } });
    }
  }

  function initAllCharts() { setupCharts(); var monthlyData = (window.DATA_ASLI && window.DATA_ASLI.monthly) ? window.DATA_ASLI.monthly : [0,0,0,0,0,0,0,0,0,0,0,0]; drawMonthly(monthlyData, 'Kejadian 2026'); drawKomposisi(); drawOtherCharts(); }
  function resizeAllCharts() { Object.values(charts).forEach(function (c) { if (c && c.resize) c.resize(); }); }

  var dataFilters = {
    '2026': { total: 44280, meninggal: 11795, rumah: '1,4 jt', prov: 78, monthly: [210,148,172,160,138,104,196,268,345,178,240,190], komposisi: { labels: ['Banjir', 'Cuaca Ekstrem', 'Tanah Longsor', 'Karhutla', 'Gempa'], data: [45, 25, 15, 10, 5] } },
    '2025': { total: 41000, meninggal: 10000, rumah: '1,1 jt', prov: 78, monthly: [180,130,150,140,120,90,180,220,300,160,200,170], komposisi: { labels: ['Banjir', 'Cuaca Ekstrem', 'Tanah Longsor', 'Karhutla', 'Gempa'], data: [40, 28, 12, 15, 5] } },
    '2024': { total: 38500, meninggal: 9500, rumah: '0,9 jt', prov: 78, monthly: [150,110,140,130,110,80,150,200,280,140,180,150], komposisi: { labels: ['Banjir', 'Cuaca Ekstrem', 'Tanah Longsor', 'Karhutla', 'Gempa'], data: [35, 30, 10, 20, 5] } }
  };

  function updateOverview(year) {
    var d = dataFilters[year] || dataFilters['2026'];
    animateValue(document.getElementById('kpi-total'), 0, d.total, 800, true);
    animateValue(document.getElementById('kpi-meninggal'), 0, d.meninggal, 800, true);
    document.getElementById('kpi-rumah').textContent = d.rumah;
    document.getElementById('kpi-prov').textContent = d.prov;
    drawMonthly(d.monthly, 'Kejadian ' + year);
    drawKomposisi(d.komposisi);
  }

  function updateSim() {
    clearTimeout(simTimer);
    simTimer = setTimeout(runPrediksi, 150);
  }

  function runPrediksi() {
    var val = function (id, d) { var el = document.getElementById(id); return el && el.value ? el.value : d; };
    var body = { jenis_bencana: val('sim-jenis', 'Banjir'), provinsi: val('sim-prov', 'Jawa Tengah'),
                 bulan: val('sim-bulan', 'Januari'), kepadatan_penduduk: val('sim-kepadatan', 'Sedang') };
    var seq = ++simSeq;
    var box = document.getElementById('sim-result');
    if (box) box.classList.add('loading');
    apiPost('/api/prediksi', body).then(function (r) {
      if (seq !== simSeq) return;               // ada permintaan yang lebih baru
      showSimStatus(null);
      renderPrediksi(r);
    }).catch(function (err) {
      if (seq !== simSeq) return;
      var offline = err instanceof TypeError;   // fetch gagal = server tidak bisa dihubungi
      showSimStatus(offline ? backendOfflineMsg() : '<b>Prediksi gagal:</b> ' + esc(err.message));
      setText('sim-val', 'Prediksi tidak tersedia');
      var sb = document.getElementById('sim-bar'); if (sb) sb.style.width = '0%';
      ['sim-korban', 'sim-terdampak', 'sim-rusak'].forEach(function (id) { setText(id, '–'); setText(id + '-d', ''); });
      setText('sim-basis', ''); setText('sim-proba', '');
      var bd = document.getElementById('mitigasi-badge'); if (bd) { bd.className = 'pill'; bd.textContent = '–'; }
      var ml = document.getElementById('mitigation-list'); if (ml) ml.innerHTML = '';
    }).then(function () { if (box) box.classList.remove('loading'); });
  }

  function renderPrediksi(r) {
    var p = r.prediksi, e = r.estimasi, k = r.klaster_provinsi, inp = r.input;
    var pct = Math.round(p.probabilitas * 100);
    setText('sim-val', p.kelas + ' · ' + pct + '%');
    var sb = document.getElementById('sim-bar'); if (sb) sb.style.width = pct + '%';

    var pr = document.getElementById('sim-proba');
    if (pr) pr.innerHTML = p.peluang.map(function (x) {
      return '<span class="' + (x.kode === p.kode ? 'on' : '') + '">' + esc(x.kelas) + ' ' + Math.round(x.p * 100) + '%</span>';
    }).join('');

    if (e && e.tersedia) {
      setText('sim-korban', e.korban_jiwa.teks); setText('sim-korban-d', e.korban_jiwa.detail);
      setText('sim-terdampak', e.terdampak.teks); setText('sim-terdampak-d', e.terdampak.detail);
      setText('sim-rusak', e.kerusakan.teks); setText('sim-rusak-d', e.kerusakan.detail);
      setText('sim-basis', 'Estimasi = ' + e.basis.charAt(0).toLowerCase() + e.basis.slice(1) + '.');
    } else {
      ['sim-korban', 'sim-terdampak', 'sim-rusak'].forEach(function (id) { setText(id, '–'); setText(id + '-d', ''); });
      setText('sim-basis', e ? e.basis : '');
    }

    var badge = document.getElementById('mitigasi-badge');
    if (badge) { badge.className = 'pill ' + p.badge.warna; badge.textContent = p.badge.teks; }
    setText('mitigasi-sub', (k ? 'Klaster ' + k.klaster + ' — ' + k.pendek.replace(/^Tingkat [IV]+ - /, '') + ' · ' : '') +
                            inp.provinsi_label + ' · ' + inp.bulan_label + ' · prediksi ' + p.kelas);

    var list = document.getElementById('mitigation-list');
    if (list) list.innerHTML = r.mitigasi.map(function (m, i) {
      return '<li class="' + (m.urgent ? 'urgent' : '') + '"><span class="m-icon">' + (i + 1) + '</span><div><b>' + esc(m.t) +
             '<span class="m-src">' + esc(m.sumber) + '</span></b><span style="font-size:12.5px;color:var(--muted);">' + esc(m.d) + '</span></div></li>';
    }).join('');
  }

  function initMap(elementId, zoom) {
    var el = document.getElementById(elementId); if (!el || !window.L) return null;
    var map = L.map(elementId).setView([-2.5489, 118.0149], zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors', maxZoom: 19 }).addTo(map);
    if (window.DATA_ASLI && window.DATA_ASLI.map_points) {
      window.DATA_ASLI.map_points.forEach(function(p) {
        var color = p.jenis.indexOf('BANJIR') >= 0 ? '#3A86FF' : p.jenis.indexOf('KEBAKARAN') >= 0 ? '#FB5607' : p.jenis.indexOf('CUACA') >= 0 ? '#E9C46A' : '#2A9D8F';
        var popup = '<div style="font-family:Inter,sans-serif;padding:2px 4px;"><b style="color:' + color + ';font-size:13.5px;">' + p.jenis + '</b><br><span style="color:#667085;font-size:12px;">' + p.prov + '</span></div>';
        var marker = L.circleMarker([p.lat, p.lng], { radius: 8, fillColor: color, color: '#fff', weight: 2, fillOpacity: 0.9, opacity: 1 }).addTo(map).bindPopup(popup);
        marker._jenis = p.jenis.toLowerCase();
      });
    }
    return map;
  }

  function animateValue(obj, start, end, duration, formatted) {
    if (!obj) return;
    var startTs = null;
    function step(ts) {
      if (!startTs) startTs = ts;
      var p = Math.min((ts - startTs) / duration, 1);
      var val = Math.floor(p * (end - start) + start);
      obj.innerHTML = formatted ? val.toLocaleString('id-ID') : val;
      if (p < 1) window.requestAnimationFrame(step);
    }
    window.requestAnimationFrame(step);
  }

  document.addEventListener('DOMContentLoaded', function () {
    initAllCharts();

    // NAV
    var navs = document.querySelectorAll('.nav-item[data-t]');
    var pages = ['overview', 'peta', 'prediksi', 'klaster', 'tren', 'laporan', 'pengaturan'];
    var sections = pages.map(function (k) { return document.getElementById('p-' + k); });
    navs.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var t = btn.dataset.t;
        navs.forEach(function (b) { b.classList.toggle('on', b === btn); });
        sections.forEach(function (s) { if (s) s.classList.toggle('on', s.id === 'p-' + t); });
        window.scrollTo({ top: 0, behavior: 'smooth' });
        setTimeout(resizeAllCharts, 60);
        if (t === 'peta' && !petaWilayah) { setTimeout(function() { petaWilayah = initMap('map-wilayah', 5); }, 100); }
      });
    });

    // TABLE TOP 5
    var tbody = document.getElementById('top-prov-tbody');
    if (tbody && window.DATA_ASLI && window.DATA_ASLI.top_prov) {
      var html = '';
      window.DATA_ASLI.top_prov.labels.forEach(function(label, i) { html += '<tr class="anim-row"><td><span class="rank">' + (i + 1) + '</span>' + label + '</td><td>' + window.DATA_ASLI.top_prov.data[i].toLocaleString('id-ID') + '</td></tr>'; });
      tbody.innerHTML = html;
    }

    // FILTER OVERVIEW
    var fTahun = document.getElementById('f-tahun');
    if (fTahun) fTahun.addEventListener('change', function (e) { updateOverview(e.target.value); });

    // SIMULASI PREDIKSI DAMPAK (backend Random Forest)
    ['sim-jenis', 'sim-prov', 'sim-bulan', 'sim-kepadatan'].forEach(function(id) { var el = document.getElementById(id); if (el) el.addEventListener('change', updateSim); });
    loadPrediksiMeta().then(runPrediksi).catch(function () {
      showSimStatus(backendOfflineMsg());
      setText('sim-val', 'Prediksi tidak tersedia');
      setText('klaster-ringkasan', '');
    });

    // MAP OVERVIEW
    var mapCheck = setInterval(function() { if (document.getElementById('map-overview') && window.L) { petaUtama = initMap('map-overview', 4); clearInterval(mapCheck); } }, 200);

    // MAP FILTER (Di tab Peta Wilayah)
    var mapFilter = document.getElementById('map-filter-jenis');
    if (mapFilter) {
      mapFilter.addEventListener('change', function(e) {
        var val = e.target.value.toLowerCase();
        if (!petaWilayah) petaWilayah = initMap('map-wilayah', 5);
        if (petaWilayah) {
          petaWilayah.eachLayer(function(layer) {
            if (layer._jenis) {
              if (val === 'semua' || layer._jenis.indexOf(val) >= 0) { layer.addTo(petaWilayah); } else { petaWilayah.removeLayer(layer); }
            }
          });
        }
      });
    }

    // SIDEBAR TOGGLE
    var btnToggle = document.getElementById('btn-toggle-sidebar');
    var appContainer = document.querySelector('.app');
    if (btnToggle && appContainer) {
      btnToggle.addEventListener('click', function() { appContainer.classList.toggle('sidebar-hidden'); setTimeout(resizeAllCharts, 450); });
    }

    // COUNT-UP KPI
    if (window.DATA_ASLI && window.DATA_ASLI.kpi) {
      animateValue(document.getElementById('kpi-total'),     0, window.DATA_ASLI.kpi.total,     1500, true);
      animateValue(document.getElementById('kpi-meninggal'), 0, window.DATA_ASLI.kpi.meninggal, 1500, true);
      animateValue(document.getElementById('kpi-prov'),      0, window.DATA_ASLI.kpi.prov,      1500, false);
      var kpiRumah = document.getElementById('kpi-rumah');
      if (kpiRumah) kpiRumah.textContent = window.DATA_ASLI.kpi.rumah;
    }

    // SEARCH
    var searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('input', function (e) {
        var val = e.target.value.toLowerCase().trim();
        var rows = document.querySelectorAll('#top-prov-tbody tr');
        rows.forEach(function (row) { row.style.display = row.textContent.toLowerCase().indexOf(val) >= 0 ? '' : 'none'; });
      });
    }

    // EXPORT CSV
    var btnExport = document.getElementById('btn-export');
    if (btnExport) {
      btnExport.addEventListener('click', function () {
        if (!window.DATA_ASLI || !window.DATA_ASLI.top_prov) return;
        var csv = 'Provinsi,Kejadian\n';
        window.DATA_ASLI.top_prov.labels.forEach(function (label, i) { csv += '"' + label + '",' + window.DATA_ASLI.top_prov.data[i] + '\n'; });
        var blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
        var link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'Data_Top_Provinsi_BNPB.csv';
        link.click();
        URL.revokeObjectURL(link.href);
      });
    }

    // DARK MODE
    var darkSwitch = document.querySelector('.switch input[type="checkbox"]');
    if (darkSwitch) {
      darkSwitch.addEventListener('change', function (e) {
        var isDark = e.target.checked;
        document.body.classList.toggle('dark-mode', isDark);
        if (typeof Chart !== 'undefined') {
          Chart.defaults.color = isDark ? '#98A2B3' : '#667085';
          Chart.defaults.borderColor = isDark ? '#2A3A5E' : '#F2F4F7';
          Object.values(charts).forEach(function (c) {
            if (!c) return;
            if (c.options.scales) {
              Object.values(c.options.scales).forEach(function (s) {
                if (s.grid)  s.grid.color  = isDark ? '#2A3A5E' : '#F2F4F7';
                if (s.ticks) s.ticks.color = isDark ? '#98A2B3' : '#667085';
              });
            }
            c.update('none');
          });
        }
      });
    }
  });
})();
