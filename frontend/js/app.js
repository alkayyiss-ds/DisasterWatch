/* ============================================================
   DisasterWatch — ALL IN ONE SCRIPT (v2 Final Fixed)
   ============================================================ */
(function () {
  'use strict';

  var charts = {};

  // ==========================================
  // KONFIGURASI MITIGASI PER KLASTER (referensi BNPB)
  // ==========================================
  var MITIGASI = {
    0: [ // Risiko Rendah
      { t: 'Sosialisasi & edukasi kebencanaan', d: 'Program rutin di sekolah & komunitas untuk meningkatkan literasi risiko.' },
      { t: 'Pemeliharaan drainase & saluran air', d: 'Pembersihan berkala untuk mencegah genangan saat musim hujan.' },
      { t: 'Monitoring & deteksi dini sederhana', d: 'Pemantauan cuaca dan titik rawan bersama babinsa/karang taruna.' }
    ],
    1: [ // Multi-Bencana Kronis
      { t: 'Diversifikasi mata pencaharian', d: 'Mengurangi ketergantungan pada sektor pertanian yang rentan bencana.' },
      { t: 'Asuransi pertanian & perlindungan sosial', d: 'Perluas cakupan asuransi lahan dan kompensasi kerusakan.' },
      { t: 'Perbaikan tata guna lahan & DAS', d: 'Reboisasi dan pengelolaan daerah aliran sungai untuk cegah banjir/longsor.' },
      { t: 'Sistem peringatan dini hidrometeorologi', d: 'Integrasi info BMKG ke level desa dan grup komunikasi warga.' },
      { t: 'Penguatan bangunan tahan bencana', d: 'Retrofit rumah & fasilitas publik di zona rawan.' }
    ],
    2: [ // Kemanusiaan Akut
      { t: 'Rencana kontingensi & jalur evakuasi', d: 'Peta evakuasi, titik kumpul, dan latihan simulasi rutin.' },
      { t: 'Stok logistik darurat wilayah', d: 'Gudang logistik di level kabupaten dengan buffer 7 hari.' },
      { t: 'Tim reaksi cepat (TRC) terlatih', d: 'Pelatihan SAR dasar untuk relawan dan aparat desa.' },
      { t: 'Kampanye kesehatan & sanitasi darurat', d: 'Cegah penyakit pasca-bencana, terutama di pengungsian.' }
    ],
    3: [ // Katastropik
      { t: 'Evakuasi dini & shelter terstruktur', d: 'Zonasi evakuasi, shelter permanen di luar zona bahaya, simulasi wajib.' },
      { t: 'Sistem peringatan dini multi-bahaya', d: 'Integrasi sensor gempa, tsunami, cuaca ekstrem ke sirene desa.' },
      { t: 'Mitigasi struktural prioritas', d: 'Tanggul, dam, atau retrofitting fasilitas vital sesuai jenis ancaman.' },
      { t: 'Koordinasi lintas sektor 24/7', d: 'Pusat komando BNPB-BPBD-TNI-Polri dengan protokol respons cepat.' },
      { t: 'Pendidikan risiko katastropik', d: 'Kurikulum khusus kesiapsiagaan bencana untuk warga di zona merah.' }
    ]
  };

  var KLASter_LABEL = {
    0: { name: 'Risiko Rendah', color: 'green', badge: 'Risiko Rendah' },
    1: { name: 'Multi-Bencana Kronis', color: 'blue', badge: 'Risiko Sedang' },
    2: { name: 'Kemanusiaan Akut', color: 'orange', badge: 'Risiko Tinggi' },
    3: { name: 'Katastropik', color: 'red', badge: 'Risiko Katastropik' }
  };

  // ==========================================
  // HEURISTIK PREDIKSI KLASTER DAMPAK
  // ==========================================
  function predictCluster(jenis, prov, bulan, kepadatan) {
    var score = 0;
    if (jenis === 'Gempa bumi') score += 3;
    else if (jenis === 'Karhutla') score += 2;
    else if (jenis === 'Banjir' || jenis === 'Tanah longsor') score += 2;
    else score += 1;
    if (['Jawa Barat','Jawa Tengah','Jawa Timur','Aceh'].indexOf(prov) >= 0) score += 2;
    else if (['Riau','Kalimantan Selatan'].indexOf(prov) >= 0) score += 1;
    if (['November','Desember','Januari','Februari','Maret'].indexOf(bulan) >= 0) score += 1;
    if (kepadatan === 'Sangat tinggi') score += 3;
    else if (kepadatan === 'Tinggi') score += 2;
    else if (kepadatan === 'Sedang') score += 1;

    if (score >= 8) return { c: 3, pct: 82 };
    if (score >= 6) return { c: 2, pct: 68 };
    if (score >= 4) return { c: 1, pct: 54 };
    return { c: 0, pct: 32 };
  }

  // ==========================================
  // SETUP CHART.JS
  // ==========================================
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

  // ==========================================
  // CHART: Monthly line (overview)
  // ==========================================
  function drawMonthly(data) {
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
        datasets: [{
          label: 'Kejadian 2026',
          data: data,
          borderColor: '#2E75B6',
          backgroundColor: grad,
          borderWidth: 2.5,
          pointBackgroundColor: '#fff',
          pointBorderColor: '#2E75B6',
          pointBorderWidth: 2.5,
          pointRadius: 4,
          pointHoverRadius: 6,
          tension: .35,
          fill: true
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          tooltip: {
            callbacks: {
              label: function (c) { return c.dataset.label + ': ' + c.parsed.y + ' kejadian'; }
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 11, weight: '600' } } },
          y: { beginAtZero: true, grid: { color: '#F2F4F7' }, ticks: { font: { size: 11 } } }
        }
      }
    });
  }

  // ==========================================
  // CHART: Komposisi doughnut (overview)
  // ==========================================
  function drawKomposisi() {
    var ctx = document.getElementById('c-komposisi');
    if (!ctx || !window.DATA_ASLI) return;
    var labels = window.DATA_ASLI.komposisi.labels;
    var data = window.DATA_ASLI.komposisi.data;
    if (charts.komposisi) charts.komposisi.destroy();
    charts.komposisi = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: ['#FB5607','#3A86FF','#6C8EAD','#E9C46A','#8D6E63','#8338EC','#2A9D8F'],
          borderWidth: 0,
          hoverOffset: 8
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '62%',
        plugins: {
          legend: {
            display: true, position: 'right',
            labels: {
              boxWidth: 10, boxHeight: 10, padding: 12,
              font: { size: 11.5, weight: '600' },
              usePointStyle: true, pointStyle: 'rectRounded'
            }
          },
          tooltip: {
            callbacks: {
              label: function (c) {
                var total = data.reduce(function(a,b){return a+b;}, 0);
                return c.label + ': ' + c.parsed + ' (' + (c.parsed / total * 100).toFixed(1) + '%)';
              }
            }
          }
        }
      }
    });
  }

  // ==========================================
  // CHART LAINNYA
  // ==========================================
  function drawOtherCharts() {
    // --- Dominan ---
    var ctxD = document.getElementById('c-dominan');
    if (ctxD) {
      if (charts.dominan) charts.dominan.destroy();
      charts.dominan = new Chart(ctxD, {
        type: 'bar',
        data: {
          labels: ['Jawa Tengah','Jawa Timur','Jawa Barat','Sulawesi Selatan','Sulawesi Tengah'],
          datasets: [
            { label: 'Banjir', data: [216,55,94,62,30], backgroundColor: '#3A86FF', borderRadius: 0, barThickness: 24 },
            { label: 'Karhutla', data: [118,179,59,29,12], backgroundColor: '#FB5607', borderRadius: 0, barThickness: 24 },
            { label: 'Tanah longsor', data: [59,42,83,53,68], backgroundColor: '#8D6E63', borderRadius: 0, barThickness: 24 }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false, indexAxis: 'y',
          plugins: {
            legend: {
              display: true, position: 'bottom',
              labels: { boxWidth: 10, boxHeight: 10, padding: 14, font: { size: 11.5, weight: '600' }, usePointStyle: true, pointStyle: 'rectRounded' }
            }
          },
          scales: {
            x: { stacked: true, grid: { color: '#F2F4F7' }, ticks: { font: { size: 11 } } },
            y: { stacked: true, grid: { display: false }, ticks: { font: { size: 11.5, weight: '600' } } }
          }
        }
      });
    }

    // --- Feature Importance ---
    var ctxF = document.getElementById('c-feature');
    if (ctxF) {
      if (charts.feature) charts.feature.destroy();
      charts.feature = new Chart(ctxF, {
        type: 'bar',
        data: {
          labels: ['Jenis bencana','Provinsi','Bulan','Kepadatan penduduk','Riwayat kejadian'],
          datasets: [{
            data: [0.32,0.24,0.16,0.18,0.10],
            backgroundColor: ['#2E75B6','#3A86FF','#6C8EAD','#9DB9DE','#C7D7EC'],
            borderRadius: 6, barThickness: 18
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false, indexAxis: 'y',
          plugins: { legend: { display: false } },
          scales: {
            x: { beginAtZero: true, grid: { color: '#F2F4F7' } },
            y: { grid: { display: false } }
          }
        }
      });
    }

    // --- Klaster: perbandingan dampak (k=4) ---
    var ctxC = document.getElementById('c-cluster-impact');
    if (ctxC) {
      if (charts.clusterImpact) charts.clusterImpact.destroy();
      charts.clusterImpact = new Chart(ctxC, {
        type: 'bar',
        data: {
          labels: ['Risiko Rendah','Multi-Bencana','Kemanusiaan Akut','Katastropik'],
          datasets: [
            { label: 'Rata-rata Korban Jiwa', data: [0.07, 0.29, 0.38, 99.85], backgroundColor: '#D92D20', borderRadius: 6, barThickness: 22 },
            { label: 'Rata-rata Terdampak', data: [45, 2563, 6817, 23422], backgroundColor: '#2E75B6', borderRadius: 6, barThickness: 22 }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true, position: 'bottom',
              labels: { boxWidth: 10, boxHeight: 10, padding: 14, font: { size: 11.5, weight: '600' }, usePointStyle: true, pointStyle: 'rectRounded' }
            },
            tooltip: {
              callbacks: {
                label: function (c) {
                  var v = c.parsed.y;
                  var fmt = v >= 1000 ? v.toLocaleString('id-ID') : v;
                  return c.dataset.label + ': ' + fmt;
                }
              }
            }
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 11.5, weight: '600' } } },
            y: {
              type: 'logarithmic', beginAtZero: false,
              grid: { color: '#F2F4F7' },
              title: { display: true, text: 'Skala logaritmik' }
            }
          }
        }
      });
    }

    // --- Forecast (FIXED: Garis Ramalan muncul & tidak terpotong) ---
    var ctxFo = document.getElementById('c-forecast');
    if (ctxFo) {
      if (charts.forecast) charts.forecast.destroy();
      charts.forecast = new Chart(ctxFo, {
        type: 'line',
        data: {
          labels: ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'],
          datasets: [
            { 
              label: 'Aktual', 
              data: [210,148,172,160,138,104,196,268,345,178,null,null], 
              borderColor: '#1F3A5F', 
              backgroundColor: '#1F3A5F',
              borderWidth: 2.5, 
              tension: .35, 
              pointRadius: 4,
              pointBackgroundColor: '#fff',
              pointBorderColor: '#1F3A5F',
              pointBorderWidth: 2
            },
            { 
              label: 'Ramalan', 
              data: [null,null,null,null,null,null,null,null,null,178,245,210], 
              borderColor: '#E4572E', 
              backgroundColor: '#E4572E',
              borderWidth: 2.5, 
              borderDash: [6,5], 
              tension: .35, 
              pointRadius: 4,
              pointBackgroundColor: '#fff',
              pointBorderColor: '#E4572E',
              pointBorderWidth: 2
            }
          ]
        },
        options: {
          responsive: true, 
          maintainAspectRatio: false,
          interaction: { intersect: false, mode: 'index' },
          plugins: { 
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function(c) {
                  if (c.parsed.y === null) return null;
                  return c.dataset.label + ': ' + c.parsed.y + ' kejadian';
                }
              }
            }
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 11, weight: '600' } } },
            y: { 
              beginAtZero: true, 
              grid: { color: '#F2F4F7' }, 
              ticks: { font: { size: 11 } },
              suggestedMax: 400
            }
          }
        }
      });
    }

    // --- Seasonal ---
    var ctxSe = document.getElementById('c-seasonal');
    if (ctxSe) {
      if (charts.seasonal) charts.seasonal.destroy();
      charts.seasonal = new Chart(ctxSe, {
        type: 'bar',
        data: {
          labels: ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'],
          datasets: [{ data: [185,160,178,152,140,120,175,210,240,190,205,220], backgroundColor: '#2E75B6', borderRadius: 6, barThickness: 20 }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false } },
            y: { beginAtZero: true, grid: { color: '#F2F4F7' } }
          }
        }
      });
    }
  }

  function initAllCharts() {
    setupCharts();
    var monthlyData = (window.DATA_ASLI && window.DATA_ASLI.monthly)
      ? window.DATA_ASLI.monthly
      : [0,0,0,0,0,0,0,0,0,0,0,0];
    drawMonthly(monthlyData);
    drawKomposisi();
    drawOtherCharts();
  }

  function resizeAllCharts() {
    Object.values(charts).forEach(function (c) { if (c && c.resize) c.resize(); });
  }

  // ==========================================
  // SIMULASI PREDIKSI DAMPAK + MITIGASI
  // ==========================================
  function updateSim() {
    var jenisEl = document.getElementById('sim-jenis');
    var provEl = document.getElementById('sim-prov');
    var bulanEl = document.getElementById('sim-bulan');
    var kepadatanEl = document.getElementById('sim-kepadatan');

    var jenis = jenisEl ? jenisEl.value : 'Banjir';
    var prov = provEl ? provEl.value : 'Jawa Tengah';
    var bulan = bulanEl ? bulanEl.value : 'Januari';
    var kepadatan = kepadatanEl ? kepadatanEl.value : 'Sedang';

    var r = predictCluster(jenis, prov, bulan, kepadatan);
    var kl = KLASter_LABEL[r.c];

    var sv = document.getElementById('sim-val');
    var sbar = document.getElementById('sim-bar');
    var korban = document.getElementById('sim-korban');
    var terdampak = document.getElementById('sim-terdampak');
    var rusak = document.getElementById('sim-rusak');
    var badge = document.getElementById('mitigasi-badge');
    var list = document.getElementById('mitigation-list');
    var sub = document.getElementById('mitigasi-sub');

    if (sv) sv.textContent = kl.name + ' · ' + r.pct + '%';
    if (sbar) sbar.style.width = r.pct + '%';

    if (korban) {
      var k = r.c === 3 ? '~ 50–150 jiwa'
            : r.c === 2 ? '~ 5–15 jiwa'
            : r.c === 1 ? '~ 1–5 jiwa'
            : '< 1 jiwa';
      korban.textContent = k;
    }
    if (terdampak) {
      var t = r.c === 3 ? '~ 20.000+ jiwa'
            : r.c === 2 ? '~ 5.000 jiwa'
            : r.c === 1 ? '~ 2.500 jiwa'
            : '~ 50 jiwa';
      terdampak.textContent = t;
    }
    if (rusak) {
      var ru = r.c === 3 ? '> 1.000 unit'
             : r.c === 2 ? '~ 500 unit'
             : r.c === 1 ? '~ 180 unit'
             : '~ 10 unit';
      rusak.textContent = ru;
    }

    if (badge) {
      badge.className = 'pill ' + kl.color;
      badge.textContent = kl.badge;
    }

    if (sub) {
      sub.textContent = 'Klaster ' + r.c + ' — ' + kl.name + ' · ' + prov + ' · ' + bulan;
    }

    if (list) {
      var items = MITIGASI[r.c] || [];
      var html = '';
      items.forEach(function(m, i) {
        var urgentClass = (r.c >= 2) ? ' urgent' : '';
        html += '<li class="' + (urgentClass ? 'urgent' : '') + '">' +
          '<span class="m-icon">' + (i + 1) + '</span>' +
          '<div><b>' + m.t + '</b>' +
          '<span style="font-size:12.5px;color:var(--muted);">' + m.d + '</span></div>' +
          '</li>';
      });
      list.innerHTML = html;
    }
  }

  // ==========================================
  // PETA LEAFLET
  // ==========================================
  function initMap(elementId, zoom) {
    var el = document.getElementById(elementId);
    if (!el || !window.L) return;

    var map = L.map(elementId).setView([-2.5489, 118.0149], zoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(map);

    if (window.DATA_ASLI && window.DATA_ASLI.map_points) {
      window.DATA_ASLI.map_points.forEach(function(p) {
        var color = p.jenis.indexOf('BANJIR') >= 0 ? '#3A86FF'
                  : p.jenis.indexOf('KEBAKARAN') >= 0 ? '#FB5607'
                  : p.jenis.indexOf('CUACA') >= 0 ? '#E9C46A'
                  : '#2A9D8F';
        L.circleMarker([p.lat, p.lng], {
          radius: 8,
          fillColor: color,
          color: '#fff',
          weight: 2,
          fillOpacity: 0.9,
          opacity: 1
        })
        .addTo(map)
        .bindPopup('<b>' + p.jenis + '</b><br>' + p.prov);
      });
    }
  }

  // ==========================================
  // INIT
  // ==========================================
  document.addEventListener('DOMContentLoaded', function () {

    initAllCharts();

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
      });
    });

    var tbody = document.getElementById('top-prov-tbody');
    if (tbody && window.DATA_ASLI && window.DATA_ASLI.top_prov) {
      var html = '';
      window.DATA_ASLI.top_prov.labels.forEach(function(label, i) {
        html += '<tr class="anim-row">' +
          '<td><span class="rank">' + (i + 1) + '</span>' + label + '</td>' +
          '<td>' + window.DATA_ASLI.top_prov.data[i].toLocaleString('id-ID') + '</td>' +
          '</tr>';
      });
      tbody.innerHTML = html;
    }

    ['sim-jenis', 'sim-prov', 'sim-bulan', 'sim-kepadatan'].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('change', updateSim);
    });
    updateSim();

    var mapCheck = setInterval(function() {
      if (document.getElementById('map-overview') && window.L) {
        initMap('map-overview', 4);
        clearInterval(mapCheck);
      }
    }, 200);

    var btnPeta = document.querySelector('.nav-item[data-t="peta"]');
    if (btnPeta) {
      btnPeta.addEventListener('click', function() {
        setTimeout(function() {
          if (!window._mapWilayahInit) {
            initMap('map-wilayah', 5);
            window._mapWilayahInit = true;
          }
        }, 200);
      });
    }

    var btnToggle = document.getElementById('btn-toggle-sidebar');
    var appContainer = document.querySelector('.app');
    if (btnToggle && appContainer) {
      btnToggle.addEventListener('click', function() {
        appContainer.classList.toggle('sidebar-hidden');
        setTimeout(resizeAllCharts, 450);
      });
    }
  });
})();