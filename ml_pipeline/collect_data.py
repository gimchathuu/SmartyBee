"""
Training Data Collection — Saves User Strokes from Web App
============================================================
Collects stroke data during normal usage for future retraining.
Stores as images + metadata JSON for dataset expansion.
"""

import os
import json
import time
from PIL import Image

from ml_pipeline.ml_config import COLLECTED_DATA_DIR
from ml_pipeline.preprocessing import stroke_to_image, preprocess_image


def save_training_sample(letter_id, path_points, eval_result, metadata=None, input_mode='draw'):
    """
    Save a user's stroke as a training sample.
    
    Saved for each attempt:
    1. Raw stroke image (before preprocessing)
    2. Preprocessed image
    3. Metadata JSON (letter_id, score, stars, timestamp, recognition info, input_mode)
    
    Args:
        letter_id: Database letter ID
        path_points: [{x, y, t}, ...] from the frontend
        eval_result: dict from vision_engine.evaluate_stroke()
        metadata: Optional dict with extra info (predicted_id, confidence, etc.)
        input_mode: 'camera' for air-written or 'draw' for mouse/touch-drawn
    """
    if not path_points or len(path_points) < 5:
        return

    try:
        # Create directory structure
        sample_dir = os.path.join(COLLECTED_DATA_DIR, str(letter_id))
        os.makedirs(sample_dir, exist_ok=True)

        # Generate unique filename
        timestamp = int(time.time() * 1000)
        base_name = f"{timestamp}"

        # Save raw stroke image
        raw_img = stroke_to_image(path_points)
        raw_path = os.path.join(sample_dir, f"{base_name}_raw.png")
        raw_img.save(raw_path)

        # Save preprocessed image
        proc_img = preprocess_image(raw_img)
        proc_path = os.path.join(sample_dir, f"{base_name}_proc.png")
        proc_img.save(proc_path)

        # Save metadata
        meta = {
            'letter_id': letter_id,
            'timestamp': timestamp,
            'num_points': len(path_points),
            'score': eval_result.get('score', 0),
            'stars': eval_result.get('stars', 0),
            'feedback_level': eval_result.get('feedback_level', ''),
            'input_mode': input_mode,
        }

        if metadata:
            meta.update(metadata)

        meta_path = os.path.join(sample_dir, f"{base_name}_meta.json")
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)

    except Exception as e:
        print(f"[DataCollect] Error saving sample: {e}")
