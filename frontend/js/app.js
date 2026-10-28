/* ============================================================
   DisasterWatch — ALL IN ONE SCRIPT (Data Asli, Chart, Peta, Animasi)
   ============================================================ */
(function () {
  'use strict';

  var charts = {};

  // ==========================================
  // BAGIAN 1: SETUP CHART.JS
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
        datasets: [{ label: 'Kejadian 2026', data: data, borderColor: '#2E75B6', backgroundColor: grad, borderWidth: 2.5, pointBackgroundColor: '#fff', pointBorderColor: '#2E75B6', pointBorderWidth: 2.5, pointRadius: 4, pointHoverRadius: 6, tension: .35, fill: true }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
        plugins: { tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + c.parsed.y + ' kejadian'; } } } },
        scales: { x: { grid: { display: false }, ticks: { font: { size: 11, weight: '600' } } }, y: { beginAtZero: true, grid: { color: '#F2F4F7' }, ticks: { font: { size: 11 } } } }
      }
    });
  }

  function drawKomposisi() {
    var ctx = document.getElementById('c-komposisi');
    if (!ctx || !window.DATA_ASLI) return;
    var labels = window.DATA_ASLI.komposisi.labels;
    var data = window.DATA_ASLI.komposisi.data;
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
    // Dominan
    var ctxD = document.getElementById('c-dominan');
    if (ctxD) {
      charts.dominan = new Chart(ctxD, {
        type: 'bar',
        data: { labels: ['Jawa Tengah','Jawa Timur','Jawa Barat','Sulawesi Selatan','Sulawesi Tengah'], datasets: [{ label: 'Banjir', data: [216,55,94,62,30], backgroundColor: '#3A86FF', borderRadius: 0, barThickness: 24 },{ label: 'Karhutla', data: [118,179,59,29,12], backgroundColor: '#FB5607', borderRadius: 0, barThickness: 24 },{ label: 'Tanah longsor', data: [59,42,83,53,68], backgroundColor: '#8D6E63', borderRadius: 0, barThickness: 24 }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 10, boxHeight: 10, padding: 14, font: { size: 11.5, weight: '600' }, usePointStyle: true, pointStyle: 'rectRounded' } } }, scales: { x: { stacked: true, grid: { color: '#F2F4F7' }, ticks: { font: { size: 11 } } }, y: { stacked: true, grid: { display: false }, ticks: { font: { size: 11.5, weight: '600' } } } } }
      });
    }
    // Feature
    var ctxF = document.getElementById('c-feature');
    if (ctxF) {
      charts.feature = new Chart(ctxF, {
        type: 'bar',
        data: { labels: ['Jenis bencana','Provinsi','Bulan','Rumah terendam','Kepadatan penduduk'], datasets: [{ data: [0.34,0.26,0.17,0.12,0.08], backgroundColor: ['#2E75B6','#3A86FF','#6C8EAD','#9DB9DE','#C7D7EC'], borderRadius: 6, barThickness: 18 }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, grid: { color: '#F2F4F7' } }, y: { grid: { display: false } } } }
      });
    }
    
    // KLASTER: Grafik Batang Rata-rata Korban
    var ctxS = document.getElementById('c-scatter');
    if (ctxS) {
      charts.scatter = new Chart(ctxS, {
        type: 'bar',
        data: {
          labels: ['Klaster 1 (Banjir)', 'Klaster 2 (Karhutla)', 'Klaster 3 (Gempa)'],
          datasets: [{
            label: 'Rata-rata Korban Jiwa',
            data: [3.1, 11.4, 19.8],
            backgroundColor: ['#3A86FF', '#FB5607', '#2A9D8F'],
            borderRadius: 6,
            barThickness: 50
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { 
            legend: { display: false },
            tooltip: { callbacks: { label: function(c) { return c.parsed.y + ' korban per kejadian'; } } }
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 12, weight: '600' } } },
            y: { beginAtZero: true, grid: { color: '#F2F4F7' }, title: { display: true, text: 'Jumlah Korban' } }
          }
        }
      });
    }

    // Forecast
    var ctxFo = document.getElementById('c-forecast');
    if (ctxFo) {
      charts.forecast = new Chart(ctxFo, {
        type: 'line',
        data: { labels: ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'], datasets: [{ label: 'Aktual', data: [210,148,172,160,138,104,196,268,345,178,null,null], borderColor: '#1F3A5F', borderWidth: 2.5, tension: .35 }, { label: 'Ramalan', data: [null,null,null,null,null,null,null,null,null,178,245,210], borderColor: '#E4572E', borderWidth: 2.5, borderDash: [6,5], tension: .35 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
      });
    }
    // Seasonal
    var ctxSe = document.getElementById('c-seasonal');
    if (ctxSe) {
      charts.seasonal = new Chart(ctxSe, {
        type: 'bar',
        data: { labels: ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'], datasets: [{ data: [185,160,178,152,140,120,175,210,240,190,205,220], backgroundColor: '#2E75B6', borderRadius: 6, barThickness: 20 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
      });
    }
  }

  function initAllCharts() {
    setupCharts();
    var monthlyData = (window.DATA_ASLI && window.DATA_ASLI.monthly) ? window.DATA_ASLI.monthly : [0,0,0,0,0,0,0,0,0,0,0,0];
    drawMonthly(monthlyData);
    drawKomposisi();
    drawOtherCharts();
  }

  function resizeAllCharts() {
    Object.values(charts).forEach(function (c) { if (c && c.resize) c.resize(); });
  }

  // ==========================================
  // BAGIAN 2: LOGIKA UI & PETA (LEAFLET)
  // ==========================================
  function initMap(elementId, zoom) {
    var el = document.getElementById(elementId);
    if (!el || !window.L) return;
    
    var map = L.map(elementId).setView([-2.5489, 118.0149], zoom);
    
    // OpenStreetMap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(map);

    if (window.DATA_ASLI && window.DATA_ASLI.map_points) {
      window.DATA_ASLI.map_points.forEach(function(p) {
        var color = p.jenis.includes('BANJIR') ? '#3A86FF' : p.jenis.includes('KEBAKARAN') ? '#FB5607' : p.jenis.includes('CUACA') ? '#E9C46A' : '#2A9D8F';
        // PETA DIPERBESAR: radius 8, weight 2
        L.circleMarker([p.lat, p.lng], { radius: 8, fillColor: color, color: '#fff', weight: 2, fillOpacity: 0.9, opacity: 1 })
         .addTo(map).bindPopup('<b>' + p.jenis + '</b><br>' + p.prov);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    // 1. Jalankan Chart
    initAllCharts();

    // 2. Navigasi
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

    // 3. Isi Tabel Top 5 & Tambahkan Animasi
    var tbody = document.getElementById('top-prov-tbody');
    if (tbody && window.DATA_ASLI) {
      var html = '';
      window.DATA_ASLI.top_prov.labels.forEach(function(label, i) {
        // Tambahan class 'anim-row' agar bisa dianimasikan CSS
        html += '<tr class="anim-row"><td><span class="rank">' + (i+1) + '</span>' + label + '</td><td>' + window.DATA_ASLI.top_prov.data[i].toLocaleString('id-ID') + '</td></tr>';
      });
      tbody.innerHTML = html;
    }

    // 4. Simulasi Prediksi
    var simMap = { 
      'Banjir|Jawa Tengah|Januari': [78,'Tinggi'], 
      'Banjir|Jawa Barat|Januari': [81,'Tinggi'],
      'Gempa bumi|Jawa Barat|Januari': [55,'Sedang']
    };
    var sj = document.getElementById('sim-jenis'), sp = document.getElementById('sim-prov'), sb = document.getElementById('sim-bulan');
    var sv = document.getElementById('sim-val'), sbar = document.getElementById('sim-bar');
    function updateSim() {
      if (!sj || !sp || !sb || !sv || !sbar) return;
      var r = simMap[sj.value + '|' + sp.value + '|' + sb.value] || [50, 'Sedang'];
      sv.textContent = r[1] + ' · ' + r[0] + '%';
      sbar.style.width = r[0] + '%';
    }
    [sj, sp, sb].forEach(function (s) { if (s) s.addEventListener('change', updateSim); });
    updateSim();

    // 5. Inisialisasi Peta (Pakai interval biar pasti siap)
    var mapCheck = setInterval(function() {
      if (document.getElementById('map-overview') && window.L) {
        initMap('map-overview', 4);
        clearInterval(mapCheck);
      }
    }, 200);

    // Peta tab kedua
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

    // 6. Fitur Sembunyikan Sidebar (Full Screen Mode)
    var btnToggle = document.getElementById('btn-toggle-sidebar');
    var appContainer = document.querySelector('.app');
    
    if (btnToggle && appContainer) {
      btnToggle.addEventListener('click', function() {
        appContainer.classList.toggle('sidebar-hidden');
        // Tunggu animasi selesai (400ms), lalu resize chart biar memanjang
        setTimeout(resizeAllCharts, 450); 
      });
    }
  });
})();