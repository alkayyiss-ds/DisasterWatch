/* DisasterWatch — app.js (Final) */
(function () {
  'use strict';

  function main() {
    var $ = function (s, r) { return (r || document).querySelector(s); };
    var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
    var fmt = function (n) { return (n == null ? '–' : Number(n).toLocaleString('id-ID')); };
    var hasChart = typeof window.Chart !== 'undefined';
    var hasLeaflet = typeof window.L !== 'undefined';
    var charts = {};
    var DATA = { topProvinsi: [], petaOverview: [], petaWilayah: [] };

    /* Guard: pastikan data.js sudah termuat */
    var DW = window.DW;
    if (!DW) {
      console.error("data.js tidak termuat. Pastikan js/data.js ada dan dipanggil sebelum app.js di index.html.");
      return;
    }

    /* Penghubung ke data statis (js/data.js) */
    function api(url, opts) {
      var u = url.split('?'), q = {};
      (u[1] || '').split('&').forEach(function (kv) { if (kv) { var p = kv.split('='); q[p[0]] = decodeURIComponent(p[1] || ''); } });
      var int = function (v, d) { var n = parseInt(v, 10); return isNaN(n) ? d : n; };
      try {
        switch (u[0]) {
          case '/api/overview': return DW.overview({ tahun: int(q.tahun, 0), dari: int(q.dari, 0), jenis: q.jenis || 'semua', provinsi: q.provinsi || 'semua' });
          case '/api/dashboard-data': return DW.dashboard();
          case '/api/extra': return DW.extra();
          case '/api/tren': return DW.tren({ seri: q.seri, model: q.model || 'auto', horizon: int(q.horizon, 12) });
          case '/api/laporan': return DW.laporan();
          case '/api/prediksi': return DW.prediksi(JSON.parse(opts.body));
        }
      } catch (e) { return Promise.reject(e); }
      return Promise.reject(new Error('Endpoint tidak dikenal: ' + url));
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

    /* 2b. Tombol Pengaturan di Topbar */
    var btnSettingsTop = $('#btn-settings-top');
    if (btnSettingsTop) {
      btnSettingsTop.addEventListener('click', function () { 
        showPage('pengaturan'); 
      });
    }

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

    /* 4. Dark mode & Pengaturan */
    var darkChk = $('#setting-darkmode');
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
    if (darkChk) { 
      darkChk.checked = saved === '1'; 
      darkChk.addEventListener('change', function () { setDark(darkChk.checked); }); 
    }
    if (saved === '1') setDark(true);

    /* 4b. Tema Warna Aksen */
    var themeBtns = $$('.theme-btn');
    function setTheme(theme) {
      // Hapus semua class theme-*
      document.body.className = document.body.className.replace(/theme-\w+/g, '').trim();
      // Tambahkan class baru (kecuali biru, karena biru default)
      if (theme && theme !== 'blue') document.body.classList.add('theme-' + theme);
      
      // Update tombol aktif
      themeBtns.forEach(function(btn) {
        btn.classList.toggle('active', btn.getAttribute('data-theme') === theme);
      });
      
      // Simpan ke localStorage
      try { localStorage.setItem('dw-theme', theme); } catch (e) {}
      
      // Update warna grafik (jika ada)
      if (hasChart && typeof Chart !== 'undefined') {
        var newColor = getComputedStyle(document.body).getPropertyValue('--blue').trim();
        Object.keys(charts).forEach(function(k) {
          var c = charts[k];
          if (c.data.datasets) {
            c.data.datasets.forEach(function(ds) {
              // Ubah borderColor dan backgroundColor yang bernilai biru default
              if (ds.borderColor === '#2E75B6' || ds.borderColor === '#3A86FF') ds.borderColor = newColor;
              if (ds.backgroundColor === '#2E75B6') ds.backgroundColor = newColor;
            });
          }
          c.update();
        });
      }
    }

    // Bind klik ke setiap tombol tema
    themeBtns.forEach(function(btn) {
      btn.addEventListener('click', function() {
        setTheme(btn.getAttribute('data-theme'));
      });
    });

    // Load tema tersimpan
    var savedTheme = null; try { savedTheme = localStorage.getItem('dw-theme'); } catch (e) {}
    if (savedTheme) setTheme(savedTheme);

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
        setText('#kpi-total', fmt(r.kpi.total)); setText('#kpi-meninggal', fmt(r.kpi.meninggal));
        setText('#kpi-rumah', fmt(r.kpi.rumah)); setText('#kpi-prov', fmt(r.kpi.prov));
        [['kpi-total', 'total'], ['kpi-meninggal', 'meninggal'], ['kpi-rumah', 'rumah']].forEach(function (x) {
          var foot = $('#' + x[0]).parentNode.querySelector('.kpi-foot'); if (foot) foot.innerHTML = trendHtml(r.trend[x[1]], r.pembanding);
        });
        var pf = $('#kpi-prov').parentNode.querySelector('.kpi-foot'); if (pf) pf.textContent = 'dari 38 provinsi';
        setText('#p-overview .grid-2 .card-head p', 'Data tahun ' + r.tahun);

        setChart('c-monthly', { type: 'line', data: { labels: r.monthly.labels, datasets: [{ label: 'Kejadian', data: r.monthly.values,
          borderColor: '#2E75B6', backgroundColor: 'rgba(46,117,182,0.12)', fill: true, tension: 0.35, pointRadius: 3 }] },
          options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } } });
        setChart('c-komposisi', { type: 'doughnut', data: { labels: r.komposisi.labels, datasets: [{ data: r.komposisi.values,
          backgroundColor: ['#2E75B6', '#F4A259', '#0E9384', '#D92D20', '#8A9BB8', '#7A5AF8', '#3A86FF', '#FB5607', '#667085'] }] },
          options: { plugins: { legend: { position: 'bottom' } } } });

        DATA.topProvinsi = r.topProvinsi.map(function (i) { return { nama: i.provinsi, nilai: i.jumlah_kejadian }; });
        renderTopProvinsi(DATA.topProvinsi);
        DATA.petaOverview = r.petaTitik; drawMaps(); afterRender();
      }).catch(function (e) { console.error('Overview gagal:', e); });
    }
    [fTahun, fJenis, fProv].forEach(function (el) { if (el) el.addEventListener('change', loadOverview); });
    if (fReset) fReset.addEventListener('click', function () {
      if (fTahun) fTahun.selectedIndex = 0; if (fJenis) fJenis.value = 'semua'; if (fProv) fProv.value = 'semua'; loadOverview();
    });

    /* 6. Peta Wilayah */
    var mapJenis = $('#map-filter-jenis'), mapPeriode = $('#map-filter-periode');
    function loadPeta() {
      var dari = mapPeriode ? (parseInt(mapPeriode.value, 10) || 0) : 0;
      return api('/api/overview?tahun=-1&dari=' + dari + '&jenis=' + encodeURIComponent(mapJenis ? mapJenis.value : 'semua')).then(function (r) {
        DATA.petaWilayah = r.petaTitik; drawMaps();
        var kab = $('#top-kab-tbody');
        if (kab) kab.innerHTML = r.topKab.map(function (k, i) {
          return '<tr><td><span class="rank">' + (i + 1) + '</span>' + k.nama + '</td><td>' + fmt(k.n) + '</td></tr>'; }).join('');
      }).catch(function (e) { console.error('Peta gagal:', e); });
    }
    [mapJenis, mapPeriode].forEach(function (el) { if (el) el.addEventListener('change', loadPeta); });

    /* 7. Model Metadata */
    function loadMeta() {
      return api('/api/dashboard-data').then(function (r) {
        setText('#kpi-akurasi', r.kpi.akurasi + '%'); setText('#kpi-wilayah', fmt(r.kpi.wilayah));
        if (r.feature && r.feature.labels.length) {
          setChart('c-feature', { type: 'bar', data: { labels: r.feature.labels, datasets: [{ data: r.feature.values,
            backgroundColor: ['#2E75B6', '#3A86FF', '#F4A259', '#0E9384', '#8A9BB8'] }] },
            options: { indexAxis: 'y', plugins: { legend: { display: false } } } });
        }
        afterRender();
      }).catch(function (e) { console.error('Meta gagal:', e); });
    }

    /* 8. Extra Data (Klaster & Dominan) */
    var PILL = ['green', 'blue', 'orange', 'red'];
    function loadExtra() {
      return api('/api/extra').then(function (x) {
        setChart('c-dominan', { type: 'bar', data: { labels: x.dominan.labels, datasets: [
          { label: 'Banjir', data: x.dominan.banjir, backgroundColor: '#2E75B6' },
          { label: 'Cuaca ekstrem', data: x.dominan.cuaca, backgroundColor: '#F4A259' },
          { label: 'Tanah longsor', data: x.dominan.longsor, backgroundColor: '#0E9384' }] },
          options: { plugins: { legend: { position: 'bottom' } }, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } } } });

        if (x.klasterImpact) setChart('c-cluster-impact', { type: 'bar', data: { labels: x.klasterImpact.labels, datasets: [
          { label: 'Korban jiwa', data: x.klasterImpact.korban, backgroundColor: '#D92D20' },
          { label: 'Terdampak', data: x.klasterImpact.terdampak, backgroundColor: '#3A86FF' }] },
          options: { plugins: { legend: { position: 'bottom' } } } });

        var ktb = $('#klaster-ringkasan');
        if (ktb && x.klaster.length) ktb.innerHTML = x.klaster.map(function (k) {
          return '<tr><td>Klaster ' + k.id + ' — ' + k.nama + '</td><td>' + fmt(k.wilayah) + '</td></tr>'; }).join('');
        var kp = $('#klaster-prov-tbody');
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

        afterRender();
      }).catch(function (e) { console.error('Extra gagal:', e); });
    }

    /* 9. Tren & Prediksi — PAKAI ID BARU */
    var tSel = [ $('#tren-seri'), $('#tren-model'), $('#tren-horizon') ].filter(Boolean);
    var tChecks = [ $('#chk-aktual'), $('#chk-prediksi'), $('#chk-interval') ].filter(Boolean);
    var BLN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
    function bln(m) { var p = m.split('-'); return BLN[+p[1] - 1] + ' ' + p[0]; }
    function f1(x) { return x == null ? '–' : Number(x).toFixed(1).replace('.', ','); }
    function monthRange(a, b) {
      var out = [], y = +a.slice(0, 4), m = +a.slice(5), ey = +b.slice(0, 4), em = +b.slice(5);
      while (y < ey || (y === ey && m <= em)) { out.push(y + '-' + (m < 10 ? '0' : '') + m); if (++m > 12) { m = 1; y++; } }
      return out;
    }
    function fillSel(sel, pairs, cur) {
      if (!sel) return;
      sel.innerHTML = pairs.map(function (p) { return '<option value="' + p[0] + '">' + p[1] + '</option>'; }).join('');
      if (cur && pairs.some(function (p) { return p[0] === cur; })) sel.value = cur;
    }
    function applyChecks() {
      var c = charts['c-forecast']; if (!c) return;
      var mapping = [[0], [1, 2], [3, 4]]; // [Aktual], [Uji, Depan], [Lower, Upper]
      mapping.forEach(function (ids, g) {
        var on = !tChecks[g] || tChecks[g].checked;
        ids.forEach(function (i) { c.setDatasetVisibility(i, on); });
      });
      c.update();
    }
    var trenInit = false;
    function loadTren() {
      if (tSel.length < 3) return Promise.resolve();
      var q = '?seri=' + encodeURIComponent(tSel[0].value || 'NASIONAL') + '&model=' + encodeURIComponent(tSel[1].value || 'auto') +
              '&horizon=' + (parseInt(tSel[2].value, 10) || 12);
      return api('/api/tren' + q).then(function (r) {
        fillSel(tSel[0], r.opsi.seri.map(function (o) { return [o.kode, o.nama]; }), r.seri);
        fillSel(tSel[1], r.opsi.model.map(function (o) { return [o.kode, o.label]; }), tSel[1].value || 'auto');
        trenInit = true;
        var A = r.aktual, F = r.prediksi, U = r.uji;
        var last = F.labels.length ? F.labels[F.labels.length - 1] : A.labels[A.labels.length - 1];
        var labels = monthRange(A.labels[0], last);
        var on = function (L, V) { var m = {}; L.forEach(function (l, i) { m[l] = V[i]; }); return labels.map(function (l) { return l in m ? m[l] : null; }); };
        setChart('c-forecast', { type: 'line', data: { labels: labels, datasets: [
          { label: 'Aktual', data: on(A.labels, A.values), borderColor: '#1F3A5F', backgroundColor: 'transparent', tension: 0.25, pointRadius: 0, borderWidth: 2 },
          { label: 'Prediksi (data uji)', data: on(U.labels, U.pred), borderColor: '#3A86FF', borderDash: [6, 4], backgroundColor: 'transparent', tension: 0.25, pointRadius: 0 },
          { label: 'Prediksi ke depan', data: on(F.labels, F.pred), borderColor: '#3A86FF', borderDash: [2, 3], backgroundColor: 'transparent', tension: 0.25, pointRadius: 2 },
          { label: 'Batas bawah', data: on(F.labels, F.lower), borderColor: 'rgba(58,134,255,0.3)', backgroundColor: 'rgba(58,134,255,0.15)', fill: '+1', pointRadius: 0, tension: 0.25 },
          { label: 'Batas atas', data: on(F.labels, F.upper), borderColor: 'rgba(58,134,255,0.3)', fill: false, pointRadius: 0, tension: 0.25 }] },
          options: { plugins: { legend: { display: false } }, interaction: { mode: 'index', intersect: false },
                     scales: { y: { beginAtZero: true }, x: { ticks: { maxTicksLimit: 14 } } } } });
        applyChecks();

        // Update KPI Tren
        var m = r.model;
        setText('#kpi-mae', f1(m.mae));
        setText('#kpi-rmse', f1(m.rmse));
        setText('#kpi-mape', f1(m.mape) + '%');
        setText('#kpi-model', m.label);
        setText('#kpi-model-foot', m.terbaik ? 'Terbaik berdasarkan MAE pada data uji' : 'Bukan yang terbaik (terbaik: ' + m.terbaik_label + ')');

        // Tabel Model
        var tModel = $('#tbl-model tbody');
        if (tModel) tModel.innerHTML = r.tabel.map(function (x) {
          return '<tr' + (x.terbaik ? ' style="background:var(--blue-soft);font-weight:700"' : '') + '><td>' + x.label + '</td><td>' + f1(x.mae) + '</td><td>' + f1(x.rmse) + '</td><td>' + f1(x.mape) + '%</td></tr>'; }).join('');

        // Tabel Prediksi
        var tPred = $('#tbl-prediksi tbody');
        if (tPred) tPred.innerHTML = F.labels.map(function (l, i) {
          return '<tr><td>' + bln(l) + '</td><td>' + fmt(Math.round(F.pred[i])) + '</td><td>' + fmt(Math.round(F.lower[i])) + '</td><td>' + fmt(Math.round(F.upper[i])) + '</td></tr>'; }).join('');

        // Page Info
        setText('#p-tren .page-head p', 'Jumlah kejadian per bulan, ' + bln(A.labels[0]) + ' sampai ' + bln(A.labels[A.labels.length - 1]) +
                ', dan perkiraan ' + F.labels.length + ' bulan ke depan. Data: BNPB.');
        setText('#p-tren .card-head h3', 'Jumlah kejadian per bulan: ' + r.nama);
        setText('#p-tren .card-head p', 'Aktual BNPB dan prediksi model ' + m.label + (m.terbaik ? ' (terbaik pada data uji)' : ''));
        
        // Alert Kecil
        var al = $('#tren-alert'); if (al) al.hidden = !r.kecil;

        // Grafik Musiman
        setChart('c-seasonal', { type: 'bar', data: { labels: r.musiman.labels, datasets: [{ data: r.musiman.values, backgroundColor: '#3A86FF' }] },
          options: { plugins: { legend: { display: false } } } });
        setText('#musiman-note', 'Rata-rata kejadian per bulan, ' + r.musiman.periode + ': ' + r.nama + '.');
        
        // Unduh CSV
        var dl = $('#p-tren a[href="#"]'); if (dl) { dl.href = 'data/unduh/forecast_12_bulan.csv'; dl.setAttribute('download', ''); }
        afterRender();
      }).catch(function (e) { console.error('Tren gagal:', e); });
    }
    tSel.forEach(function (el, i) {
      el.addEventListener('change', function () { if (i === 0 && tSel[1]) tSel[1].value = 'auto'; loadTren(); });
    });
    tChecks.forEach(function (c) { c.addEventListener('change', applyChecks); });

    /* 10. Laporan */
    function loadLaporan() {
      return api('/api/laporan').then(function (items) {
        var box = $('#laporan-container'); if (!box) return;
        box.innerHTML = items.map(function (it) {
          return '<div class="report-card" style="padding:20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:12px">' +
            '<div style="display:flex;gap:16px;align-items:center"><div style="width:48px;height:48px;border-radius:12px;background:#E8F1FB;display:flex;align-items:center;justify-content:center;color:var(--blue);font-size:11px;font-weight:800">' + it.tipe + '</div>' +
            '<div><b style="font-size:15px;color:var(--ink);display:block;margin-bottom:4px">' + it.judul + '</b><span style="font-size:12px;color:var(--muted)">' + it.deskripsi + '</span></div></div>' +
            (it.url ? '<a class="btn-download" style="text-decoration:none" download href="' + it.url + '">Unduh</a>' : '<span style="font-size:12px;color:var(--muted)">Tidak disertakan</span>') + '</div>'; }).join('');
      }).catch(function (e) { console.error('Laporan gagal:', e); });
    }

    /* 11. Prediksi & Mitigasi */
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
        if (st) { st.hidden = false; st.textContent = 'Gagal memuat prediksi: ' + e.message + '. Pastikan folder data/ ada dan halaman dibuka lewat server (bukan file://).'; }
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

    /* 12. Export & pencarian */
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

    /* 13. Auto-refresh */
    var autoChk = $('#set-autorefresh'), timer = null;
    function setAuto(on) {
      try { localStorage.setItem('dw-auto', on ? '1' : '0'); } catch (e) {}
      clearInterval(timer);
      if (on) timer = setInterval(function () { loadOverview(); loadMeta(); loadExtra(); loadTren(); loadPeta(); loadLaporan(); }, 300000);
    }
    if (autoChk) {
      var sa = null; try { sa = localStorage.getItem('dw-auto'); } catch (e) {}
      autoChk.checked = sa === '1'; setAuto(autoChk.checked);
      autoChk.addEventListener('change', function () { setAuto(autoChk.checked); });
    }

    loadOverview(); loadMeta(); loadExtra(); loadTren(); loadPeta(); loadLaporan(); hitungPrediksi();
    setText('#model-badge', 'Random Forest');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', main); else main();
})();