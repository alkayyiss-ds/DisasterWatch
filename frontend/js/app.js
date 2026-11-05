/* DisasterWatch — app.js (Final Storytelling Version) */
(function () {
  'use strict';

  function main() {
    var $ = function (s, r) { return (r || document).querySelector(s); };
    var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
    var fmt = function (n) { return (n == null ? '–' : Number(n).toLocaleString('id-ID')); };
    var API = 'http://127.0.0.1:8000';
    var hasChart = typeof window.Chart !== 'undefined';
    var hasLeaflet = typeof window.L !== 'undefined';
    var charts = {};
    var DATA = { topProvinsi: [], petaOverview: [], petaWilayah: [] };

    function api(url, opts) {
      return fetch(API + url, opts).then(function (r) {
        return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || ('HTTP ' + r.status)); return d; });
      });
    }
    function setChart(id, cfg) {
      var el = $('#' + id); if (!el || !hasChart) return;
      if (charts[id]) charts[id].destroy();
      cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false }, cfg.options || {});
      charts[id] = new Chart(el, cfg);
    }
    function afterRender() { if (window.markEmptyCharts) setTimeout(window.markEmptyCharts, 200); }
    function setText(sel, t) { var e = $(sel); if (e) e.textContent = t; }
    function setEl(e, t) { if (e) e.textContent = t; }

    /* 1. Navigasi */
    function showPage(t) {
      $$('.page').forEach(function (p) { p.classList.toggle('on', p.id === 'p-' + t); });
      $$('.nav-item').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-t') === t); });
      window.scrollTo(0, 0);
      setTimeout(function () {
        if (t === 'peta' && window.__mapWilayah) window.__mapWilayah.invalidateSize();
        if (t === 'overview' && window.__mapOverview) window.__mapOverview.invalidateSize();
      }, 150);
    }
    document.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('.nav-item[data-t]') : null;
      if (b) showPage(b.getAttribute('data-t'));
    });

    /* 2. Sidebar */
    var bt = $('#btn-toggle-sidebar'), appEl = $('.app');
    if (bt && appEl) bt.addEventListener('click', function () { appEl.classList.toggle('sidebar-hidden'); });

    /* 3. Notifikasi */
    var nb = $('#btn-notif'), np = $('#notif-panel'), nc = $('#close-notif');
    if (nb && np) {
      nb.addEventListener('click', function (e) {
        e.stopPropagation();
        var vis = np.style.display === 'block';
        np.style.display = vis ? 'none' : 'block';
        nb.setAttribute('aria-expanded', String(!vis));
        var dot = nb.querySelector('.dot'); if (!vis && dot) dot.style.display = 'none';
      });
      if (nc) nc.addEventListener('click', function (e) { e.stopPropagation(); np.style.display = 'none'; nb.setAttribute('aria-expanded', 'false'); });
      document.addEventListener('click', function (e) {
        if (!np.contains(e.target) && !nb.contains(e.target)) { np.style.display = 'none'; nb.setAttribute('aria-expanded', 'false'); }
      });
      $$('.notif-trash').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
          e.stopPropagation();
          var it = btn.closest('.notif-item'); if (!it) return;
          it.style.transition = 'opacity .2s ease, transform .2s ease'; it.style.opacity = '0'; it.style.transform = 'translateX(8px)';
          setTimeout(function () {
            it.remove();
            var body = $('.notif-body');
            if (body && !$('.notif-item', body)) body.innerHTML = '<div class="notif-empty">Tidak ada pemberitahuan.</div>';
          }, 200);
        });
      });
    }

    /* 4. Dark mode */
    var darkChk = $('#p-pengaturan .switch input');
    function setDark(on) {
      document.body.classList.toggle('dark-mode', on);
      try { localStorage.setItem('dw-dark', on ? '1' : '0'); } catch (e) {}
      if (hasChart) {
        Chart.defaults.color = on ? '#C9D4E5' : '#667085';
        Chart.defaults.borderColor = on ? '#2A3A5E' : 'rgba(0,0,0,0.1)';
        Object.keys(charts).forEach(function (k) { charts[k].update(); });
      }
    }
    var saved = null; try { saved = localStorage.getItem('dw-dark'); } catch (e) {}
    if (darkChk) { darkChk.checked = saved === '1'; darkChk.addEventListener('change', function () { setDark(darkChk.checked); }); }
    if (saved === '1') setDark(true);

    /* 5. Overview */
    var fTahun = $('#f-tahun'), fJenis = $('#f-jenis'), fProv = $('#f-prov'), fReset = $('#f-reset');

    function trendHtml(p, pemb) {
      if (p == null) return '<span class="trend flat">— n/a</span> vs tahun lalu';
      var cls = p > 0 ? 'up' : p < 0 ? 'down' : 'flat', ar = p > 0 ? '▲' : p < 0 ? '▼' : '—';
      return '<span class="trend ' + cls + '">' + ar + ' ' + Math.abs(p).toLocaleString('id-ID') + '%</span> vs tahun lalu' + (pemb ? ' (' + pemb + ')' : '');
    }
    function renderTopProvinsi(rows) {
      var tb = $('#top-prov-tbody'); if (!tb) return;
      tb.innerHTML = rows.slice(0, 5).map(function (r, i) {
        return '<tr><td><span class="rank">' + (i + 1) + '</span>' + r.nama + '</td><td>' + fmt(r.nilai) + '</td></tr>';
      }).join('');
    }
    function warna(r) { return r === 'tinggi' ? '#D92D20' : r === 'sedang' ? '#F4A259' : '#0E9384'; }
    function drawMaps() {
      if (!hasLeaflet) return;
      [['map-overview', '__mapOverview', false, 'petaOverview'], ['map-wilayah', '__mapWilayah', true, 'petaWilayah']].forEach(function (a) {
        var el = $('#' + a[0]); if (!el) return;
        var m = window[a[1]];
        if (!m) {
          m = L.map(el).setView([-2.5, 118], 5);
          L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(m);
          m.__pts = L.layerGroup().addTo(m); window[a[1]] = m;
        }
        m.__pts.clearLayers();
        DATA[a[3]].forEach(function (p) {
          L.circleMarker([p.lat, p.lng], { radius: a[2] ? (p.risiko === 'tinggi' ? 14 : 10) : 8, color: '#fff', weight: 2, fillColor: warna(p.risiko), fillOpacity: 0.88 })
            .addTo(m.__pts).bindPopup('<b>' + p.nama + '</b><br>' + fmt(p.n) + ' laporan · risiko ' + p.risiko);
        });
        setTimeout(function () { m.invalidateSize(); }, 200);
      });
    }

    function loadOverview() {
      var q = '?tahun=' + (fTahun ? fTahun.value : 0) + '&jenis=' + encodeURIComponent(fJenis ? fJenis.value : 'semua') +
              '&provinsi=' + encodeURIComponent(fProv ? fProv.value : 'semua');
      return api('/api/overview' + q).then(function (r) {
        if (fProv && fProv.options.length <= 1 && r.petaTitik) {
            var currentVal = fProv.value;
            fProv.innerHTML = '<option value="semua">Semua provinsi</option>';
            var sortedProv = r.petaTitik.map(function(p) { return p.nama; }).sort();
            sortedProv.forEach(function(nama) {
                var opt = document.createElement('option');
                opt.value = nama.toUpperCase(); 
                opt.textContent = nama;
                fProv.appendChild(opt);
            });
            fProv.value = currentVal;
        }

        setText('#kpi-total', fmt(r.kpi.total)); setText('#kpi-meninggal', fmt(r.kpi.meninggal));
        setText('#kpi-rumah', fmt(r.kpi.rumah)); setText('#kpi-prov', fmt(r.kpi.prov));
        [['kpi-total', 'total'], ['kpi-meninggal', 'meninggal'], ['kpi-rumah', 'rumah']].forEach(function (x) {
          var foot = $('#' + x[0]).parentNode.querySelector('.kpi-foot'); if (foot) foot.innerHTML = trendHtml(r.trend[x[1]], r.pembanding);
        });
        var pf = $('#kpi-prov').parentNode.querySelector('.kpi-foot'); if (pf) pf.textContent = 'dari 38 provinsi';
        setText('#p-overview .grid-2 .card-head p', 'Data tahun ' + r.tahun);

        setChart('c-monthly', { type: 'line', data: { labels: r.monthly.labels, datasets: [{ label: 'Kejadian', data: r.monthly.values,
          borderColor: '#2E75B6', backgroundColor: 'rgba(46,117,182,0.1)', fill: true, tension: 0.4, pointRadius: 2, borderWidth: 3 }] },
          options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c){ return ' '+c.parsed.y.toLocaleString('id-ID')+' kejadian'; } } } }, 
          scales: { y: { beginAtZero: true, grid: { color: '#F2F4F7' }, border:{display:false} }, x: { grid: { display: false }, border:{display:false} } } } });
        
        setChart('c-komposisi', { type: 'doughnut', data: { labels: r.komposisi.labels, datasets: [{ data: r.komposisi.values,
          backgroundColor: ['#2E75B6', '#F4A259', '#0E9384', '#D92D20', '#8A9BB8', '#7A5AF8', '#3A86FF', '#FB5607', '#667085'], borderWidth: 2, borderColor: '#fff' }] },
          options: { cutout: '65%', plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, padding: 20 } }, tooltip: { callbacks: { label: function(c){ return ' '+c.label+': '+c.parsed.toLocaleString('id-ID')+' kejadian'; } } } } } });

        DATA.topProvinsi = r.topProvinsi.map(function (i) { return { nama: i.provinsi, nilai: i.jumlah_kejadian }; });
        renderTopProvinsi(DATA.topProvinsi);
        DATA.petaOverview = r.petaTitik; drawMaps(); afterRender();
      }).catch(function (e) { console.error('Overview gagal:', e); });
    }
    [fTahun, fJenis, fProv].forEach(function (el) { if (el) el.addEventListener('change', loadOverview); });
    if (fReset) fReset.addEventListener('click', function () {
      if (fTahun) fTahun.selectedIndex = 0; if (fJenis) fJenis.value = 'semua'; if (fProv) fProv.value = 'semua'; loadOverview();
    });

    /* Peta Wilayah */
    var mapJenis = $('#map-filter-jenis'), mapPeriode = $('#p-peta .filter-group select');
    function loadPeta() {
      var dari = mapPeriode ? (parseInt(mapPeriode.value.slice(0, 4), 10) || 0) : 0;
      return api('/api/overview?tahun=-1&dari=' + dari + '&jenis=' + encodeURIComponent(mapJenis ? mapJenis.value : 'semua')).then(function (r) {
        DATA.petaWilayah = r.petaTitik; drawMaps();
        var kab = $('#p-peta tbody');
        if (kab) kab.innerHTML = r.topKab.map(function (k, i) {
          return '<tr><td><span class="rank">' + (i + 1) + '</span>' + k.nama + '</td><td>' + fmt(k.n) + '</td></tr>'; }).join('');
      }).catch(function (e) { console.error('Peta gagal:', e); });
    }
    [mapJenis, mapPeriode].forEach(function (el) { if (el) el.addEventListener('change', loadPeta); });

    /* 6. Model Metadata */
    function loadMeta() {
      return api('/api/dashboard-data').then(function (r) {
        setText('#kpi-akurasi', r.kpi.akurasi + '%'); setText('#kpi-wilayah', fmt(r.kpi.wilayah));
        if (r.feature && r.feature.labels.length) {
          setChart('c-feature', { type: 'bar', data: { labels: r.feature.labels, datasets: [{ data: r.feature.values,
            backgroundColor: ['#2E75B6', '#3A86FF', '#F4A259', '#0E9384', '#8A9BB8'], borderRadius: 6 }] },
            options: { indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c){ return ' Bobot: '+(c.parsed.x*100).toFixed(1)+'%'; } } } },
            scales: { x: { grid: { color: '#F2F4F7' }, border:{display:false} }, y: { grid: { display: false }, border:{display:false} } } } });
        }
        afterRender();
      }).catch(function (e) { console.error('Meta gagal:', e); });
    }

    /* 7. Extra Data (Klaster, Tren, dll) */
    var PILL = ['green', 'blue', 'orange', 'red'];
    function loadExtra() {
      return api('/api/extra').then(function (x) {
        // Ubah dari Stacked Bar menjadi Grouped Bar (Berjejer) agar lebih mudah dibaca
        setChart('c-dominan', { type: 'bar', data: { labels: x.dominan.labels, datasets: [
          { label: 'Banjir', data: x.dominan.banjir, backgroundColor: '#2E75B6', borderRadius: 4 },
          { label: 'Cuaca ekstrem', data: x.dominan.cuaca, backgroundColor: '#F4A259', borderRadius: 4 },
          { label: 'Tanah longsor', data: x.dominan.longsor, backgroundColor: '#0E9384', borderRadius: 4 }] },
          options: { plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, padding: 16 } }, tooltip: { callbacks: { label: function(c){ return ' '+c.dataset.label+': '+c.parsed.y.toLocaleString('id-ID'); } } } },
          scales: { x: { stacked: false, grid: { display: false }, border:{display:false} }, y: { stacked: false, beginAtZero: true, grid: { color: '#F2F4F7' }, border:{display:false} } } } });

        if (x.klasterImpact) setChart('c-cluster-impact', { type: 'bar', data: { labels: x.klasterImpact.labels, datasets: [
          { label: 'Korban jiwa', data: x.klasterImpact.korban, backgroundColor: '#D92D20', borderRadius: 4 },
          { label: 'Terdampak', data: x.klasterImpact.terdampak, backgroundColor: '#3A86FF', borderRadius: 4 }] },
          options: { plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8 } }, tooltip: { callbacks: { label: function(c){ return ' '+c.dataset.label+': '+c.parsed.y.toLocaleString('id-ID'); } } } },
          scales: { y: { beginAtZero: true, grid: { color: '#F2F4F7' }, border:{display:false} }, x: { grid: { display: false }, border:{display:false} } } } });

        setChart('c-seasonal', { type: 'bar', data: { labels: x.seasonal.labels, datasets: [{ data: x.seasonal.values, backgroundColor: '#3A86FF', borderRadius: 6 }] },
          options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c){ return ' Rata-rata: '+c.parsed.y.toLocaleString('id-ID')+' kejadian'; } } } },
          scales: { y: { beginAtZero: true, grid: { color: '#F2F4F7' }, border:{display:false} }, x: { grid: { display: false }, border:{display:false} } } } });

        var ktb = $('#klaster-ringkasan');
        if (ktb && x.klaster.length) ktb.innerHTML = x.klaster.map(function (k) {
          return '<tr><td>Klaster ' + k.id + ' — ' + k.nama + '</td><td>' + fmt(k.wilayah) + '</td></tr>'; }).join('');
        var kp = $('#p-klaster .grid-2e tbody');
        if (kp && x.klasterProv.length) kp.innerHTML = x.klasterProv.map(function (r) {
          return '<tr><td>' + r.nama + '</td><td><span class="pill ' + PILL[r.klaster] + '">' + r.label + '</span></td></tr>'; }).join('');
        
        if (x.klaster.length) {
          var cards = $$('#p-klaster .cluster-card'), tot = x.klasterTotal || x.klaster.reduce(function (a, k) { return a + k.wilayah; }, 0);
          x.klaster.forEach(function (k) {
            var c = cards[k.id]; if (!c) return; var bs = $$('.cc-stat b', c);
            setEl(c.querySelector('.cc-title'), 'Klaster ' + k.id); setEl(c.querySelector('.cc-subtitle'), k.pendek);
            if (bs[0]) bs[0].textContent = fmt(k.wilayah);
            if (bs[1]) bs[1].textContent = (k.wilayah / tot * 100).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + '%';
          });
          setText('#p-klaster .page-head p', 'Pengelompokan ' + fmt(tot) + ' wilayah berdasarkan karakteristik dampak bencana (K-Means, k=' + x.klaster.length + ')');
        }

        var a = x.aktual, f = x.forecast, labels = a.labels.slice(), pad = function (n) { return new Array(n).fill(null); };
        var ds = [{ 
            label: 'Aktual', 
            data: a.values.concat(f ? pad(f.labels.length) : []), 
            borderColor: '#1F3A5F', // Warna Navy (Sesuai legenda)
            backgroundColor: 'transparent', 
            tension: 0.3, 
            pointRadius: 1.5, 
            borderWidth: 2.5,
            pointBackgroundColor: '#1F3A5F'
        }];
        
        if (f) {
          labels = labels.concat(f.labels);
          ds.push({ 
              label: 'Prediksi', 
              data: pad(a.labels.length).concat(f.prediksi), 
              borderColor: '#3A86FF', // Warna Biru (Sesuai legenda)
              borderDash: [6, 4], 
              backgroundColor: 'transparent', 
              tension: 0.3, 
              pointRadius: 2,
              borderWidth: 2.5,
              pointBackgroundColor: '#3A86FF'
          });
          ds.push({ 
              label: 'Interval', 
              data: pad(a.labels.length).concat(f.lower), 
              borderColor: 'rgba(58,134,255,0.4)', 
              backgroundColor: 'rgba(58,134,255,0.15)', 
              fill: '+1', 
              pointRadius: 0 
          });
          ds.push({ 
              label: 'Batas Atas', 
              data: pad(a.labels.length).concat(f.upper), 
              borderColor: 'transparent', 
              fill: false, 
              pointRadius: 0 
          });
          
          var ft = $$('#p-tren table.tbl')[1];
          if (ft) ft.querySelector('tbody').innerHTML = f.labels.map(function (l, i) {
            return '<tr><td>' + l + '</td><td>' + fmt(f.prediksi[i]) + '</td><td>' + fmt(f.lower[i]) + '</td><td>' + fmt(f.upper[i]) + '</td></tr>'; }).join('');
        }
        
        setChart('c-forecast', { 
          type: 'line', 
          data: { labels: labels, datasets: ds },
          options: { 
            interaction: { mode: 'index', intersect: false }, 
            plugins: { 
              legend: { display: false }, 
              tooltip: { 
                callbacks: { 
                  label: function(c){ return ' '+c.dataset.label+': '+(c.parsed.y==null?'-':c.parsed.y.toLocaleString('id-ID')); } 
                } 
              } 
            },
            scales: { 
              y: { beginAtZero: true, grid: { color: '#F2F4F7' }, border:{display:false} }, 
              x: { grid: { display: false }, ticks: { maxTicksLimit: 12 }, border:{display:false} } 
            } 
          } 
        });
        
        setText('#p-tren .card-head p', 'Laporan per bulan dari BNPB, ' + a.labels[0] + ' sampai ' + a.labels[a.labels.length - 1] +
          (f ? ', ditambah prediksi ke depan.' : '. Prediksi belum tersedia: letakkan forecast.csv di data/processed.'));
        if (!f) { var ft2 = $$('#p-tren table.tbl')[1]; if (ft2) ft2.querySelector('tbody').innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--muted)">Belum ada hasil prediksi.</td></tr>'; }
        setText('#p-tren .grid-2e .card:nth-child(2) p[style*="center"]', 'Rata-rata laporan per bulan, ' + x.seasonal.periode + '.');
        afterRender();
      }).catch(function (e) { console.error('Extra gagal:', e); });
    }

    /* 7b. Laporan */
    function loadLaporan() {
      return api('/api/laporan').then(function (items) {
        var box = $('#p-laporan .card'); if (!box) return;
        box.innerHTML = items.map(function (it) {
          return '<div class="report-card" style="padding:20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:12px">' +
            '<div style="display:flex;gap:16px;align-items:center"><div style="width:48px;height:48px;border-radius:12px;background:#E8F1FB;display:flex;align-items:center;justify-content:center;color:var(--blue);font-size:11px;font-weight:800">' + it.tipe + '</div>' +
            '<div><b style="font-size:15px;color:var(--ink);display:block;margin-bottom:4px">' + it.judul + '</b><span style="font-size:12px;color:var(--muted)">' + it.deskripsi + '</span></div></div>' +
            '<a class="btn-download" style="text-decoration:none" download href="' + API + '/api/unduh/' + encodeURIComponent(it.kode) + '">Unduh</a></div>'; }).join('');
      }).catch(function (e) { console.error('Laporan gagal:', e); });
    }

    /* 8. Prediksi & mitigasi */
    var simJenis = $('#sim-jenis'), simProv = $('#sim-prov'), simBulan = $('#sim-bulan'), simKep = $('#sim-kepadatan');
    var LBL = ['Tanpa Dampak', 'Ringan', 'Sedang', 'Berat'];

    function hitungPrediksi() {
      var jenis = simJenis ? simJenis.value : 'Banjir', prov = simProv ? simProv.value : 'Jawa Tengah';
      var bulan = simBulan ? simBulan.value : 'Januari', kep = simKep ? simKep.value : 'Sedang';
      var box = $('#sim-result'), st = $('#sim-status');
      setText('#sim-val', 'Memproses model ML...'); if (box) box.classList.add('loading'); if (st) st.hidden = true;

      api('/api/prediksi', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jenis_bencana: jenis, provinsi: prov, bulan: bulan, kepadatan: kep }) })
      .then(function (d) {
        var t = d.tingkat;
        setText('#sim-val', d.label);
        var bar = $('#sim-bar'); if (bar) { bar.style.width = ((t + 1) * 25) + '%'; bar.style.background = ['#0E9384', '#3A86FF', '#F4A259', '#D92D20'][t]; }
        var pr = $('#sim-proba');
        if (pr) pr.innerHTML = d.probabilitas.map(function (p, i) { return '<span class="' + (i === t ? 'on' : '') + '">' + LBL[i] + ' ' + p + '%</span>'; }).join('');
        setText('#sim-korban', fmt(d.korban) + ' jiwa'); setText('#sim-terdampak', fmt(d.terdampak) + ' jiwa'); setText('#sim-rusak', fmt(d.rusak) + ' unit');
        var r = d.rentang;
        setText('#sim-korban-d', r ? 'rentang tipikal ' + fmt(r.korban[0]) + '–' + fmt(r.korban[1]) : '');
        setText('#sim-terdampak-d', r ? 'rentang tipikal ' + fmt(r.terdampak[0]) + '–' + fmt(r.terdampak[1]) : '');
        setText('#sim-rusak-d', r ? 'rentang tipikal ' + fmt(r.rusak[0]) + '–' + fmt(r.rusak[1]) : '');
        setText('#sim-basis', d.n_historis
          ? 'Tingkat dampak dari model Random Forest. Estimasi angka = median ' + fmt(d.n_historis) + ' laporan BNPB historis (' + d.basis_estimasi + ').'
          : 'Tingkat dampak dari model Random Forest. Estimasi angka tidak tersedia: ' + d.basis_estimasi + '.');
        renderMitigasi(t, d.label, jenis, prov, kep);
      })
      .catch(function (e) {
        console.error('Prediksi gagal:', e);
        setText('#sim-val', 'Prediksi gagal');
        if (st) { st.hidden = false; st.textContent = 'Gagal memuat prediksi: ' + e.message + '. Pastikan backend berjalan di ' + API + '.'; }
      })
      .then(function () { if (box) box.classList.remove('loading'); });
    }

    function renderMitigasi(t, label, jenis, prov, kep) {
      var list = $('#mitigation-list'), badge = $('#mitigasi-badge'); if (!list) return;
      var it = [];
      if (t >= 3) {
        it.push({ u: 1, t: 'Evakuasi & peringatan dini', d: 'Aktifkan sirene, evakuasi zona merah, dan siagakan posko darurat di ' + prov + '.' });
        it.push({ u: 1, t: 'Logistik darurat', d: 'Siapkan tenda, air bersih, dan obat-obatan untuk warga terdampak.' });
        it.push({ u: 0, t: 'Koordinasi lintas sektor', d: 'Libatkan BNPB, TNI/Polri, dan relawan untuk respons cepat.' });
      } else if (t === 2) {
        it.push({ u: 1, t: 'Peningkatan kesiapsiagaan', d: 'Cek jalur evakuasi dan pastikan posko siaga di ' + prov + '.' });
        it.push({ u: 0, t: 'Sosialisasi warga', d: 'Edukasi mitigasi ' + jenis.toLowerCase() + ' untuk warga.' });
      } else {
        it.push({ u: 0, t: 'Pemantauan rutin', d: 'Pantau prakiraan cuaca dan kondisi lingkungan di ' + prov + '.' });
        it.push({ u: 0, t: 'Kesiapsiagaan dasar', d: 'Pastikan perlengkapan darurat keluarga tersedia.' });
      }
      if (jenis === 'Banjir') it.push({ u: 0, t: 'Normalisasi drainase', d: 'Bersihkan saluran air dan sungai di area rawan.' });
      if (jenis === 'Tanah longsor') it.push({ u: 0, t: 'Penguatan lereng', d: 'Pasang bronjong dan tanam vegetasi penahan di lereng rawan.' });
      if (jenis === 'Karhutla') it.push({ u: 0, t: 'Patroli api', d: 'Tingkatkan patroli dan deteksi titik panas di lahan gambut.' });
      if (kep === 'Tinggi' || kep === 'Sangat tinggi') it.push({ u: 0, t: 'Zonasi tata ruang', d: 'Perketat izin bangunan di zona rawan bencana.' });
      list.innerHTML = it.map(function (x) {
        return '<li class="' + (x.u ? 'urgent' : '') + '"><span class="m-icon">' + (x.u ? '!' : '✓') + '</span><div><b>' + x.t + '</b>' + x.d + '</div></li>'; }).join('');
      if (badge) { badge.textContent = label; badge.className = 'pill ' + ['green', 'blue', 'orange', 'red'][t]; }
      setText('#kpi-tingkat', t + 1); setText('#kpi-rekomendasi', it.length);
    }
    [simJenis, simProv, simBulan, simKep].forEach(function (el) { if (el) el.addEventListener('change', hitungPrediksi); });

    /* 9. Export & pencarian */
    var ex = $('#btn-export');
    if (ex) ex.addEventListener('click', function () {
      var rows = [['Provinsi', 'Kejadian']].concat(DATA.topProvinsi.map(function (r) { return [r.nama, r.nilai]; }));
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([rows.map(function (r) { return r.join(','); }).join('\n')], { type: 'text/csv;charset=utf-8;' }));
      a.download = 'disasterwatch-export.csv'; a.click();
    });
    var si = $('#search-input');
    if (si) si.addEventListener('input', function () {
      var q = this.value.toLowerCase().trim();
      var rows = DATA.topProvinsi.filter(function (r) { return r.nama.toLowerCase().indexOf(q) !== -1; });
      renderTopProvinsi(rows.length ? rows : DATA.topProvinsi);
    });

    /* 10. Mulai */
    var autoChk = $('#set-autorefresh'), timer = null;
    function setAuto(on) {
      try { localStorage.setItem('dw-auto', on ? '1' : '0'); } catch (e) {}
      clearInterval(timer);
      if (on) timer = setInterval(function () { loadOverview(); loadMeta(); loadExtra(); loadPeta(); loadLaporan(); }, 300000);
    }
    if (autoChk) {
      var sa = null; try { sa = localStorage.getItem('dw-auto'); } catch (e) {}
      autoChk.checked = sa === '1'; setAuto(autoChk.checked);
      autoChk.addEventListener('change', function () { setAuto(autoChk.checked); });
    }

    // Inisialisasi Global Chart.js untuk gaya Storytelling
    if (hasChart) {
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.font.size = 12;
        Chart.defaults.color = '#667085';
        Chart.defaults.plugins.tooltip.backgroundColor = '#0F1B2D';
        Chart.defaults.plugins.tooltip.titleFont = { size: 13, weight: 'bold' };
        Chart.defaults.plugins.tooltip.bodyFont = { size: 13 };
        Chart.defaults.plugins.tooltip.padding = 10;
        Chart.defaults.plugins.tooltip.cornerRadius = 8;
    }

    loadOverview(); loadMeta(); loadExtra(); loadPeta(); loadLaporan(); hitungPrediksi();
    setText('#model-badge', 'Random Forest');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', main); else main();
})();