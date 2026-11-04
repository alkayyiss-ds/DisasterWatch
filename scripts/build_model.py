"""
Script ini dijalankan otomatis oleh Vercel saat build.
Melatih model Random Forest jika artefak belum ada.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "backend" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

if (MODEL_DIR / "rf_severity.joblib").exists():
    print("[build] Model sudah ada, skip training.")
    sys.exit(0)

print("[build] Model belum ada, mulai training...")
sys.path.insert(0, str(ROOT / "backend"))
import train_model
train_model.main()
print("[build] Training selesai.")
