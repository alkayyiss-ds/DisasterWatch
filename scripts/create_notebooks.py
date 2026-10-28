from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "notebook"
OUT.mkdir(exist_ok=True)

def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}

def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(True)}

def write(name, cells):
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.x"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (OUT / name).write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")

write("eda_disaster.ipynb", [
    md("""
    # EDA DisasterWatch

    Exploratory Data Analysis data bencana BNPB periode **1 Januari 2026 sampai 21 Oktober 2026**.
    Notebook ini membaca data hasil download dari `data/processed/`.
    """),
    code("""
    from pathlib import Path
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    from IPython.display import display
    
    sns.set_theme(style="whitegrid")
    pd.set_option("display.max_columns", 120)
    ROOT = Path.cwd().parent if Path.cwd().name == "notebook" else Path.cwd()
    DATA = sorted((ROOT / "data" / "processed").glob("bnpb_bencana_*.csv"))[-1]
    df = pd.read_csv(DATA, encoding="utf-8-sig")
    print(df.shape)
    df.head()
    """),
    md("## 1. Struktur dan kualitas data"),
    code("""
    df.info()
    display(df.describe(include="all").T)
    missing = (df.isna().mean().mul(100).sort_values(ascending=False)
               .to_frame("missing_pct"))
    display(missing.head(25))
    """),
    code("""
    date_cols = ["tahun", "bulan", "tanggal"]
    df[date_cols] = df[date_cols].apply(pd.to_numeric, errors="coerce")
    df["date"] = pd.to_datetime(dict(year=df.tahun, month=df.bulan, day=df.tanggal), errors="coerce")
    print("Tanggal:", df.date.min(), "s.d.", df.date.max())
    print("Duplikat baris penuh:", df.duplicated().sum())
    """),
    md("## 2. Distribusi kejadian"),
    code("""
    display(df["kejadian"].value_counts().to_frame("jumlah"))
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.countplot(data=df, y="kejadian", order=df.kejadian.value_counts().index, ax=ax)
    ax.set(title="Jumlah laporan berdasarkan jenis bencana", xlabel="Jumlah laporan", ylabel="")
    plt.tight_layout()
    """),
    code("""
    monthly = df.groupby(df.date.dt.to_period("M")).size().rename("jumlah").reset_index()
    monthly["date"] = monthly.date.dt.to_timestamp()
    ax = monthly.plot(x="date", y="jumlah", marker="o", figsize=(11, 4), legend=False)
    ax.set(title="Tren laporan bencana per bulan", xlabel="Bulan", ylabel="Jumlah laporan")
    plt.tight_layout()
    """),
    code("""
    top_prov = df.provinsi.value_counts().head(15).sort_values()
    top_prov.plot.barh(figsize=(9, 6), title="15 provinsi dengan laporan terbanyak")
    plt.xlabel("Jumlah laporan")
    plt.tight_layout()
    """),
    md("## 3. Dampak bencana dan koordinat"),
    code("""
    impact_cols = ["meninggal", "hilang", "terluka", "menderita", "mengungsi",
                   "rumah_rusak", "terendam", "lahan"]
    impact = df[impact_cols].apply(pd.to_numeric, errors="coerce").sum().sort_values(ascending=False)
    display(impact.to_frame("total"))
    print("Koordinat tersedia:", df[["geometry_lon", "geometry_lat"]].notna().all(axis=1).mean())
    """),
    md("## 4. Kualitas data dan potensi duplikasi"),
    code("""
    # Selain duplikasi penuh, cek indikasi laporan ganda berdasarkan kombinasi inti.
    key_cols = ["tahun", "bulan", "tanggal", "id_kab", "kejadian", "lokasi"]
    duplicate_groups = (df.groupby(key_cols, dropna=False).size()
                          .reset_index(name="jumlah_baris")
                          .query("jumlah_baris > 1")
                          .sort_values("jumlah_baris", ascending=False))
    print("Duplikasi baris penuh:", df.duplicated().sum())
    print("Grup indikasi laporan ganda:", len(duplicate_groups))
    print("Baris yang berada dalam grup ganda:", duplicate_groups.jumlah_baris.sum() if len(duplicate_groups) else 0)
    display(duplicate_groups.head(10))
    """),
    md("## 5. Tren waktu yang lebih dalam"),
    code("""
    # Heatmap jumlah laporan: bulan x jenis bencana.
    df["year_month"] = df.date.dt.to_period("M").astype(str)
    type_month = pd.crosstab(df["year_month"], df["kejadian"])
    plt.figure(figsize=(14, 6))
    sns.heatmap(type_month, annot=True, fmt="g", cmap="YlOrRd")
    plt.title("Heatmap laporan per bulan dan jenis bencana")
    plt.xlabel("Jenis bencana"); plt.ylabel("Bulan")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    display(type_month)
    """),
    code("""
    # Perubahan bulanan relatif terhadap bulan sebelumnya.
    monthly_type = (df.groupby(["year_month", "kejadian"]).size()
                      .unstack(fill_value=0).sort_index())
    monthly_change = monthly_type.pct_change().replace([np.inf, -np.inf], np.nan) * 100
    display(monthly_change.round(1).tail(5))
    """),
    md("## 6. Konsentrasi wilayah"),
    code("""
    province_counts = df["provinsi"].value_counts().rename("jumlah_laporan").to_frame()
    province_counts["persentase"] = province_counts.jumlah_laporan / len(df) * 100
    province_counts["persentase_kumulatif"] = province_counts.persentase.cumsum()
    display(province_counts.head(15).round(2))
    top5_share = province_counts.head(5).persentase.sum()
    top10_share = province_counts.head(10).persentase.sum()
    print(f"Top 5 provinsi menyumbang {top5_share:.1f}% laporan")
    print(f"Top 10 provinsi menyumbang {top10_share:.1f}% laporan")
    """),
    code("""
    top_province_type = (pd.crosstab(df.provinsi, df.kejadian)
                           .loc[province_counts.head(10).index])
    plt.figure(figsize=(13, 7))
    top_province_type.plot(kind="bar", stacked=True, figsize=(13, 7), colormap="tab20")
    plt.title("Komposisi jenis bencana pada 10 provinsi teratas")
    plt.xlabel(""); plt.ylabel("Jumlah laporan"); plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    """),
    md("## 7. Group by masing-masing jenis bencana"),
    code("""
    # Ringkasan utama untuk setiap jenis bencana.
    disaster_groupby = df.groupby("kejadian", dropna=False).agg(
        jumlah_laporan=("kejadian", "size"),
        jumlah_kejadian=("jumlah_kejadian", "sum"),
        provinsi_terdampak=("provinsi", "nunique"),
        kabkot_terdampak=("kabkot", "nunique"),
        meninggal=("meninggal", "sum"),
        hilang=("hilang", "sum"),
        terluka=("terluka", "sum"),
        menderita=("menderita", "sum"),
        mengungsi=("mengungsi", "sum"),
        rumah_rusak=("rumah_rusak", "sum"),
        terendam=("terendam", "sum"),
        lahan_ha=("lahan", "sum"),
    ).sort_values("jumlah_laporan", ascending=False)
    display(disaster_groupby.round(2))
    """),
    code("""
    # Group by jenis bencana dan provinsi: wilayah dominan untuk setiap bencana.
    disaster_province = (df.groupby(["kejadian", "provinsi"], dropna=False)
                           .agg(jumlah_laporan=("kejadian", "size"),
                                meninggal=("meninggal", "sum"),
                                mengungsi=("mengungsi", "sum"),
                                rumah_rusak=("rumah_rusak", "sum"),
                                terendam=("terendam", "sum"))
                           .reset_index()
                           .sort_values(["kejadian", "jumlah_laporan"], ascending=[True, False]))
    display(disaster_province.head(20))

    # Tampilkan top-5 provinsi secara terpisah untuk setiap jenis bencana.
    for disaster, group in disaster_province.groupby("kejadian", sort=True):
        print(f"\\n=== {disaster} ===")
        display(group.head(5).reset_index(drop=True))
    """),
    code("""
    # Group by jenis bencana dan bulan untuk melihat pola waktunya.
    disaster_month = (df.groupby(["kejadian", "year_month"], dropna=False)
                        .agg(jumlah_laporan=("kejadian", "size"),
                             jumlah_kejadian=("jumlah_kejadian", "sum"),
                             meninggal=("meninggal", "sum"),
                             mengungsi=("mengungsi", "sum"),
                             rumah_rusak=("rumah_rusak", "sum"))
                        .reset_index())
    display(disaster_month.sort_values(["kejadian", "year_month"]).head(30))
    """),
    md("## 8. Severity dan dampak per kejadian"),
    code("""
    numeric_impact = ["meninggal", "hilang", "terluka", "menderita", "mengungsi",
                      "rumah_rusak", "terendam", "lahan"]
    for col in numeric_impact:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["fatality_or_injury"] = df["meninggal"] + df["hilang"] + df["terluka"]
    df["people_affected"] = df["menderita"] + df["mengungsi"]
    df["has_human_impact"] = (df["fatality_or_injury"] + df["people_affected"] > 0).astype(int)
    severity_by_type = df.groupby("kejadian").agg(
        laporan=("kejadian", "size"),
        total_korban=("fatality_or_injury", "sum"),
        total_terdampak=("people_affected", "sum"),
        total_rumah_rusak=("rumah_rusak", "sum"),
        median_korban=("fatality_or_injury", "median"),
        persentase_berdampak=("has_human_impact", "mean"),
    ).sort_values("total_terdampak", ascending=False)
    severity_by_type["persentase_berdampak"] *= 100
    display(severity_by_type.round(2))
    """),
    code("""
    # Laporan paling berat menurut beberapa dimensi dampak.
    display(df.nlargest(10, "fatality_or_injury")[["date", "provinsi", "kabkot", "kejadian", "fatality_or_injury", "kronologis"]])
    display(df.nlargest(10, "people_affected")[["date", "provinsi", "kabkot", "kejadian", "people_affected", "kronologis"]])
    """),
    md("## 8. Korelasi dan pola dampak"),
    code("""
    corr_cols = ["meninggal", "hilang", "terluka", "menderita", "mengungsi", "rumah_rusak", "terendam", "lahan"]
    corr = df[corr_cols].corr()
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, square=True)
    plt.title("Korelasi antar indikator dampak")
    plt.tight_layout()
    display(corr.round(2))
    """),
    md("## 9. Analisis spasial sederhana"),
    code("""
    geo = df.dropna(subset=["geometry_lon", "geometry_lat"]).copy()
    geo["geometry_lon"] = pd.to_numeric(geo.geometry_lon, errors="coerce")
    geo["geometry_lat"] = pd.to_numeric(geo.geometry_lat, errors="coerce")
    geo = geo.dropna(subset=["geometry_lon", "geometry_lat"])
    print(f"Koordinat valid: {len(geo):,} dari {len(df):,} ({len(geo)/len(df)*100:.1f}%)")
    plt.figure(figsize=(12, 7))
    plt.scatter(geo.geometry_lon, geo.geometry_lat, s=8, alpha=.35, c=geo.fatality_or_injury, cmap="Reds")
    plt.colorbar(label="Meninggal + hilang + terluka")
    plt.title("Sebaran koordinat laporan bencana")
    plt.xlabel("Longitude"); plt.ylabel("Latitude")
    plt.tight_layout()
    """),
    md("## 10. Insight otomatis"),
    code("""
    top_type = df.kejadian.value_counts().idxmax()
    top_type_n = int(df.kejadian.value_counts().max())
    top_prov = df.provinsi.value_counts().idxmax()
    top_prov_n = int(df.provinsi.value_counts().max())
    peak_month = df.year_month.value_counts().idxmax()
    peak_month_n = int(df.year_month.value_counts().max())
    highest_fatality_type = severity_by_type.total_korban.idxmax()
    highest_affected_type = severity_by_type.total_terdampak.idxmax()
    print(f"1. Jenis bencana paling sering: {top_type} ({top_type_n:,} laporan).")
    print(f"2. Provinsi dengan laporan terbanyak: {top_prov} ({top_prov_n:,} laporan).")
    print(f"3. Bulan dengan laporan terbanyak: {peak_month} ({peak_month_n:,} laporan).")
    print(f"4. Jenis dengan total korban jiwa/cedera tertinggi: {highest_fatality_type}.")
    print(f"5. Jenis dengan total penduduk terdampak/pengungsi tertinggi: {highest_affected_type}.")
    print(f"6. Konsentrasi top-5 provinsi: {top5_share:.1f}% dari seluruh laporan.")
    print("Gunakan hasil ini sebagai hipotesis; validasi dengan kualitas pelaporan dan data pembanding sebelum mengambil keputusan.")
    """),
    md("## Kesimpulan dan pertanyaan analitik\n\nDokumentasikan temuan penting dari output di atas. Pertanyaan lanjutan yang dapat dijawab: mengapa terjadi lonjakan pada bulan tertentu, apakah konsentrasi wilayah mencerminkan risiko atau kelengkapan pelaporan, jenis bencana mana yang paling berat per laporan, dan bagaimana missing value memengaruhi kesimpulan?")
])

