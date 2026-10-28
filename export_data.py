import pandas as pd
import json
import os

csv_path = 'data/processed/bnpb_bencana_2015-01-01_2026-10-28.csv'
print("Membaca data (bisa memakan waktu 10-20 detik)...")
df = pd.read_csv(csv_path, low_memory=False)

# --- 1. KPI Utama ---
total_kejadian = len(df)
total_meninggal = int(df['meninggal'].fillna(0).sum())
total_rumah_rusak = int(df['rumah_rusak'].fillna(0).sum())
total_provinsi = df['provinsi'].nunique()

if total_rumah_rusak > 1000000:
    rumah_str = f"{total_rumah_rusak/1000000:.1f} jt".replace('.', ',')
elif total_rumah_rusak > 1000:
    rumah_str = f"{total_rumah_rusak/1000:.0f} rb"
else:
    rumah_str = str(total_rumah_rusak)

# --- 2. Tren Bulanan (Filter 2026) ---
df_2026 = df[df['tahun'] == 2026] if 'tahun' in df.columns else df
monthly_trend = [0] * 12
if not df_2026.empty and 'bulan' in df_2026.columns:
    bulan_counts = df_2026.groupby('bulan').size()
    for b, count in bulan_counts.items():
        if 1 <= int(b) <= 12:
            monthly_trend[int(b)-1] = int(count)

# --- 3. Komposisi Bencana ---
komposisi = df['kejadian'].value_counts().head(7)
komposisi_labels = komposisi.index.tolist()
komposisi_data = [int(x) for x in komposisi.values.tolist()]

# --- 4. Top 5 Provinsi ---
top_prov = df['provinsi'].value_counts().head(5)
top_prov_labels = top_prov.index.tolist()
top_prov_data = [int(x) for x in top_prov.values.tolist()]

# --- 5. Data Peta (Ambil 200 titik acak yang ada koordinatnya) ---
map_df = df.dropna(subset=['latitude', 'longitude'])
# Ambil sampel max 200 titik biar browser ga lag
map_sample = map_df.sample(n=min(200, len(map_df)), random_state=42)
map_points = []
for _, row in map_sample.iterrows():
    map_points.append({
        "lat": float(row['latitude']),
        "lng": float(row['longitude']),
        "jenis": str(row['kejadian']),
        "prov": str(row['provinsi'])
    })

# --- 6. Data Klaster (Baca dari CSV hasil modelling) ---
cluster_path = 'data/processed/cluster_profiles.csv'
cluster_data = []
if os.path.exists(cluster_path):
    cdf = pd.read_csv(cluster_path)
    # Konversi ke list of dicts, ganti NaN jadi string kosong
    cluster_data = cdf.fillna("").to_dict(orient='records')

# Bungkus jadi JSON
data_json = {
    "kpi": {"total": total_kejadian, "meninggal": total_meninggal, "rumah": rumah_str, "prov": total_provinsi},
    "monthly": monthly_trend,
    "komposisi": {"labels": komposisi_labels, "data": komposisi_data},
    "top_prov": {"labels": top_prov_labels, "data": top_prov_data},
    "map_points": map_points,
    "clusters": cluster_data
}

os.makedirs('frontend/js', exist_ok=True)
with open('frontend/js/data_asli.js', 'w', encoding='utf-8') as f:
    f.write(f"window.DATA_ASLI = {json.dumps(data_json, indent=2)};")

print(f"✅ Berhasil! Total Peta: {len(map_points)} titik.")