"""
Dataset Validation — Comprehensive Pre-Training Checks
=======================================================
Run this BEFORE every training run to catch data issues early.
"""

import os
import sys
import hashlib
from collections import Counter
from PIL import Image

from ml_pipeline.ml_config import (
    TRAIN_DIR, VALID_DIR, TEST_DIR,
    FOLDER_IDS, FOLDER_TO_LETTER, FOLDER_TO_CLASS,
    NUM_CLASSES,
)


def validate_all():
    """Run all validation checks."""
    print("=" * 60)
    print("COMPREHENSIVE DATASET VALIDATION")
    print("=" * 60)

    errors = []
    warnings = []

    # 1. Directory existence
    print("\n[1] Checking directory structure...")
    for name, path in [("Train", TRAIN_DIR), ("Valid", VALID_DIR), ("Test", TEST_DIR)]:
        if not os.path.isdir(path):
            errors.append(f"MISSING directory: {path}")
            print(f"  [FAIL] {name}: {path}")
        else:
            print(f"  [OK]   {name}: {path}")

    # 2. Folder coverage
    print("\n[2] Checking folder coverage (14 target folders)...")
    for split_name, split_dir in [("train", TRAIN_DIR), ("valid", VALID_DIR), ("test", TEST_DIR)]:
        if not os.path.isdir(split_dir):
            continue
        for folder_id in FOLDER_IDS:
            folder_path = os.path.join(split_dir, str(folder_id))
            if not os.path.isdir(folder_path):
                errors.append(f"MISSING folder: {split_name}/{folder_id} ({FOLDER_TO_LETTER[folder_id]})")
            else:
                count = len([f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))])
                if count == 0:
                    errors.append(f"EMPTY folder: {split_name}/{folder_id}")
                else:
                    print(f"  [OK] {split_name}/{folder_id} ({FOLDER_TO_LETTER[folder_id]}): {count} images")

    # 3. Image integrity
    print("\n[3] Checking image integrity (sample check)...")
    for split_name, split_dir in [("train", TRAIN_DIR), ("valid", VALID_DIR), ("test", TEST_DIR)]:
        if not os.path.isdir(split_dir):
            continue
        corrupt_count = 0
        total_checked = 0
        for folder_id in FOLDER_IDS:
            folder_path = os.path.join(split_dir, str(folder_id))
            if not os.path.isdir(folder_path):
                continue
            files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
            # Check first 5 and last 5 images per folder
            check_files = files[:5] + files[-5:] if len(files) > 10 else files
            for fname in check_files:
                total_checked += 1
                fpath = os.path.join(folder_path, fname)
                try:
                    img = Image.open(fpath)
                    img.verify()
                except Exception as e:
                    corrupt_count += 1
                    errors.append(f"CORRUPT: {fpath}: {e}")

        if corrupt_count > 0:
            print(f"  [FAIL] {split_name}: {corrupt_count}/{total_checked} corrupted")
        else:
            print(f"  [OK]   {split_name}: {total_checked} images checked, all valid")

    # 4. Class balance
    print("\n[4] Checking class balance...")
    for split_name, split_dir in [("train", TRAIN_DIR), ("valid", VALID_DIR), ("test", TEST_DIR)]:
        if not os.path.isdir(split_dir):
            continue
        counts = {}
        for folder_id in FOLDER_IDS:
            folder_path = os.path.join(split_dir, str(folder_id))
            if os.path.isdir(folder_path):
                count = len([f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))])
                counts[folder_id] = count

        if counts:
            min_c = min(counts.values())
            max_c = max(counts.values())
            ratio = min_c / max_c if max_c > 0 else 0
            print(f"  {split_name}: min={min_c}, max={max_c}, ratio={ratio:.2f}")
            if ratio < 0.7:
                warnings.append(f"{split_name}: Class imbalance detected (ratio={ratio:.2f})")

    # 5. No data leakage between splits
    print("\n[5] Checking for data leakage between splits...")
    split_hashes = {}
    for split_name, split_dir in [("train", TRAIN_DIR), ("valid", VALID_DIR), ("test", TEST_DIR)]:
        if not os.path.isdir(split_dir):
            continue
        hashes = set()
        for folder_id in FOLDER_IDS:
            folder_path = os.path.join(split_dir, str(folder_id))
            if not os.path.isdir(folder_path):
                continue
            for fname in os.listdir(folder_path):
                fpath = os.path.join(folder_path, fname)
                if os.path.isfile(fpath):
                    with open(fpath, 'rb') as f:
                        h = hashlib.md5(f.read()).hexdigest()
                    hashes.add(h)
        split_hashes[split_name] = hashes

    # Check for overlaps
    for s1 in split_hashes:
        for s2 in split_hashes:
            if s1 >= s2:
                continue
            overlap = split_hashes[s1] & split_hashes[s2]
            if overlap:
                errors.append(f"DATA LEAKAGE: {len(overlap)} identical files between {s1} and {s2}")
                print(f"  [FAIL] {s1} ↔ {s2}: {len(overlap)} identical files!")
            else:
                print(f"  [OK] {s1} ↔ {s2}: No overlap")

    # 6. Label mapping verification
    print("\n[6] Verifying label mapping consistency...")
    for folder_id in FOLDER_IDS:
        class_idx = FOLDER_TO_CLASS[folder_id]
        letter = FOLDER_TO_LETTER[folder_id]
        print(f"  Folder {folder_id:>3} → Class {class_idx:>2} → {letter}")

    expected_classes = set(range(NUM_CLASSES))
    actual_classes = set(FOLDER_TO_CLASS.values())
    if expected_classes != actual_classes:
        errors.append(f"Class index gap: expected {expected_classes}, got {actual_classes}")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"VALIDATION FAILED — {len(errors)} errors, {len(warnings)} warnings")
        for e in errors:
            print(f"  [ERROR] {e}")
        for w in warnings:
            print(f"  [WARN]  {w}")
    else:
        print(f"VALIDATION PASSED — 0 errors, {len(warnings)} warnings")
        for w in warnings:
            print(f"  [WARN]  {w}")
    print("=" * 60)

    return len(errors) == 0


if __name__ == "__main__":
    validate_all()