write("preprocessing_disaster.ipynb", [
    md("""
    # Preprocessing DisasterWatch

    Membersihkan tipe data, tanggal, nilai kosong, duplikasi, dan menyimpan dataset bersih.
    **Nilai kosong tidak otomatis dianggap nol** kecuali pada kolom dampak yang dipilih.
    """),
    code("""
    from pathlib import Path
    import pandas as pd
    import numpy as np
    
    ROOT = Path.cwd().parent if Path.cwd().name == "notebook" else Path.cwd()
    INPUT = sorted((ROOT / "data" / "processed").glob("bnpb_bencana_*.csv"))[-1]
    OUT = ROOT / "data" / "processed"
    df = pd.read_csv(INPUT, encoding="utf-8-sig")
    print("Sebelum:", df.shape)
    """),
    md("## 1. Standarisasi tipe data"),
    code("""
    numeric_cols = ["id_prov", "id_kab", "id_jenis_bencana", "tahun", "bulan", "tanggal",
                    "meninggal", "terluka", "hilang", "menderita", "mengungsi", "jumlah_kejadian",
                    "terendam", "rumah_rusak", "lahan", "longitude", "latitude"]
    for col in numeric_cols:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(dict(year=df.tahun, month=df.bulan, day=df.tanggal), errors="coerce")
    for col in ["provinsi", "kabkot", "kejadian", "lokasi"]:
        df[col] = df[col].astype("string").str.strip()
    df["kejadian"] = df["kejadian"].str.upper()
    """),
    md("## 2. Penanganan missing value dan duplikasi"),
    code("""
    # Kolom dampak yang kosong diperlakukan sebagai 0 hanya untuk kebutuhan agregasi/model.
    impact_cols = ["meninggal", "terluka", "hilang", "menderita", "mengungsi", "terendam",
                   "rumah_rusak", "lahan", "jumlah_kejadian"]
    for col in impact_cols:
        df[col] = df[col].fillna(0)
    df["has_coordinates"] = df[["longitude", "latitude"]].notna().all(axis=1)
    df = df.dropna(subset=["date", "kejadian", "provinsi", "kabkot"])
    before = len(df)
    df = df.drop_duplicates()
    print("Baris duplikat penuh dihapus:", before - len(df))
    print("Sesudah:", df.shape)
    """),
    md("## 3. Simpan dataset bersih"),
    code("""
    output = OUT / "bnpb_disaster_clean.csv"
    df.to_csv(output, index=False, encoding="utf-8-sig")
    print(output)
    display(df.head())
    """),
    md("### Catatan\nUntuk analisis dampak, bedakan antara nilai 0 (tidak ada dampak) dan nilai kosong (belum dilaporkan). Jika diperlukan, buat versi kedua yang mempertahankan `NaN`.")
])

