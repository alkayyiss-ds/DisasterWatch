#!/usr/bin/env python3
"""
DisasterWatch - Downloader dataset bencana BNPB (gis.bnpb.go.id)

Sumber : API GeoJSON Geoportal Kebencanaan Indonesia (BNPB)
Endpoint: https://gis.bnpb.go.id/databencana/src/index.php
          ?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD

Output :
  data/raw/bnpb_bencana_<mulai>_<akhir>.geojson   -> respons mentah (FeatureCollection)
  data/processed/bnpb_bencana_<mulai>_<akhir>.csv -> tabel siap analisis
  data/processed/metadata.json                    -> provenance & ringkasan

Pemakaian:
  python scripts/download_bnpb.py
  python scripts/download_bnpb.py --start 2026-01-01 --end 2026-10-21
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timezone
from pathlib import Path

BASE_URL = "https://gis.bnpb.go.id/databencana/src/index.php"

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


def fetch_geojson(start: str, end: str, timeout: int = 180) -> dict:
    query = urllib.parse.urlencode({"startDate": start, "endDate": end})
    url = f"{BASE_URL}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DisasterWatch/0.1 (+research; dataset downloader)",
            "Accept": "application/json",
        },
    )
    for attempt in range(1, 4):
        try:
            print(f"[+] GET {url} (attempt {attempt}/3)")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            print(f"[+] {len(raw):,} bytes diterima")
            return json.loads(raw.decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if attempt == 3:
                raise
            print(f"[!] Retry karena {exc}; menunggu {attempt * 5} detik")
            time.sleep(attempt * 5)


def next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def fetch_geojson_range(start: str, end: str) -> dict:
    """Fetch a long range month-by-month because the endpoint rejects large ranges."""
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    features = []
    cursor = first.replace(day=1)
    total_chunks = 0
    chunk_dir = RAW_DIR / ".chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    while cursor <= last:
        chunk_end = next_month(cursor)
        chunk_end = date.fromordinal(chunk_end.toordinal() - 1)
        chunk_start = max(cursor, first)
        chunk_stop = min(chunk_end, last)
        cache_path = chunk_dir / f"{chunk_start.isoformat()}_{chunk_stop.isoformat()}.geojson"
        if cache_path.exists():
            fc = json.loads(cache_path.read_text(encoding="utf-8"))
            print(f"[+] Cache: {cache_path.name} -> {len(fc.get('features') or []):,} feature")
        else:
            fc = fetch_geojson(chunk_start.isoformat(), chunk_stop.isoformat())
            cache_path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
        features.extend(fc.get("features") or [])
        total_chunks += 1
        print(f"[+] Chunk {total_chunks}: {chunk_start} s.d. {chunk_stop} -> {len(fc.get('features') or []):,} feature")
        cursor = next_month(cursor)
    print(f"[+] Total gabungan: {len(features):,} feature dari {total_chunks} chunk bulanan")
    return {
        "type": "FeatureCollection",
        "startDate": start,
        "endDate": end,
        "features": features,
    }


def flatten_features(fc: dict) -> tuple[list[str], list[dict]]:
    features = fc.get("features") or []
    if not features:
        return [], []

    # Kumpulkan seluruh nama atribut (jaga-jaga bila antar-feature berbeda)
    columns: list[str] = []
    seen: set[str] = set()
    for feat in features:
        for key in (feat.get("properties") or {}):
            if key not in seen:
                seen.add(key)
                columns.append(key)
    columns += ["geometry_lon", "geometry_lat"]

    rows: list[dict] = []
    for feat in features:
        props = dict(feat.get("properties") or {})
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or [None, None]
        props["geometry_lon"] = coords[0] if len(coords) > 0 else None
        props["geometry_lat"] = coords[1] if len(coords) > 1 else None
        rows.append(props)
    return columns, rows


def row_date_key(row: dict) -> tuple:
    return (
        row.get("tahun") or 0,
        row.get("bulan") or 0,
        row.get("tanggal") or 0,
        row.get("provinsi") or "",
        row.get("kabkot") or "",
    )


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    # utf-8-sig agar aman dibuka langsung di Excel
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in columns})
    print(f"[+] CSV  -> {path} ({len(rows):,} baris, {len(columns)} kolom)")


def summarize(rows: list[dict]) -> dict:
    def total(key: str) -> int:
        return sum(int(r.get(key) or 0) for r in rows)

    dates = sorted(
        f"{r.get('tahun')}-{int(r.get('bulan') or 0):02d}-{int(r.get('tanggal') or 0):02d}"
        for r in rows
    )
    by_type: dict[str, int] = {}
    by_prov: dict[str, int] = {}
    for r in rows:
        by_type[r.get("kejadian") or "-"] = by_type.get(r.get("kejadian") or "-", 0) + 1
        by_prov[r.get("provinsi") or "-"] = by_prov.get(r.get("provinsi") or "-", 0) + 1

    return {
        "jumlah_kejadian": len(rows),
        "tanggal_min": dates[0] if dates else None,
        "tanggal_max": dates[-1] if dates else None,
        "jumlah_provinsi": len(by_prov),
        "jumlah_kabupaten_kota": len({r.get("id_kab") for r in rows}),
        "total_meninggal": total("meninggal"),
        "total_hilang": total("hilang"),
        "total_terluka": total("terluka"),
        "total_menderita": total("menderita"),
        "total_mengungsi": total("mengungsi"),
        "total_rumah_rusak": total("rumah_rusak"),
        "total_rumah_terendam": total("terendam"),
        "total_lahan_ha": round(sum(float(r.get("lahan") or 0) for r in rows), 2),
        "per_jenis_bencana": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "per_provinsi": dict(sorted(by_prov.items(), key=lambda kv: -kv[1])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Download data bencana BNPB")
    parser.add_argument("--start", default="2015-01-01", help="tanggal awal (YYYY-MM-DD)")
    parser.add_argument("--end", default=date.today().isoformat(), help="tanggal akhir (YYYY-MM-DD), default hari ini")
    args = parser.parse_args()

    start, end = args.start, args.end
    date.fromisoformat(start), date.fromisoformat(end)  # validasi format

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    stem = f"bnpb_bencana_{start}_{end}"
    raw_path = RAW_DIR / f"{stem}.geojson"
    csv_path = PROCESSED_DIR / f"{stem}.csv"
    meta_path = PROCESSED_DIR / "metadata.json"

    fc = fetch_geojson_range(start, end)

    raw_path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print(f"[+] JSON -> {raw_path}")

    columns, rows = flatten_features(fc)
    if not rows:
        print("[!] Tidak ada feature yang dikembalikan. Cek rentang tanggal.", file=sys.stderr)
        return 2

    rows.sort(key=row_date_key)
    write_csv(csv_path, columns, rows)

    summary = summarize(rows)
    metadata = {
        "project": "DisasterWatch",
        "source": "Geoportal Data Bencana Indonesia - BNPB",
        "source_page": "https://gis.bnpb.go.id",
        "endpoint": BASE_URL,
        "requested_range": {"start": start, "end": end},
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_file": str(raw_path.relative_to(ROOT)).replace("\\", "/"),
        "csv_file": str(csv_path.relative_to(ROOT)).replace("\\", "/"),
        "summary": summary,
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[+] META -> {meta_path}")

    print("\n=== RINGKASAN ===")
    print(f"Kejadian      : {summary['jumlah_kejadian']:,}")
    print(f"Rentang       : {summary['tanggal_min']} s.d. {summary['tanggal_max']}")
    print(f"Provinsi      : {summary['jumlah_provinsi']}")
    print(f"Kab/Kota      : {summary['jumlah_kabupaten_kota']}")
    print(f"Meninggal     : {summary['total_meninggal']:,}")
    print(f"Mengungsi     : {summary['total_mengungsi']:,}")
    print(f"Rumah rusak   : {summary['total_rumah_rusak']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
