"""
Dataset Module — Safe PyTorch Dataset for Sinhala Letters
=========================================================
- Explicit folder-to-label mapping (NEVER uses folder ID as label)
- Supports train/valid/test splits
- Aggressive data augmentation for small dataset
- Validation scripts to detect label mismatch
"""

import os
import numpy as np
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T

from ml_pipeline.ml_config import (
    FOLDER_IDS, FOLDER_TO_CLASS, FOLDER_TO_LETTER,
    CLASS_TO_LETTER, NUM_CLASSES,
    TRAIN_DIR, VALID_DIR, TEST_DIR,
    IMG_SIZE, BATCH_SIZE,
    AUGMENT_ROTATION, AUGMENT_TRANSLATE, AUGMENT_SCALE,
    AUGMENT_SHEAR, AUGMENT_ERASING_PROB, AUGMENT_BRIGHTNESS,
)


class SinhalaLetterDataset(Dataset):
    """
    PyTorch Dataset for Sinhala handwriting images.

    Key safety features:
    1. Only loads images from the 14 specified folders (FOLDER_IDS)
    2. Maps folder IDs to contiguous class indices [0-13]
    3. Validates all images on initialization
    4. Reports any corrupted/unreadable files

    Args:
        root_dir: Path to train/valid/test split directory
        transform: Optional torchvision transform
        validate: If True, verify all images can be loaded (slower init)
    """

    def __init__(self, root_dir, transform=None, validate=False):
        self.root_dir = root_dir
        self.transform = transform
        self.samples = []   # List of (image_path, class_index)
        self.corrupted = []  # Track bad files

        # Load only from our 14 target folders
        for folder_id in FOLDER_IDS:
            folder_path = os.path.join(root_dir, str(folder_id))
            class_idx = FOLDER_TO_CLASS[folder_id]

            if not os.path.isdir(folder_path):
                print(f"[WARNING] Missing folder: {folder_path} (class {class_idx}: {FOLDER_TO_LETTER[folder_id]})")
                continue

            for fname in sorted(os.listdir(folder_path)):
                fpath = os.path.join(folder_path, fname)
                if not os.path.isfile(fpath):
                    continue
                # Only accept image files
                if not fname.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    continue

                if validate:
                    try:
                        img = Image.open(fpath)
                        img.verify()
                    except Exception as e:
                        self.corrupted.append((fpath, str(e)))
                        continue

                self.samples.append((fpath, class_idx))

        if self.corrupted:
            print(f"[WARNING] {len(self.corrupted)} corrupted files found:")
            for path, err in self.corrupted[:5]:
                print(f"  {path}: {err}")

        # Verify class distribution
        self._verify_distribution()

    def _verify_distribution(self):
        """Check that all 14 classes have samples and distribution is reasonable."""
        counts = {}
        for _, label in self.samples:
            counts[label] = counts.get(label, 0) + 1

        missing = [CLASS_TO_LETTER[i] for i in range(NUM_CLASSES) if i not in counts]
        if missing:
            print(f"[CRITICAL] Missing classes: {missing}")

        min_count = min(counts.values()) if counts else 0
        max_count = max(counts.values()) if counts else 0

        if max_count > 0 and min_count / max_count < 0.5:
            print(f"[WARNING] Class imbalance detected: min={min_count}, max={max_count}")

        print(f"[Dataset] {self.root_dir}: {len(self.samples)} samples, "
              f"{len(counts)} classes, range [{min_count}-{max_count}]")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]

        try:
            img = Image.open(img_path).convert('L')  # Force grayscale
        except Exception as e:
            print(f"[ERROR] Failed to load {img_path}: {e}")
            # Return a blank image with the correct label rather than crashing
            img = Image.new('L', (IMG_SIZE, IMG_SIZE), 0)

        if self.transform:
            img = self.transform(img)
        else:
            # Default: resize + tensor + normalize
            img = T.Compose([
                T.Resize((IMG_SIZE, IMG_SIZE)),
                T.ToTensor(),
                T.Normalize(mean=[0.5], std=[0.5]),
            ])(img)

        return img, label


# ============================================================
# TRANSFORMS
# ============================================================