write("feature_engineering.ipynb", [
    md("""
    # Feature Engineering DisasterWatch

    Membentuk fitur waktu, lokasi, dampak, dan agregasi wilayah dari dataset bersih.
    """),
    code("""
    from pathlib import Path
    import pandas as pd
    import numpy as np
    
    ROOT = Path.cwd().parent if Path.cwd().name == "notebook" else Path.cwd()
    INPUT = ROOT / "data" / "processed" / "bnpb_disaster_clean.csv"
    if not INPUT.exists():
        INPUT = ROOT / "data" / "processed" / "bnpb_disaster_clean.csv"
    OUT = ROOT / "data" / "processed"
    df = pd.read_csv(INPUT, encoding="utf-8-sig", parse_dates=["date"])
    print(df.shape)
    """),
    md("## 1. Fitur waktu"),
    code("""
    df["year"] = df.date.dt.year
    df["month"] = df.date.dt.month
    df["day"] = df.date.dt.day
    df["day_of_year"] = df.date.dt.dayofyear
    df["week_of_year"] = df.date.dt.isocalendar().week.astype(int)
    df["day_of_week"] = df.date.dt.dayofweek
    df["is_weekend"] = (df.day_of_week >= 5).astype(int)
    df["quarter"] = df.date.dt.quarter
    """),
    md("## 2. Fitur dampak dan lokasi"),
    code("""
    impact = ["meninggal", "terluka", "hilang", "menderita", "mengungsi", "terendam", "rumah_rusak", "lahan"]
    for col in impact:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["total_korban"] = df[["meninggal", "terluka", "hilang"]].sum(axis=1)
    df["total_terdampak"] = df[["menderita", "mengungsi"]].sum(axis=1)
    df["total_dampak_fisik"] = df[["rumah_rusak", "terendam", "lahan"]].sum(axis=1)
    df["has_coordinates"] = df[["longitude", "latitude"]].notna().all(axis=1).astype(int)
    """),
    md("## 3. Fitur frekuensi historis wilayah"),
    code("""
    df = df.sort_values("date")
    df["province_event_count"] = df.groupby("provinsi").cumcount() + 1
    df["kabkot_event_count"] = df.groupby("kabkot").cumcount() + 1
    df["type_event_count"] = df.groupby("kejadian").cumcount() + 1
    """),
    md("## 4. Agregasi data"),
    code("""
    # Agregasi dipisahkan dari data detail agar bisa dipakai untuk dashboard dan analisis tren.
    agg_metrics = {
        "jumlah_laporan": ("kejadian", "size"),
        "jumlah_kejadian": ("jumlah_kejadian", "sum"),
        "meninggal": ("meninggal", "sum"),
        "terluka": ("terluka", "sum"),
        "hilang": ("hilang", "sum"),
        "menderita": ("menderita", "sum"),
        "mengungsi": ("mengungsi", "sum"),
        "rumah_rusak": ("rumah_rusak", "sum"),
        "terendam": ("terendam", "sum"),
        "lahan": ("lahan", "sum"),
    }

    def aggregate(group_cols, filename):
        result = df.groupby(group_cols, dropna=False).agg(**agg_metrics).reset_index()
        result.to_csv(OUT / filename, index=False, encoding="utf-8-sig")
        print(f"{filename}: {result.shape}")
        return result

    # 1) Tren nasional per tanggal dan per bulan.
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    daily_agg = aggregate(["date"], "bnpb_aggregate_daily.csv")
    monthly_agg = aggregate(["year", "month", "year_month"], "bnpb_aggregate_monthly.csv")

    # 2) Rekap wilayah dan jenis bencana.
    province_agg = aggregate(["provinsi"], "bnpb_aggregate_province.csv")
    kabkot_agg = aggregate(["provinsi", "kabkot"], "bnpb_aggregate_kabkot.csv")
    type_agg = aggregate(["kejadian"], "bnpb_aggregate_type.csv")

    # 3) Dimensi gabungan untuk heatmap/pivot dashboard.
    province_type_agg = aggregate(["provinsi", "kejadian"], "bnpb_aggregate_province_type.csv")
    province_month_agg = aggregate(["year_month", "provinsi"], "bnpb_aggregate_province_month.csv")
    display(monthly_agg.head(), province_agg.head(), province_type_agg.head())
    """),
    md("## 5. Encoding kategorikal dan ekspor"),
    code("""
    model_cols = ["date", "year", "month", "day_of_year", "week_of_year", "day_of_week", "is_weekend",
                  "quarter", "provinsi", "kabkot", "kejadian", "longitude", "latitude", "has_coordinates",
                  "total_korban", "total_terdampak", "total_dampak_fisik", "province_event_count",
                  "kabkot_event_count", "type_event_count", "jumlah_kejadian"]
    features = df[[c for c in model_cols if c in df.columns]].copy()
    features.to_csv(OUT / "bnpb_disaster_features.csv", index=False, encoding="utf-8-sig")
    print("Disimpan:", features.shape)
    display(features.head())
    """),
    md("### Catatan leakage\nFitur agregat harus dihitung hanya dari data masa lalu saat modelling time-series. Jangan memakai kolom dampak jika target yang diprediksi adalah dampak yang sama. File agregasi yang dibuat: `bnpb_aggregate_daily.csv`, `bnpb_aggregate_monthly.csv`, `bnpb_aggregate_province.csv`, `bnpb_aggregate_kabkot.csv`, `bnpb_aggregate_type.csv`, `bnpb_aggregate_province_type.csv`, dan `bnpb_aggregate_province_month.csv`.")
])

