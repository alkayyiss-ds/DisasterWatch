#!/usr/bin/env python3
"""
DisasterWatch - forecasting jumlah laporan kejadian bencana bulanan Indonesia.

Dataset:
    01/01/2015 - 31/10/2026

Model:
    1. Seasonal Naive
    2. Prophet
    3. XGBoost

Evaluasi:
    Train    : 2015-01 s/d 2025-10
    Test     : 2025-11 s/d 2026-10
    Forecast : 2026-11 s/d 2027-10

Install:
    python -m pip install pandas numpy matplotlib openpyxl prophet xgboost scikit-learn

Run:
    python modeling_tren.py
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)


# ============================================================
# CONFIG
# ============================================================

SEASONAL_PERIOD = 12
LOW_FREQ_MEAN = 6.0
MIN_NONZERO_FOR_COMPLEX_MODELS = 36
XGB_LAGS = [1, 2, 3, 6, 12]

MODEL_ORDER = [
    "seasonal_naive",
    "prophet",
    "xgboost",
]

MODEL_LABEL = {
    "seasonal_naive": "Seasonal Naive (baseline)",
    "prophet": "Prophet",
    "xgboost": "XGBoost",
}


ALIAS_JENIS = {
    "GEMPABUMI": "GEMPA BUMI",
    "GEMPA BUMI": "GEMPA BUMI",

    "KARHUTLA": "KEBAKARAN HUTAN DAN LAHAN",
    "KEBAKARAN HUTAN LAHAN": "KEBAKARAN HUTAN DAN LAHAN",
    "KEBAKARAN HUTAN DAN LAHAN": "KEBAKARAN HUTAN DAN LAHAN",

    "GELOMBANG PASANG ABRASI": "GELOMBANG PASANG DAN ABRASI",
    "GELOMBANG PASANG DAN ABRASI": "GELOMBANG PASANG DAN ABRASI",

    "ERUPSI GUNUNGAPI": "ERUPSI GUNUNG API",
    "ERUPSI GUNUNG API": "ERUPSI GUNUNG API",
}


# ============================================================
# HELPER COLUMN
# ============================================================

def norm_col(x: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(x).strip().casefold()
    )


def resolve_col(
    df,
    requested,
    aliases,
    required=False,
    label="kolom",
):
    if requested and requested in df.columns:
        return requested

    lookup = {
        norm_col(c): c
        for c in df.columns
    }

    candidates = []

    if requested:
        candidates.append(requested)

    candidates.extend(aliases)

    for name in candidates:
        hit = lookup.get(norm_col(name))

        if hit:
            return hit

    if required:
        raise SystemExit(
            f"Tidak menemukan {label}.\n"
            f"Kolom tersedia: {list(df.columns)}"
        )

    return None


def norm_jenis(x):
    if pd.isna(x):
        return "TIDAK DIKETAHUI"

    s = str(x).upper().strip()

    s = re.sub(
        r"[^A-Z ]",
        " ",
        s
    )

    s = re.sub(
        r"\s+",
        " ",
        s
    ).strip()

    return ALIAS_JENIS.get(
        s,
        s or "TIDAK DIKETAHUI"
    )


def norm_key(x):
    if pd.isna(x):
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(x).upper().strip()
    )


# ============================================================
# LOAD + CLEAN
# ============================================================

def load_clean(
    args,
    outdir: Path,
):

    df = pd.read_excel(
        args.file,
        header=args.header_row
    )

    raw_rows = len(df)

    # hapus audit lama
    for old in [
        "duplicates_removed.csv",
        "duplicate_groups_all.csv",
        "rows_invalid_date.csv",
    ]:

        p = outdir / old

        if p.exists():
            p.unlink()

    # -----------------------
    # AUTO DETECT COLUMN
    # -----------------------

    jenis_col = resolve_col(
        df,
        args.jenis_col,
        [
            "Kejadian",
            "Jenis Bencana",
        ],
        True,
        "jenis bencana",
    )

    date_col = resolve_col(
        df,
        args.date_col,
        [
            "Tanggal Kejadian",
            "Tanggal",
            "tanggal",
        ],
        True,
        "tanggal kejadian",
    )

    kab_id_col = resolve_col(
        df,
        args.kab_id_col,
        [
            "ID Kabupaten",
            "id_kab",
        ],
    )

    kab_col = resolve_col(
        df,
        args.kabupaten_col,
        [
            "Kabupaten",
            "kabkot",
        ],
    )

    lokasi_col = resolve_col(
        df,
        args.lokasi_col,
        [
            "Lokasi",
            "lokasi",
        ],
    )

    event_id_col = resolve_col(
        df,
        args.event_id_col,
        [
            "Kode Identitas Bencana",
            "kib",
            "ID Bencana",
        ],
    )

    # -----------------------
    # PRINT SCHEMA
    # -----------------------

    print(
        f"[1] Baris mentah : {raw_rows:,}"
    )

    print(
        f"    Jumlah kolom: {len(df.columns):,}"
    )

    print(
        "\n    Kolom yang dipakai:"
    )

    used_columns = {
        "jenis": jenis_col,
        "tanggal": date_col,
        "id_kabupaten": kab_id_col,
        "kabupaten": kab_col,
        "lokasi": lokasi_col,
        "event_id": event_id_col,
    }

    for key, value in used_columns.items():
        print(
            f"      {key:18s}: {value}"
        )

    # ========================================================
    # DATE
    # ========================================================

    df["_tgl"] = pd.to_datetime(
        df[date_col],
        errors="coerce",
        dayfirst=True,
    )

    bad_date = df["_tgl"].isna()

    if bad_date.any():

        df.loc[
            bad_date
        ].to_csv(
            outdir / "rows_invalid_date.csv",
            index=False,
            encoding="utf-8-sig",
        )

        print(
            f"\n    Tanggal invalid dibuang: "
            f"{bad_date.sum():,}"
        )

        df = df.loc[
            ~bad_date
        ].copy()

    # ========================================================
    # FILTER PROJECT PERIOD
    # ========================================================

    start = pd.Timestamp(
        args.start_date
    )

    end = pd.Timestamp(
        args.end_date
    )

    df = df.loc[
        df["_tgl"].between(
            start,
            end,
        )
    ].copy()

    # ========================================================
    # NORMALIZE DISASTER TYPE
    # ========================================================

    df["_jenis"] = df[
        jenis_col
    ].map(
        norm_jenis
    )

    print(
        "\n    Daftar jenis setelah normalisasi:"
    )

    print(
        df["_jenis"]
        .value_counts()
        .to_string()
    )

    # ========================================================
    # DEDUP
    # ========================================================
    #
    # PENTING:
    #
    # event ID berbeda -> jangan dianggap duplikat.
    #
    # Jadi sekarang key:
    #
    # tanggal
    # + kabupaten
    # + jenis
    # + lokasi
    # + Kode Identitas Bencana
    #
    # ========================================================

    df["_kab_key"] = ""

    if kab_id_col:

        df["_kab_key"] = (
            df[kab_id_col]
            .map(norm_key)
        )

    if kab_col:

        kab_fallback = (
            df[kab_col]
            .map(norm_key)
        )

        blank = (
            df["_kab_key"]
            .eq("")
        )

        df.loc[
            blank,
            "_kab_key"
        ] = kab_fallback[
            blank
        ]

    # kabupaten kosong dibuat unik
    # supaya tidak salah hapus

    blank_kab = (
        df["_kab_key"]
        .eq("")
    )

    df.loc[
        blank_kab,
        "_kab_key"
    ] = [
        f"ROWKAB:{i}"
        for i in df.index[
            blank_kab
        ]
    ]

    # lokasi

    if lokasi_col:

        df["_lokasi_key"] = (
            df[lokasi_col]
            .map(norm_key)
        )

    else:

        df["_lokasi_key"] = ""

    # event id

    if event_id_col:

        df["_event_key"] = (
            df[event_id_col]
            .map(norm_key)
        )

    else:

        df["_event_key"] = ""

    # event id kosong -> dibuat unik
    # jadi tidak dihapus secara agresif

    blank_event = (
        df["_event_key"]
        .eq("")
    )

    df.loc[
        blank_event,
        "_event_key"
    ] = [
        f"ROWEVENT:{i}"
        for i in df.index[
            blank_event
        ]
    ]

    dedup_subset = [
        "_tgl",
        "_kab_key",
        "_jenis",
        "_lokasi_key",
        "_event_key",
    ]

    # semua anggota duplicate group

    dup_all = df.duplicated(
        subset=dedup_subset,
        keep=False,
    )

    # yang benar-benar dibuang

    dup_remove = df.duplicated(
        subset=dedup_subset,
        keep="first",
    )

    # --------------------------------------------------------
    # AUDIT SEMUA GRUP
    # --------------------------------------------------------

    if dup_all.any():

        audit = (
            df.loc[
                dup_all
            ]
            .copy()
        )

        audit[
            "_dedup_action"
        ] = np.where(
            dup_remove.loc[
                audit.index
            ],
            "REMOVE",
            "KEEP",
        )

        audit = audit.sort_values(
            dedup_subset
        )

        audit.to_csv(
            outdir
            / "duplicate_groups_all.csv",
            index=False,
            encoding="utf-8-sig",
        )

    # --------------------------------------------------------
    # AUDIT HANYA YANG DIBUANG
    # --------------------------------------------------------

    if dup_remove.any():

        df.loc[
            dup_remove
        ].to_csv(
            outdir
            / "duplicates_removed.csv",
            index=False,
            encoding="utf-8-sig",
        )

    before = len(df)

    df = df.loc[
        ~dup_remove
    ].copy()

    removed = (
        before
        - len(df)
    )

    print(
        f"\n[1] Duplikat dibuang: "
        f"{removed:,} "
        f"(Tanggal + Kabupaten + Jenis + Lokasi "
        f"+ Kode Identitas Bencana)"
        f" -> {len(df):,} baris"
    )

    if dup_all.any():

        print(
            "    Audit lengkap: "
            "duplicate_groups_all.csv "
            "(KEEP / REMOVE)"
        )

    # ========================================================
    # CLEANING SUMMARY
    # ========================================================

    summary = {

        "raw_rows":
            int(raw_rows),

        "rows_after_cleaning":
            int(len(df)),

        "duplicates_removed":
            int(removed),

        "dedup_rule":
            (
                "Tanggal + Kabupaten + Jenis + Lokasi "
                "+ Kode Identitas Bencana; "
                "event ID berbeda dipertahankan"
            ),

        "period_start":
            args.start_date,

        "period_end":
            args.end_date,
    }

    with open(
        outdir
        / "cleaning_summary.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return (
        df,
        summary,
    )


# ============================================================
# MONTHLY AGGREGATION
# ============================================================

def monthly_table(
    df,
    args,
):

    work = df.copy()

    work["_bln"] = (
        work["_tgl"]
        .dt
        .to_period("M")
    )

    start = pd.Period(
        args.start_date,
        freq="M",
    )

    cutoff = pd.Period(
        args.cutoff,
        freq="M",
    )

    work = work.loc[
        work["_bln"]
        .between(
            start,
            cutoff,
        )
    ].copy()

    piv = work.pivot_table(

        index="_bln",

        columns="_jenis",

        values="_tgl",

        aggfunc="count",

        fill_value=0,
    )

    full_months = pd.period_range(
        start,
        cutoff,
        freq="M",
    )

    piv = piv.reindex(
        full_months,
        fill_value=0,
    )

    piv = (
        piv
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
        .fillna(0)
    )

    # NASIONAL =
    # semua jenis dijumlahkan

    piv["NASIONAL"] = (
        piv.sum(
            axis=1
        )
    )

    # ========================================================
    # SANITY CHECK
    # ========================================================

    expected = len(work)

    got = int(
        piv["NASIONAL"]
        .sum()
    )

    if expected != got:

        raise RuntimeError(
            f"Sanity check gagal: "
            f"cleaned={expected:,}, "
            f"monthly nasional={got:,}"
        )

    print(
        f"\n[2] Tabel bulanan: "
        f"{piv.index.min()} "
        f"s/d "
        f"{piv.index.max()} "
        f"({len(piv)} bulan, "
        f"{piv.shape[1]} seri termasuk NASIONAL)"
    )

    print(
        f"    Total target nasional sepanjang periode: "
        f"{got:,}"
    )

    print(
        f"    Rata-rata nasional per bulan         : "
        f"{piv['NASIONAL'].mean():.2f}"
    )

    return piv


# ============================================================
# METRICS
# ============================================================

def metrics(
    actual,
    pred,
):

    a = np.asarray(
        actual,
        dtype=float,
    )

    p = np.asarray(
        pred,
        dtype=float,
    )

    mae = float(
        np.mean(
            np.abs(
                a - p
            )
        )
    )

    rmse = float(
        np.sqrt(
            np.mean(
                (a - p) ** 2
            )
        )
    )

    # MAPE hanya actual > 0

    nz = (
        a > 0
    )

    if nz.any():

        mape = float(
            np.mean(
                np.abs(
                    a[nz]
                    - p[nz]
                )
                / a[nz]
            )
            * 100
        )

    else:

        mape = None

    # sMAPE

    denom = (
        np.abs(a)
        + np.abs(p)
    )

    valid = (
        denom > 0
    )

    if valid.any():

        smape = float(
            np.mean(
                200
                * np.abs(
                    a[valid]
                    - p[valid]
                )
                / denom[valid]
            )
        )

    else:

        smape = None

    return {

        "mae":
            mae,

        "rmse":
            rmse,

        "mape":
            mape,

        "smape":
            smape,
    }


def rnd(
    x,
    n=2,
):

    if x is None:
        return None

    x = float(x)

    if not np.isfinite(x):
        return None

    return round(
        x,
        n,
    )


def clip0(x):

    return np.maximum(
        np.asarray(
            x,
            dtype=float,
        ),
        0,
    )


# ============================================================
# SEASONAL NAIVE
# ============================================================

def fc_seasonal_naive(
    series: pd.Series,
    h: int,
):

    y = np.asarray(
        series.values,
        dtype=float,
    )

    if len(y) < 12:

        raise ValueError(
            "Seasonal Naive butuh minimal 12 bulan."
        )

    last_12 = y[-12:]

    pred = np.tile(
        last_12,
        int(
            np.ceil(
                h / 12
            )
        ),
    )[:h]

    return clip0(
        pred
    )


# ============================================================
# PROPHET
# ============================================================

def fc_prophet(
    series: pd.Series,
    h: int,
):

    try:

        from prophet import Prophet

    except ImportError as exc:

        raise RuntimeError(
            "Prophet belum terpasang. "
            "Jalankan: "
            "python -m pip install prophet"
        ) from exc

    train_df = pd.DataFrame({

        "ds":
            series.index
            .to_timestamp(
                how="start"
            ),

        "y":
            series.values
            .astype(float),
    })

    model = Prophet(

        yearly_seasonality=True,

        weekly_seasonality=False,

        daily_seasonality=False,

        seasonality_mode="additive",

        interval_width=0.95,

        changepoint_prior_scale=0.05,
    )

    model.fit(
        train_df
    )

    dates = pd.date_range(

        series.index.max()
        .to_timestamp(
            how="start"
        )
        + pd.offsets.MonthBegin(1),

        periods=h,

        freq="MS",
    )

    result = model.predict(

        pd.DataFrame({

            "ds":
                dates
        })
    )

    mean = clip0(
        result[
            "yhat"
        ].values
    )

    lower = clip0(
        result[
            "yhat_lower"
        ].values
    )

    upper = clip0(
        result[
            "yhat_upper"
        ].values
    )

    return (
        mean,
        lower,
        upper,
    )


# ============================================================
# XGBOOST FEATURES
# ============================================================

def calendar_features(
    period: pd.Period,
):

    month = int(
        period.month
    )

    return {

        "month":
            month,

        "year":
            int(
                period.year
            ),

        "time_idx":
            int(
                period.year
                * 12
                + month
            ),

        "month_sin":
            float(
                np.sin(
                    2
                    * np.pi
                    * month
                    / 12
                )
            ),

        "month_cos":
            float(
                np.cos(
                    2
                    * np.pi
                    * month
                    / 12
                )
            ),
    }


def feature_row(
    history,
    period: pd.Period,
):

    history = list(
        map(
            float,
            history,
        )
    )

    if len(history) < 12:

        raise ValueError(
            "History kurang dari 12 bulan."
        )

    row = {

        f"lag_{lag}":
            history[-lag]

        for lag in XGB_LAGS
    }

    row.update({

        "rolling_mean_3":
            float(
                np.mean(
                    history[-3:]
                )
            ),

        "rolling_mean_6":
            float(
                np.mean(
                    history[-6:]
                )
            ),

        "rolling_mean_12":
            float(
                np.mean(
                    history[-12:]
                )
            ),

        "rolling_std_3":
            float(
                np.std(
                    history[-3:]
                )
            ),

        "rolling_std_6":
            float(
                np.std(
                    history[-6:]
                )
            ),

        "rolling_std_12":
            float(
                np.std(
                    history[-12:]
                )
            ),
    })

    row.update(
        calendar_features(
            period
        )
    )

    return row


def xgb_training_data(
    series: pd.Series,
):

    values = list(
        map(
            float,
            series.values,
        )
    )

    periods = list(
        series.index
    )

    X = []

    y = []

    for i in range(
        12,
        len(values),
    ):

        X.append(

            feature_row(
                values[:i],
                periods[i],
            )
        )

        y.append(
            values[i]
        )

    return (
        pd.DataFrame(
            X
        ),
        np.asarray(
            y,
            dtype=float,
        ),
    )


def new_xgb_model():

    try:

        from xgboost import XGBRegressor

    except ImportError as exc:

        raise RuntimeError(
            "XGBoost belum terpasang. "
            "Jalankan: "
            "python -m pip install xgboost"
        ) from exc

    return XGBRegressor(

        objective="count:poisson",

        n_estimators=500,

        learning_rate=0.03,

        max_depth=4,

        min_child_weight=2,

        subsample=0.85,

        colsample_bytree=0.85,

        reg_alpha=0.05,

        reg_lambda=1.0,

        random_state=42,

        n_jobs=-1,

        verbosity=0,
    )


def fc_xgboost(
    series: pd.Series,
    h: int,
):

    X, y = xgb_training_data(
        series
    )

    if len(X) < 24:

        raise ValueError(
            "Data supervised XGBoost terlalu sedikit."
        )

    model = new_xgb_model()

    model.fit(
        X,
        y,
    )

    history = list(
        map(
            float,
            series.values,
        )
    )

    future_periods = pd.period_range(

        series.index.max()
        + 1,

        periods=h,

        freq="M",
    )

    preds = []

    # recursive forecasting

    for period in future_periods:

        row = pd.DataFrame([

            feature_row(
                history,
                period,
            )

        ])

        pred = max(
            float(
                model.predict(
                    row
                )[0]
            ),
            0.0,
        )

        preds.append(
            pred
        )

        history.append(
            pred
        )

    return np.asarray(
        preds,
        dtype=float,
    )


# ============================================================
# MODEL DISPATCH
# ============================================================

def predict_model(
    model_name,
    series,
    h,
):

    if model_name == "seasonal_naive":

        return (
            fc_seasonal_naive(
                series,
                h,
            ),
            None,
            None,
        )

    if model_name == "prophet":

        return fc_prophet(
            series,
            h,
        )

    if model_name == "xgboost":

        return (
            fc_xgboost(
                series,
                h,
            ),
            None,
            None,
        )

    raise ValueError(
        f"Model tidak dikenal: {model_name}"
    )


# ============================================================
# APPROX UNCERTAINTY
# ============================================================

def approximate_interval(
    mean,
    test_rmse,
):

    width = (
        1.96
        * float(
            test_rmse
        )
    )

    mean = np.asarray(
        mean,
        dtype=float,
    )

    lower = clip0(
        mean - width
    )

    upper = clip0(
        mean + width
    )

    return (
        lower,
        upper,
    )


# ============================================================
# SEASONAL PATTERN
# ============================================================

def complete_year_seasonality(
    series,
    end_year=2025,
):

    # Jangan campur Jan-Okt 2026
    # dengan Nov-Des yang belum punya 2026.
    #
    # Jadi dashboard menggunakan
    # tahun kalender lengkap 2015-2025.

    valid = series.loc[
        series.index.year
        <= end_year
    ]

    return [

        rnd(
            valid.loc[
                valid.index.month
                == month
            ].mean()
        )

        for month in range(
            1,
            13,
        )
    ]


# ============================================================
# RUN ONE SERIES
# ============================================================

def run_series(
    name,
    series,
    args,
):

    train_end = pd.Period(
        args.train_end,
        freq="M",
    )

    cutoff = pd.Period(
        args.cutoff,
        freq="M",
    )

    series = (
        series.loc[
            series.index
            <= cutoff
        ]
        .astype(float)
    )

    train = series.loc[
        series.index
        <= train_end
    ]

    test = series.loc[
        series.index
        > train_end
    ]

    h_test = len(test)

    out = {

        "label":
            name,

        "mean_per_month":
            rnd(
                series.mean()
            ),

        "low_frequency":
            bool(
                series.mean()
                < LOW_FREQ_MEAN
            ),

        "actual": [

            {
                "month":
                    str(period),

                "value":
                    int(
                        round(value)
                    ),
            }

            for period, value
            in series.items()
        ],

        "seasonal_avg":
            complete_year_seasonality(
                series,
                args.seasonality_end_year,
            ),

        "seasonality_period":
            (
                f"2015-"
                f"{args.seasonality_end_year} "
                f"(tahun lengkap)"
            ),

        "models":
            {},

        "best_model":
            None,

        "best_label":
            None,

        # top level tetap disimpan
        # agar frontend lama tetap bisa pakai

        "test_pred":
            [],

        "forecast":
            [],

        "note":
            None,
    }

    # ========================================================
    # LOW DATA FILTER
    # ========================================================

    nonzero_train = int(
        (
            train > 0
        ).sum()
    )

    if nonzero_train < 12:

        out["note"] = (
            "Data terlalu jarang; "
            "seri tidak dimodelkan."
        )

        return out

    candidates = [
        "seasonal_naive"
    ]

    if (
        nonzero_train
        >= MIN_NONZERO_FOR_COMPLEX_MODELS
    ):

        candidates += [
            "prophet",
            "xgboost",
        ]

    else:

        out["note"] = (
            "Prophet/XGBoost dilewati karena "
            f"bulan non-zero train < "
            f"{MIN_NONZERO_FOR_COMPLEX_MODELS}."
        )

    raw_mae = {}

    # ========================================================
    # RUN ALL MODELS
    # ========================================================

    for model_name in candidates:

        try:

            # --------------------------------------------
            # TEST PREDICTION
            # --------------------------------------------

            (
                test_mean,
                _,
                _,
            ) = predict_model(

                model_name,

                train,

                h_test,
            )

            met = metrics(

                test.values,

                test_mean,
            )

            raw_mae[
                model_name
            ] = met[
                "mae"
            ]

            # --------------------------------------------
            # REFIT FULL SERIES
            # --------------------------------------------

            (
                forecast_mean,
                forecast_lower,
                forecast_upper,
            ) = predict_model(

                model_name,

                series,

                args.horizon,
            )

            # Prophet punya prediction interval asli.
            #
            # Seasonal Naive dan XGB:
            # uncertainty approximation dari RMSE test.

            if model_name != "prophet":

                (
                    forecast_lower,
                    forecast_upper,
                ) = approximate_interval(

                    forecast_mean,

                    met["rmse"],
                )

                interval_type = (
                    "approximation"
                )

                interval_label = (
                    "Approx. uncertainty range"
                )

            else:

                interval_type = (
                    "model_interval"
                )

                interval_label = (
                    "Prophet 95% prediction interval"
                )

            future_index = pd.period_range(

                series.index.max()
                + 1,

                periods=args.horizon,

                freq="M",
            )

            # ============================================
            # SIMPAN SEMUA MODEL
            # ============================================

            out[
                "models"
            ][
                model_name
            ] = {

                "label":
                    MODEL_LABEL[
                        model_name
                    ],

                "metrics": {

                    key:
                        rnd(value)

                    for key, value
                    in met.items()
                },

                # flat metrics
                # supaya frontend gampang

                "mae":
                    rnd(
                        met["mae"]
                    ),

                "rmse":
                    rnd(
                        met["rmse"]
                    ),

                "mape":
                    rnd(
                        met["mape"]
                    ),

                "smape":
                    rnd(
                        met["smape"]
                    ),

                "interval_type":
                    interval_type,

                "interval_label":
                    interval_label,

                "test_pred": [

                    {
                        "month":
                            str(period),

                        "actual":
                            int(
                                round(actual)
                            ),

                        "pred":
                            rnd(pred),
                    }

                    for (
                        period,
                        actual,
                        pred,
                    )
                    in zip(
                        test.index,
                        test.values,
                        test_mean,
                    )
                ],

                "forecast": [

                    {
                        "month":
                            str(period),

                        "pred":
                            rnd(mean),

                        "lower":
                            rnd(lower),

                        "upper":
                            rnd(upper),
                    }

                    for (
                        period,
                        mean,
                        lower,
                        upper,
                    )
                    in zip(
                        future_index,
                        forecast_mean,
                        forecast_lower,
                        forecast_upper,
                    )
                ],
            }

        except Exception as exc:

            out[
                "models"
            ][
                model_name
            ] = {

                "label":
                    MODEL_LABEL[
                        model_name
                    ],

                "error":
                    str(exc)[
                        :400
                    ],
            }

    # ========================================================
    # BEST MODEL BY MAE
    # ========================================================

    valid = {

        key:
            value

        for key, value
        in raw_mae.items()

        if np.isfinite(
            value
        )
    }

    if not valid:

        out["note"] = (
            (
                out["note"]
                + " "
            )
            if out["note"]
            else ""
        ) + (
            "Semua model gagal."
        )

        return out

    best = min(
        valid,
        key=valid.get,
    )

    out[
        "best_model"
    ] = best

    out[
        "best_label"
    ] = MODEL_LABEL[
        best
    ]

    # --------------------------------------------
    # compatibility shortcut
    # --------------------------------------------

    out[
        "test_pred"
    ] = out[
        "models"
    ][
        best
    ][
        "test_pred"
    ]

    out[
        "forecast"
    ] = out[
        "models"
    ][
        best
    ][
        "forecast"
    ]

    if out[
        "low_frequency"
    ]:

        out["note"] = (
            (
                out["note"]
                + " "
            )
            if out["note"]
            else ""
        ) + (
            "Seri berfrekuensi rendah; "
            "interpretasikan forecast "
            "dengan hati-hati."
        )

    return out


# ============================================================
# PLOTS
# ============================================================

def make_plots(
    result,
    outdir: Path,
):

    try:

        import matplotlib

        matplotlib.use(
            "Agg"
        )

        import matplotlib.pyplot as plt

    except Exception:

        print(
            "    matplotlib tidak tersedia, "
            "plot dilewati"
        )

        return

    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name, r in result[
        "series"
    ].items():

        if not r[
            "actual"
        ]:

            continue

        fig, ax = plt.subplots(
            figsize=(
                12,
                5,
            )
        )

        # ACTUAL

        actual_x = pd.PeriodIndex(

            [
                x["month"]
                for x
                in r["actual"]
            ],

            freq="M",

        ).to_timestamp()

        actual_y = [

            x["value"]

            for x
            in r["actual"]
        ]

        ax.plot(

            actual_x,

            actual_y,

            label="Aktual",
        )

        # TEST

        if r[
            "test_pred"
        ]:

            test_x = pd.PeriodIndex(

                [
                    x["month"]
                    for x
                    in r["test_pred"]
                ],

                freq="M",

            ).to_timestamp()

            ax.plot(

                test_x,

                [
                    x["pred"]
                    for x
                    in r["test_pred"]
                ],

                "--",

                label="Prediksi test",
            )

        # FORECAST

        if r[
            "forecast"
        ]:

            future_x = pd.PeriodIndex(

                [
                    x["month"]
                    for x
                    in r["forecast"]
                ],

                freq="M",

            ).to_timestamp()

            ax.plot(

                future_x,

                [
                    x["pred"]
                    for x
                    in r["forecast"]
                ],

                ":",

                linewidth=2,

                label="Forecast",
            )

            ax.fill_between(

                future_x,

                [
                    x["lower"]
                    for x
                    in r["forecast"]
                ],

                [
                    x["upper"]
                    for x
                    in r["forecast"]
                ],

                alpha=0.18,

                label="Uncertainty interval",
            )

        train_end = pd.Period(

            result[
                "meta"
            ][
                "train_end"
            ],

            freq="M",

        ).to_timestamp(
            how="end"
        )

        ax.axvline(

            train_end,

            linestyle="--",

            linewidth=1,

            label="Batas train-test",
        )

        ax.set_title(

            f"{name} - "
            f"{r.get('best_label') or 'Tidak dimodelkan'}"
        )

        ax.set_xlabel(
            "Bulan"
        )

        ax.set_ylabel(
            "Jumlah laporan kejadian"
        )

        ax.legend(
            fontsize=8
        )

        ax.grid(
            alpha=0.2
        )

        fig.tight_layout()

        filename = re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            name,
        ).strip(
            "_"
        ).lower()

        fig.savefig(

            outdir
            / f"forecast_{filename}.png",

            dpi=140,
        )

        plt.close(
            fig
        )


# ============================================================
# EXPORT FLAT FILES
# ============================================================

def export_flat_files(
    result,
    outdir: Path,
):

    metrics_rows = []

    test_rows = []

    forecast_rows = []

    best_forecast_rows = []

    for (
        series_name,
        r,
    ) in result[
        "series"
    ].items():

        for (
            model_name,
            model,
        ) in r[
            "models"
        ].items():

            if (
                "error"
                in model
            ):

                metrics_rows.append({

                    "seri":
                        series_name,

                    "model":
                        model_name,

                    "label":
                        model.get(
                            "label"
                        ),

                    "error":
                        model.get(
                            "error"
                        ),
                })

                continue

            metrics_rows.append({

                "seri":
                    series_name,

                "model":
                    model_name,

                "label":
                    model[
                        "label"
                    ],

                "is_best":
                    (
                        model_name
                        == r[
                            "best_model"
                        ]
                    ),

                "mae":
                    model.get(
                        "mae"
                    ),

                "rmse":
                    model.get(
                        "rmse"
                    ),

                "mape":
                    model.get(
                        "mape"
                    ),

                "smape":
                    model.get(
                        "smape"
                    ),
            })

            # TEST ALL MODELS

            for x in model.get(
                "test_pred",
                [],
            ):

                test_rows.append({

                    "seri":
                        series_name,

                    "model":
                        model_name,

                    **x,
                })

            # FORECAST ALL MODELS

            for x in model.get(
                "forecast",
                [],
            ):

                forecast_rows.append({

                    "seri":
                        series_name,

                    "model":
                        model_name,

                    **x,
                })

        # BEST ONLY

        for x in r.get(
            "forecast",
            [],
        ):

            best_forecast_rows.append({

                "seri":
                    series_name,

                "best_model":
                    r.get(
                        "best_model"
                    ),

                "best_label":
                    r.get(
                        "best_label"
                    ),

                **x,
            })

    pd.DataFrame(
        metrics_rows
    ).to_csv(

        outdir
        / "metrics_all_models.csv",

        index=False,

        encoding="utf-8-sig",
    )

    pd.DataFrame(
        test_rows
    ).to_csv(

        outdir
        / "test_predictions_all_models.csv",

        index=False,

        encoding="utf-8-sig",
    )

    pd.DataFrame(
        forecast_rows
    ).to_csv(

        outdir
        / "forecast_all_models.csv",

        index=False,

        encoding="utf-8-sig",
    )

    pd.DataFrame(
        best_forecast_rows
    ).to_csv(

        outdir
        / "forecast_12_bulan.csv",

        index=False,

        encoding="utf-8-sig",
    )

    # ========================================================
    # SEASONALITY FLAT
    # ========================================================

    month_labels = [

        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "Mei",
        "Jun",
        "Jul",
        "Agu",
        "Sep",
        "Okt",
        "Nov",
        "Des",
    ]

    season_rows = []

    for (
        series_name,
        r,
    ) in result[
        "series"
    ].items():

        for (
            i,
            value,
        ) in enumerate(

            r[
                "seasonal_avg"
            ],

            start=1,
        ):

            season_rows.append({

                "seri":
                    series_name,

                "month_num":
                    i,

                "month_label":
                    month_labels[
                        i - 1
                    ],

                "avg":
                    value,

                "period":
                    r[
                        "seasonality_period"
                    ],
            })

    pd.DataFrame(
        season_rows
    ).to_csv(

        outdir
        / "seasonality_monthly.csv",

        index=False,

        encoding="utf-8-sig",
    )


# ============================================================
# MAIN
# ============================================================

def main():

    ap = argparse.ArgumentParser()

    # ========================================================
    # INPUT
    # ========================================================

    ap.add_argument(
        "--file",
        default="Data Bencana (2).xlsx",
    )

    ap.add_argument(
        "--outdir",
        default=".",
    )

    # header Excel ada di row kedua
    # jadi pandas header=1

    ap.add_argument(
        "--header-row",
        type=int,
        default=1,
    )

    # ========================================================
    # COLUMNS
    # ========================================================

    ap.add_argument(
        "--jenis-col",
        default="Kejadian",
    )

    ap.add_argument(
        "--date-col",
        default="Tanggal Kejadian",
    )

    ap.add_argument(
        "--kab-id-col",
        default="ID Kabupaten",
    )

    ap.add_argument(
        "--kabupaten-col",
        default="Kabupaten",
    )

    ap.add_argument(
        "--lokasi-col",
        default="Lokasi",
    )

    ap.add_argument(
        "--event-id-col",
        default="Kode Identitas Bencana",
    )

    # ========================================================
    # PERIOD
    # ========================================================

    ap.add_argument(
        "--start-date",
        default="2015-01-01",
    )

    ap.add_argument(
        "--end-date",
        default="2026-10-31",
    )

    ap.add_argument(
        "--train-end",
        default="2025-10",
    )

    ap.add_argument(
        "--cutoff",
        default="2026-10",
    )

    ap.add_argument(
        "--horizon",
        type=int,
        default=12,
    )

    # seasonality dashboard
    # hanya tahun lengkap

    ap.add_argument(
        "--seasonality-end-year",
        type=int,
        default=2025,
    )

    args = ap.parse_args()

    # ========================================================
    # OUTPUT DIR
    # ========================================================

    outdir = Path(
        args.outdir
    )

    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # LOAD
    # ========================================================

    (
        df,
        cleaning_summary,
    ) = load_clean(

        args,

        outdir,
    )

    # ========================================================
    # MONTHLY
    # ========================================================

    piv = monthly_table(
        df,
        args,
    )

    piv.index.name = (
        "bulan"
    )

    piv.to_csv(

        outdir
        / "monthly_counts.csv",

        encoding="utf-8-sig",
    )

    # ========================================================
    # SERIES ORDER
    # ========================================================

    disaster_cols = sorted(

        [
            col
            for col
            in piv.columns

            if col
            != "NASIONAL"
        ],

        key=lambda col:
            -piv[col].sum(),
    )

    series_names = [

        "NASIONAL",

        *disaster_cols,
    ]

    # ========================================================
    # JSON META
    # ========================================================

    train_end_period = pd.Period(
        args.train_end,
        freq="M",
    )

    cutoff_period = pd.Period(
        args.cutoff,
        freq="M",
    )

    result = {

        "meta": {

            "sumber":
                "BNPB - Geoportal Data Bencana Indonesia",

            "periode_data":
                (
                    f"{args.start_date} "
                    f"s/d "
                    f"{args.end_date}"
                ),

            "definisi_target":
                (
                    "jumlah laporan kejadian per bulan "
                    "setelah deduplikasi konservatif"
                ),

            "dedup_rule":
                cleaning_summary[
                    "dedup_rule"
                ],

            "train_start":
                str(
                    piv.index.min()
                ),

            "train_end":
                args.train_end,

            "test_start":
                str(
                    train_end_period
                    + 1
                ),

            "test_end":
                args.cutoff,

            "forecast_start":
                str(
                    cutoff_period
                    + 1
                ),

            "forecast_end":
                str(
                    cutoff_period
                    + args.horizon
                ),

            "horizon_bulan":
                args.horizon,

            "selection_metric":
                "MAE",

            "models": [

                MODEL_LABEL[
                    model
                ]

                for model
                in MODEL_ORDER
            ],

            "seasonality_period":
                (
                    f"2015-"
                    f"{args.seasonality_end_year} "
                    f"(tahun lengkap)"
                ),

            "mape_note":
                (
                    "MAPE dapat tidak stabil "
                    "pada seri dengan nilai aktual kecil/nol. "
                    "MAE digunakan sebagai metrik seleksi utama."
                ),

            "interval_note":
                (
                    "Prophet memakai prediction interval model. "
                    "Seasonal Naive dan XGBoost memakai "
                    "approximate uncertainty range "
                    "berbasis RMSE pada data test."
                ),
        },

        "series":
            {},
    }

    # ========================================================
    # MODELING
    # ========================================================

    print(
        "\n[3] Memodelkan semua series ..."
    )

    summary_rows = []

    for name in series_names:

        r = run_series(

            name,

            piv[name],

            args,
        )

        result[
            "series"
        ][
            name
        ] = r

        best = r[
            "best_model"
        ]

        if best:

            best_model_data = (
                r[
                    "models"
                ][
                    best
                ]
            )

        else:

            best_model_data = {}

        summary_rows.append({

            "seri":
                name,

            "rata2_per_bulan":
                r[
                    "mean_per_month"
                ],

            "model_terbaik":
                r[
                    "best_label"
                ],

            "MAE_best":
                best_model_data.get(
                    "mae"
                ),

            "RMSE_best":
                best_model_data.get(
                    "rmse"
                ),

            "MAPE_best":
                best_model_data.get(
                    "mape"
                ),

            "sMAPE_best":
                best_model_data.get(
                    "smape"
                ),
        })

        print(

            f"    {name:36s} "

            f"terbaik="
            f"{str(r['best_label']):28s} "

            f"MAE="
            f"{best_model_data.get('mae')}"
        )

    # ========================================================
    # JSON
    # ========================================================

    with open(

        outdir
        / "forecast_output.json",

        "w",

        encoding="utf-8",

    ) as f:

        json.dump(

            result,

            f,

            ensure_ascii=False,

            indent=2,
        )

    # ========================================================
    # METRIC SUMMARY
    # ========================================================

    pd.DataFrame(
        summary_rows
    ).to_csv(

        outdir
        / "metrics_summary.csv",

        index=False,

        encoding="utf-8-sig",
    )

    # ========================================================
    # DASHBOARD FILES
    # ========================================================

    export_flat_files(

        result,

        outdir,
    )

    # ========================================================
    # PLOTS
    # ========================================================

    print(
        "\n[4] Membuat plot ..."
    )

    make_plots(

        result,

        outdir
        / "plots",
    )

    # ========================================================
    # FINISH
    # ========================================================

    print(
        "\n=== SELESAI ==="
    )

    print(
        f"Output di: "
        f"{outdir.resolve()}"
    )

    print(
        """
  cleaning_summary.json
  duplicate_groups_all.csv
  duplicates_removed.csv
  monthly_counts.csv
  metrics_summary.csv
  metrics_all_models.csv
  test_predictions_all_models.csv
  forecast_all_models.csv
  forecast_12_bulan.csv
  seasonality_monthly.csv
  forecast_output.json
  plots/
"""
    )

    print(
        "Periode evaluasi:"
    )

    print(
        f"  Train    : "
        f"2015-01 "
        f"s/d "
        f"{args.train_end}"
    )

    print(
        f"  Test     : "
        f"{train_end_period + 1} "
        f"s/d "
        f"{args.cutoff}"
    )

    print(
        f"  Forecast : "
        f"{cutoff_period + 1} "
        f"s/d "
        f"{cutoff_period + args.horizon}"
    )


if __name__ == "__main__":
    main()