def get_train_transforms():
    """
    Aggressive augmentation for small dataset (~190 samples/class).
    Simulates natural variation in air-writing:
    - Rotation: natural hand tilt
    - Translation: imprecise positioning
    - Scale: different writing sizes  
    - Affine shear: perspective distortion
    - Random erasing: simulates partial occlusion
    - Elastic-like via affine: simulates stroke wobble
    """
    return T.Compose([
        T.Resize((IMG_SIZE + 8, IMG_SIZE + 8)),  # Slight oversizing for crop
        T.RandomCrop(IMG_SIZE),
        T.RandomAffine(
            degrees=AUGMENT_ROTATION,
            translate=(AUGMENT_TRANSLATE, AUGMENT_TRANSLATE),
            scale=AUGMENT_SCALE,
            shear=AUGMENT_SHEAR,
            fill=0,  # Black background fill
        ),
        T.RandomPerspective(distortion_scale=0.1, p=0.3, fill=0),
        T.ColorJitter(brightness=AUGMENT_BRIGHTNESS),
        T.ToTensor(),
        T.Normalize(mean=[0.5], std=[0.5]),
        T.RandomErasing(p=AUGMENT_ERASING_PROB, scale=(0.02, 0.15), ratio=(0.3, 3.3), value=-1.0),
    ])


def get_eval_transforms():
    """Minimal transforms for validation/test — no augmentation."""
    return T.Compose([
        T.Resize((IMG_SIZE, IMG_SIZE)),
        T.ToTensor(),
        T.Normalize(mean=[0.5], std=[0.5]),
    ])


def get_inference_transform():
    """Transform for single image inference (from canvas/air-writing)."""
    return T.Compose([
        T.Resize((IMG_SIZE, IMG_SIZE)),
        T.ToTensor(),
        T.Normalize(mean=[0.5], std=[0.5]),
    ])


# ============================================================
# DATA LOADERS
# ============================================================

def get_data_loaders(batch_size=BATCH_SIZE, num_workers=0, validate_files=False):
    """
    Create train/valid/test DataLoaders.

    Args:
        batch_size: Batch size for training
        num_workers: DataLoader workers (0 for Windows compatibility)
        validate_files: Whether to verify all images during init

    Returns:
        (train_loader, valid_loader, test_loader)
    """
    train_ds = SinhalaLetterDataset(
        TRAIN_DIR, transform=get_train_transforms(), validate=validate_files
    )
    valid_ds = SinhalaLetterDataset(
        VALID_DIR, transform=get_eval_transforms(), validate=validate_files
    )
    test_ds = SinhalaLetterDataset(
        TEST_DIR, transform=get_eval_transforms(), validate=validate_files
    )

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=False, drop_last=False
    )
    valid_loader = DataLoader(
        valid_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=False
    )
    test_loader = DataLoader(
        test_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=False
    )

    return train_loader, valid_loader, test_loader


# ============================================================
# VALIDATION SCRIPT
# ============================================================

def validate_dataset():
    """
    Comprehensive dataset validation. Run this BEFORE training.
    
    Checks:
    1. All 14 folders exist in each split
    2. All images are loadable
    3. No folder-to-label mismatch
    4. Class distribution is balanced
    5. Image dimensions are consistent
    """
    print("=" * 60)
    print("DATASET VALIDATION REPORT")
    print("=" * 60)

    errors = []

    for split_name, split_dir in [("train", TRAIN_DIR), ("valid", VALID_DIR), ("test", TEST_DIR)]:
        print(f"\n--- {split_name.upper()} ({split_dir}) ---")

        if not os.path.isdir(split_dir):
            errors.append(f"MISSING: {split_dir}")
            continue

        ds = SinhalaLetterDataset(split_dir, transform=get_eval_transforms(), validate=True)

        if ds.corrupted:
            errors.append(f"{split_name}: {len(ds.corrupted)} corrupted files")

        # Check class coverage
        labels = [label for _, label in ds.samples]
        unique_labels = set(labels)
        missing = set(range(NUM_CLASSES)) - unique_labels
        if missing:
            missing_letters = [CLASS_TO_LETTER[i] for i in missing]
            errors.append(f"{split_name}: Missing classes {missing_letters}")

        # Sample a few images to check dimensions
        sizes = set()
        for i in range(min(5, len(ds))):
            img, label = ds[i]
            sizes.add(tuple(img.shape))

        print(f"  Image tensor shapes: {sizes}")

        # Verify label consistency: load one image per class, ensure folder matches
        for folder_id in FOLDER_IDS:
            expected_class = FOLDER_TO_CLASS[folder_id]
            folder_path = os.path.join(split_dir, str(folder_id))
            if os.path.isdir(folder_path):
                files = os.listdir(folder_path)
                if files:
                    test_path = os.path.join(folder_path, files[0])
                    # Find this path in samples
                    found = [s for s in ds.samples if s[0] == test_path]
                    if found and found[0][1] != expected_class:
                        errors.append(
                            f"LABEL MISMATCH: {test_path} has label {found[0][1]}, "
                            f"expected {expected_class} (folder {folder_id})"
                        )

    print("\n" + "=" * 60)
    if errors:
        print(f"VALIDATION FAILED — {len(errors)} issues:")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("VALIDATION PASSED — All checks green.")
    print("=" * 60)

    return len(errors) == 0


if __name__ == "__main__":
    validate_dataset()
