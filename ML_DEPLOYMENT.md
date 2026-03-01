# SmartyBee ML Pipeline — Deployment & Architecture Guide

## Architecture Overview

```
User draws letter → Canvas captures stroke points (x, y, t)
         ↓
  /api/submit_attempt  or  /api/recognize
         ↓
  ┌──────────────────────────────────┐
  │  Preprocessing (preprocessing.py)│
  │  stroke → image → binarize →    │
  │  dilate → center → tensor 64×64 │
  └──────────────┬───────────────────┘
                 ↓
  ┌──────────────────────────────────┐
  │  CNN Prediction (predict.py)     │
  │  SinhalaCNN → 14-class softmax  │
  │  Returns: letter, confidence,   │
  │  probabilities                   │
  └──────────────┬───────────────────┘
                 ↓
  ┌──────────────────────────────────┐
  │  Gatekeeper (recognize_letter.py)│
  │  Is predicted == target letter?  │
  │  Confidence above threshold?     │
  │  → ALLOW / BLOCK / REJECT       │
  └──────────────┬───────────────────┘
                 ↓
     If ALLOWED → Score with vision_engine.py
     If BLOCKED → Return error to user
     If REJECTED → "Unrecognizable" message
```

## Trained Model Stats

| Metric | Value |
|--------|-------|
| Test Accuracy | **97.32%** |
| Best Val Accuracy | 96.73% (epoch 49/61) |
| Parameters | 305,454 |
| Architecture | 3× ConvBlock (32→64→128) + GAP + FC |
| Input | 64×64 grayscale |
| Classes | 14 Sinhala letters |
| Training Time | ~30 min on CPU |
| Dataset | 2,685 train / 336 valid / 336 test |

### Per-Class Accuracy
| Letter | Accuracy | Avg Confidence |
|--------|----------|----------------|
| ක | 87.5% | 0.760 |
| ග | 95.8% | 0.933 |
| ට | 100.0% | 0.979 |
| ත | 100.0% | 0.917 |
| න | 100.0% | 0.918 |
| ප | 100.0% | 0.982 |
| බ | 91.7% | 0.915 |
| ම | 91.7% | 0.927 |
| ය | 100.0% | 0.964 |
| ර | 100.0% | 0.991 |
| ල | 100.0% | 0.999 |
| ව | 100.0% | 0.979 |
| හ | 100.0% | 0.966 |
| ෆ | 95.8% | 0.938 |

### Known Confusion Pairs
- ක → ත (3 cases)
- බ → ග (2 cases)
- ම → ව (2 cases)

## File Structure

```
ml_pipeline/
├── __init__.py          # Package init, version tag
├── ml_config.py         # ALL config: paths, mappings, hyperparams, thresholds
├── dataset.py           # PyTorch Dataset (14 target folders), transforms, loaders
├── preprocessing.py     # Stroke→image, binarize, dilate, center, inference pipeline
├── model.py             # SinhalaCNN (3 ConvBlocks + GAP + FC), ~305K params
├── train.py             # Full training loop with early stopping, cosine annealing
├── predict.py           # MLPredictor singleton (loads model, predicts)
├── recognize_letter.py  # Gatekeeper: validate_letter → allow/block/reject
├── scoring.py           # Structural scoring (coverage, overlap, position...)
├── collect_data.py      # Save user drawings as training data
├── db_integration.py    # ML database tables (7 tables), logging functions
├── debug_tools.py       # Post-training diagnostics suite
├── validate_dataset.py  # Pre-training dataset validation
└── saved_models/
    ├── best_model.pth        # Trained model weights
    └── training_log.json     # Training history
```

## Gatekeeper Thresholds (ml_config.py)

| Threshold | Value | Purpose |
|-----------|-------|---------|
| CONFIDENCE_THRESHOLD | 0.50 | Minimum to accept a prediction |
| WRONG_LETTER_BLOCK_THRESHOLD | 0.60 | If wrong letter predicted above this → BLOCK |
| REJECT_THRESHOLD | 0.20 | Below this → "unrecognizable" |

## How to Retrain

```bash
# 1. Activate venv
.venv\Scripts\activate

# 2. Validate dataset first
python -m ml_pipeline.validate_dataset

# 3. Train (auto saves best model)
python -m ml_pipeline.train

# 4. Run diagnostics
python -m ml_pipeline.debug_tools
```

## How to Create ML Database Tables

```bash
python -m ml_pipeline.db_integration
```

This creates 7 tables: ML_Model_Version, ML_Prediction, ML_Score, ML_Error_Feedback, ML_Stroke_Data, ML_Error_Log, ML_Training_Run.

## Config Flags (config.py)

| Flag | Default | Effect |
|------|---------|--------|
| USE_ML_MODEL | True | Use CNN for recognition (False = template only) |
| ML_WEIGHT | 0.7 | Hybrid score blend: 70% ML + 30% template |
| COLLECT_TRAINING_DATA | True | Save user drawings to collected_data/ |

## Known Issues & Notes

1. **Noise robustness**: CNN gives high confidence (0.999) on random noise. The gatekeeper handles this via threshold checks, but be aware during live testing.
2. **Data leakage**: The original Dataset454 has ~15% overlapping images between train/valid/test splits. Test accuracy (97.32%) may be slightly optimistic.
3. **ක confusion**: The weakest class (87.5%) — occasionally confused with ත. Users writing ක may need extra attempts.
4. **CPU inference**: Model runs on CPU (~50ms per prediction). Fast enough for real-time use.

## API Endpoints

### POST /api/recognize
Standalone recognition (used by recognition_test.html).
```json
// Request
{"path": [{"x": 0.1, "y": 0.2, "t": 0}, ...], "target_letter": "ක"}

// Response (success)
{"success": true, "letter": "ක", "letter_id": "12", "confidence": 0.85,
 "is_confident": true, "all_probabilities": {"12": 0.85, "25": 0.05, ...},
 "validation": {"allowed": true, "action": "allow", "reason": "..."}, "method": "ml"}
```

### POST /api/submit_attempt
Full attempt submission (used by learn.html/write.html). Includes gatekeeper + scoring + DB logging.
```json
// Response (blocked by gatekeeper)
{"success": false, "blocked": true, "predicted_letter": "ග",
 "target_letter": "ක", "confidence": 0.85, "message": "Wrong letter detected"}

// Response (allowed + scored)
{"success": true, "score": 78.5, "feedback": "Good work on ක!",
 "ml_prediction": {"letter": "ක", "confidence": 0.92}}
```
