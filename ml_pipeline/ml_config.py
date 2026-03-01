"""
ML Pipeline Configuration — Single Source of Truth
===================================================
All dataset paths, class mappings, hyperparameters, and thresholds.
NEVER hardcode these values elsewhere.
"""

import os

# ============================================================
# DATASET PATHS
# ============================================================

DATASET_ROOT = r"C:\Users\ASUS TUF A15\Downloads\SQW\archive (1)\Dataset454"
TRAIN_DIR = os.path.join(DATASET_ROOT, "train")
VALID_DIR = os.path.join(DATASET_ROOT, "valid")
TEST_DIR = os.path.join(DATASET_ROOT, "test")

# ============================================================
# CLASS MAPPING — CRITICAL: folder_id → class_index
# ============================================================
# The dataset uses numeric folder IDs (12, 25, 64, ...) for each Sinhala letter.
# These MUST be remapped to contiguous class indices [0-13].
# NEVER use folder IDs directly as labels — that creates a sparse 283-class problem.

FOLDER_TO_LETTER = {
    12:  "ක",
    25:  "ග",
    64:  "ට",
    93:  "ත",
    120: "න",
    134: "ප",
    149: "බ",
    164: "ම",
    179: "ය",
    190: "ර",
    198: "ල",
    208: "ව",
    264: "හ",
    282: "ෆ",
}

# Sorted folder IDs for deterministic index assignment
FOLDER_IDS = sorted(FOLDER_TO_LETTER.keys())  # [12, 25, 64, 93, 120, 134, 149, 164, 179, 190, 198, 208, 264, 282]

# folder_id → class_index (0-13)
FOLDER_TO_CLASS = {fid: idx for idx, fid in enumerate(FOLDER_IDS)}

# class_index → folder_id (reverse)
CLASS_TO_FOLDER = {idx: fid for fid, idx in FOLDER_TO_CLASS.items()}

# class_index → Sinhala letter
CLASS_TO_LETTER = {idx: FOLDER_TO_LETTER[fid] for idx, fid in CLASS_TO_FOLDER.items()}

# Sinhala letter → class_index
LETTER_TO_CLASS = {letter: idx for idx, letter in CLASS_TO_LETTER.items()}

NUM_CLASSES = len(FOLDER_IDS)  # 14

# ============================================================
# IMAGE PREPROCESSING
# ============================================================

IMG_SIZE = 64           # Input image size (64x64) — small model for small dataset
IMG_CHANNELS = 1        # Grayscale
SKELETON_ENABLED = True # Apply morphological skeletonization

# Preprocessing for bridging scanned handwriting ↔ digital air-writing
DILATION_KERNEL = 3     # Thicken thin strokes
BLUR_KERNEL = 3         # Gaussian blur radius for smoothing
BINARIZE_THRESH = 128   # Threshold for binary conversion
INVERT_COLORS = True    # If True, ensure white-on-black (stroke=white, bg=black)

# ============================================================
# MODEL ARCHITECTURE
# ============================================================

# Small-data-safe CNN designed for ~190 samples/class
MODEL_NAME = "SinhalaCNN"
DROPOUT_RATE = 0.4      # Heavy dropout for regularization
HIDDEN_DIM = 128        # FC hidden layer size
CONV_CHANNELS = [32, 64, 128]  # Progressive feature extraction

# ============================================================
# TRAINING HYPERPARAMETERS
# ============================================================

BATCH_SIZE = 32         # Faster convergence with more data
LEARNING_RATE = 1e-3    # Adam optimizer
WEIGHT_DECAY = 1e-4     # L2 regularization
NUM_EPOCHS = 120        # Max epochs (increased from 80 for better convergence)
EARLY_STOP_PATIENCE = 20 # Stop if no improvement for N epochs (increased from 12)

# Data augmentation (aggressive for small dataset)
AUGMENT_ROTATION = 20      # ±20 degrees (air writing rotates more)
AUGMENT_TRANSLATE = 0.15   # ±15% shift (air writing drifts more)
AUGMENT_SCALE = (0.80, 1.20)  # ±20% scale (air writing varies more)
AUGMENT_SHEAR = 8          # ±8 degrees shear
AUGMENT_ERASING_PROB = 0.2 # Random erasing probability
AUGMENT_BRIGHTNESS = 0.3   # ColorJitter brightness — handles lighting variation

# ============================================================
# RECOGNITION GATEKEEPER
# ============================================================

# Minimum confidence to accept a prediction
CONFIDENCE_THRESHOLD = 0.50

# Minimum confidence to BLOCK scoring (high confidence in WRONG letter)
WRONG_LETTER_BLOCK_THRESHOLD = 0.75

# Below this confidence, reject as "unrecognizable"
REJECT_THRESHOLD = 0.35

# Uncertainty zone boundaries
UNCERTAIN_ZONE_LOW = 0.35
UNCERTAIN_ZONE_HIGH = 0.75
UNCERTAIN_PENALTY_FACTOR = 0.85  # multiply final score by this in uncertain zone

# ============================================================
# SCORING — Child-friendly thresholds
# ============================================================

# Normalization constants for geometric scoring (relaxed for children)
MAX_PROCRUSTES = 0.40   # was 0.35 — alignment tolerance
MAX_HAUSDORFF  = 0.35   # was 0.30 — worst-point tolerance
MAX_CHAMFER    = 0.20   # was 0.15 — average shape tolerance
MAX_DTW        = 0.25   # was 0.22 — timing tolerance

# Star thresholds for 5-star system
STAR_5_THRESHOLD = 90
STAR_4_THRESHOLD = 80
STAR_3_THRESHOLD = 65
STAR_2_THRESHOLD = 50
STAR_1_THRESHOLD = 30
STAR_THRESHOLDS = {
    5: STAR_5_THRESHOLD,
    4: STAR_4_THRESHOLD, 
    3: STAR_3_THRESHOLD, 
    2: STAR_2_THRESHOLD, 
    1: STAR_1_THRESHOLD
}

# ============================================================
# MODEL PATHS
# ============================================================

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_models")
BEST_MODEL_PATH = os.path.join(MODEL_DIR, "best_model.pth")
TRAINING_LOG_PATH = os.path.join(MODEL_DIR, "training_log.json")

# ============================================================
# TRAINING DATA COLLECTION (from web app)
# ============================================================

COLLECTED_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "collected_data")