write("modelling_disaster.ipynb", [
    md("""
    # Modelling DisasterWatch — baseline

    Baseline **klasifikasi jenis bencana (`kejadian`)**.

    Asumsi ini dibuat karena target bisnis belum ditentukan. Untuk use case prediksi korban,
    dampak, atau forecasting jumlah kejadian, ganti `TARGET` dan strategi split di bawah.
    """),
    code("""
    from pathlib import Path
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay
    from sklearn.model_selection import train_test_split
    
    ROOT = Path.cwd().parent if Path.cwd().name == "notebook" else Path.cwd()
    DATA = ROOT / "data" / "processed" / "bnpb_disaster_features.csv"
    df = pd.read_csv(DATA, encoding="utf-8-sig", parse_dates=["date"])
    TARGET = "kejadian"
    df = df.dropna(subset=[TARGET]).sort_values("date")
    print(df.shape, df[TARGET].value_counts())
    """),
    md("## 1. Siapkan fitur dan split temporal"),
    code("""
    # Hindari kolom target dan kolom yang berpotensi membocorkan target.
    # Karena target adalah jenis bencana, fitur dampak tetap dikeluarkan dari baseline.
    feature_cols = ["year", "month", "day_of_year", "week_of_year", "day_of_week", "is_weekend",
                    "quarter", "provinsi", "kabkot", "longitude", "latitude", "has_coordinates",
                    "province_event_count", "kabkot_event_count"]
    feature_cols = [c for c in feature_cols if c in df.columns]
    X, y = df[feature_cols], df[TARGET]
    split = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    print("Train:", X_train.shape, "Test:", X_test.shape)
    """),
    md("## 2. Pipeline preprocessing + model"),
    code("""
    categorical = [c for c in ["provinsi", "kabkot"] if c in X.columns]
    numerical = [c for c in feature_cols if c not in categorical]
    preprocessor = ColumnTransformer([
        ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numerical),
        ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")),
                          ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical),
    ])
    model = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced")),
    ])
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    print(classification_report(y_test, pred, zero_division=0))
    """),
    code("""
    labels = sorted(y_test.unique())
    ConfusionMatrixDisplay.from_predictions(y_test, pred, labels=labels, xticks_rotation=45, cmap="Blues")
    plt.tight_layout()
    """),
    md("## 3. Validasi dan langkah lanjutan\n\n- Bandingkan dengan baseline `DummyClassifier`.\n- Gunakan rolling/expanding time-series validation.\n- Tentukan target final: klasifikasi jenis bencana, regresi korban, atau forecasting per wilayah.\n- Audit leakage: jangan memakai fitur yang baru diketahui setelah kejadian jika model dimaksudkan untuk peringatan dini."),
])

print(f"Created notebooks in {OUT}")
