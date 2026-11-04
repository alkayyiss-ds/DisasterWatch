import pandas as pd
import json
import os

csv_path = 'data/processed/bnpb_disaster_clean.csv'
if not os.path.exists(csv_path):
    csv_path = 'data/processed/bnpb_bencana_2015-01-01_2026-10-28.csv'

print(f"Membaca data dari: {csv_path}...")
df = pd.read_csv(csv_path, low_memory=False)

# 1. KPI Utama
total_kejadian = len(df)
total_meninggal = int(df['meninggal'].fillna(0).sum()) if 'meninggal' in df.columns else 0
total_rumah_rusak = int(df['rumah_rusak'].fillna(0).sum()) if 'rumah_rusak' in df.columns else 0
total_provinsi = df['provinsi'].nunique() if 'provinsi' in df.columns else 0

if total_rumah_rusak > 1000000: rumah_str = f"{total_rumah_rusak/1000000:.1f} jt".replace('.', ',')
elif total_rumah_rusak > 1000: rumah_str = f"{total_rumah_rusak/1000:.0f} rb"
else: rumah_str = str(total_rumah_rusak)

# 2. Top 5 Provinsi (INI YANG HILANG)
top_prov = df['provinsi'].value_counts().head(5)
top_prov_labels = top_prov.index.tolist()
top_prov_data = [int(x) for x in top_prov.values.tolist()]

# 3. Agregat per Tahun
tahun_agg = {}
for th in df['tahun'].unique():
    if pd.isna(th): continue
    th = int(th)
    df_th = df[df['tahun'] == th]
    t_kej = len(df_th)
    t_men = int(df_th['meninggal'].fillna(0).sum())
    t_rum = int(df_th['rumah_rusak'].fillna(0).sum())
    
    if t_rum > 1000000: t_rum_str = f"{t_rum/1000000:.1f} jt".replace('.', ',')
    elif t_rum > 1000: t_rum_str = f"{t_rum/1000:.0f} rb"
    else: t_rum_str = str(t_rum)
    
    monthly = [0]*12
    for b, count in df_th.groupby('bulan').size().items():
        if 1 <= int(b) <= 12: monthly[int(b)-1] = int(count)
    
    tahun_agg[str(th)] = {
        "total": t_kej, "meninggal": t_men, "rumah": t_rum_str, "prov": df_th['provinsi'].nunique(),
        "monthly": monthly
    }

# 4. Agregat per Jenis
jenis_col = 'kejadian' if 'kejadian' in df.columns else 'jenis_bencana'
jenis_agg = {}
for jns in df[jenis_col].dropna().unique():
    df_jns = df[df[jenis_col] == jns]
    jenis_agg[jns] = {
        "total": len(df_jns),
        "meninggal": int(df_jns['meninggal'].fillna(0).sum())
    }

# 5. Agregat per Provinsi
prov_agg = {}
for prov in df['provinsi'].dropna().unique():
    df_prov = df[df['provinsi'] == prov]
    prov_agg[prov] = {
        "total": len(df_prov),
        "meninggal": int(df_prov['meninggal'].fillna(0).sum())
    }

# 6. Data Peta
map_df = df.dropna(subset=['latitude', 'longitude'])
map_sample = map_df.sample(n=min(200, len(map_df)), random_state=42)
map_points = []
for _, row in map_sample.iterrows():
    map_points.append({
        "lat": float(row['latitude']), "lng": float(row['longitude']),
        "jenis": str(row.get(jenis_col, 'BENCANA')), "prov": str(row.get('provinsi', 'INDONESIA'))
    })

# 7. Komposisi
komposisi = df[jenis_col].value_counts().head(7)
komposisi_labels = komposisi.index.tolist()
komposisi_data = [int(x) for x in komposisi.values.tolist()]

# 8. Klaster
cluster_path = 'data/processed/cluster_profiles.csv'
cluster_data = []
if os.path.exists(cluster_path):
    cdf = pd.read_csv(cluster_path)
    cluster_data = cdf.fillna(0).to_dict(orient='records')

# 9. Bungkus JSON
data_json = {
    "kpi": {"total": total_kejadian, "meninggal": total_meninggal, "rumah": rumah_str, "prov": total_provinsi},
    "komposisi": {"labels": komposisi_labels, "data": komposisi_data},
    "top_prov": {"labels": top_prov_labels, "data": top_prov_data},
    "tahun_agg": tahun_agg,
    "jenis_agg": jenis_agg,
    "prov_agg": prov_agg,
    "map_points": map_points,
    "clusters": cluster_data,
    "monthly": tahun_agg.get('2026', {}).get('monthly', [0]*12) # Fallback untuk grafik awal
}

os.makedirs('frontend/js', exist_ok=True)
with open('frontend/js/data_asli.js', 'w', encoding='utf-8') as f:
    f.write(f"window.DATA_ASLI = {json.dumps(data_json, indent=2, ensure_ascii=False)};")

print("✅ Berhasil! Data lengkap disimpan.")