"""
SolarGuard — Kaggle Dataset Splitting & Preprocessing Script

Utility to automatically organize and split the downloaded Kaggle Solar Panel Images dataset
(https://www.kaggle.com/datasets/pythonafroz/solar-panel-images) into an 80/20 train/val structure.

Usage:
  python ml_engine/split_dataset.py --source /path/to/downloaded/dataset
  python ml_engine/split_dataset.py --source /path/to/downloaded/dataset --max-per-class 150
  python ml_engine/split_dataset.py --source /path/to/downloaded/dataset --all-classes
"""

import os
import sys
import shutil
import random
import argparse
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / 'data'

CLASS_MAPPING_4 = {
    'clean': 'Normal',
    'normal': 'Normal',
    'dusty': 'Dusty',
    'bird-drop': 'Bird-Dropping',
    'bird_drop': 'Bird-Dropping',
    'bird-dropping': 'Bird-Dropping',
    'physical-damage': 'Cracked',
    'physical_damage': 'Cracked',
    'cracked': 'Cracked',
}

CLASS_MAPPING_6 = {
    **CLASS_MAPPING_4,
    'electrical-damage': 'Electrical-Damage',
    'electrical_damage': 'Electrical-Damage',
    'snow-covered': 'Snow-Covered',
    'snow_covered': 'Snow-Covered',
}


def split_dataset(source_dir, output_dir=None, split_ratio=0.8, max_per_class=150, all_classes=False):
    source_path = Path(source_dir).resolve()
    if not source_path.exists():
        print(f"[ERROR] Source directory not found: {source_path}")
        sys.exit(1)

    out_path = Path(output_dir).resolve() if output_dir else DEFAULT_DATA_DIR
    train_path = out_path / 'train'
    val_path = out_path / 'val'

    mapping = CLASS_MAPPING_6 if all_classes else CLASS_MAPPING_4

    print("=" * 70)
    print("[SolarGuard] Kaggle Dataset Splitter & Organizer")
    print("=" * 70)
    print(f"[*] Source directory:      {source_path}")
    print(f"[*] Output directory:      {out_path}")
    print(f"[*] Train/Val Split Ratio: {int(split_ratio * 100)}% / {int((1 - split_ratio) * 100)}%")
    print(f"[*] Max images per class:  {max_per_class if max_per_class else 'Unlimited'}")
    print(f"[*] Mode:                  {'6-Class Full' if all_classes else '4-Class Optimized (Recommended)'}")
    print("-" * 70)

    # Find subdirectories in source
    subdirs = [p for p in source_path.iterdir() if p.is_dir()]
    if not subdirs:
        # Check if images are flat or in nested directories
        print("[!] No subdirectories found directly. Searching 1 level deeper...")
        subdirs = [p for p in source_path.glob('*/*') if p.is_dir()]

    matched_classes = {}
    for subdir in subdirs:
        folder_name_clean = subdir.name.strip().lower()
        if folder_name_clean in mapping:
            target_name = mapping[folder_name_clean]
            matched_classes[target_name] = subdir

    if not matched_classes:
        print("[ERROR] No recognized class folders found in source directory!")
        print(f"[*] Looked for folders matching: {list(mapping.keys())}")
        print(f"[*] Found in source: {[d.name for d in subdirs]}")
        sys.exit(1)

    print(f"[*] Recognized classes to process: {list(matched_classes.keys())}\n")

    # Reset output folders
    for cls in matched_classes.keys():
        (train_path / cls).mkdir(parents=True, exist_ok=True)
        (val_path / cls).mkdir(parents=True, exist_ok=True)

    summary_stats = []

    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

    for target_class, src_folder in matched_classes.items():
        all_images = [
            f for f in src_folder.iterdir()
            if f.is_file() and f.suffix.lower() in valid_extensions
        ]

        if not all_images:
            print(f"[!] Warning: No images found in {src_folder}")
            continue

        random.seed(42)
        random.shuffle(all_images)

        if max_per_class and len(all_images) > max_per_class:
            selected_images = all_images[:max_per_class]
        else:
            selected_images = all_images

        n_total = len(selected_images)
        n_train = int(n_total * split_ratio)
        n_val = n_total - n_train

        train_images = selected_images[:n_train]
        val_images = selected_images[n_train:]

        # Copy files
        for img in train_images:
            shutil.copy2(img, train_path / target_class / img.name)

        for img in val_images:
            shutil.copy2(img, val_path / target_class / img.name)

        summary_stats.append({
            'class': target_class,
            'source_total': len(all_images),
            'selected': n_total,
            'train': n_train,
            'val': n_val
        })

    print("-" * 70)
    print(f"{'Class':<20} | {'Found':<8} | {'Used':<8} | {'Train (80%)':<12} | {'Val (20%)':<10}")
    print("-" * 70)
    for stat in summary_stats:
        print(f"{stat['class']:<20} | {stat['source_total']:<8} | {stat['selected']:<8} | {stat['train']:<12} | {stat['val']:<10}")
    print("-" * 70)
    print(f"[OK] Dataset successfully prepared at: {out_path}")
    print(f"[*] Train folder: {train_path}")
    print(f"[*] Val folder:   {val_path}")
    print("=" * 70)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="SolarGuard Dataset Splitter")
    parser.add_argument('--source', type=str, required=True, help="Path to unzipped Kaggle dataset folder")
    parser.add_argument('--output', type=str, default=None, help="Destination directory (defaults to ./data)")
    parser.add_argument('--split', type=float, default=0.8, help="Train split ratio (default: 0.8)")
    parser.add_argument('--max-per-class', type=int, default=150, help="Max images per class (default: 150 for low RAM)")
    parser.add_argument('--all-classes', action='store_true', help="Include all 6 Kaggle classes instead of 4")

    args = parser.parse_args()
    split_dataset(
        source_dir=args.source,
        output_dir=args.output,
        split_ratio=args.split,
        max_per_class=args.max_per_class,
        all_classes=args.all_classes
    )
