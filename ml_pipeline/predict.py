"""
Prediction Module — ML Model Inference for Letter Recognition
==============================================================
Provides:
1. get_ml_predictor() — returns a singleton predictor  instance
2. hybrid_score() — combines ML prediction with template scoring
"""

import os
import torch
import torch.nn.functional as F
import numpy as np

from ml_pipeline.ml_config import (
    BEST_MODEL_PATH, NUM_CLASSES, CLASS_TO_LETTER, CLASS_TO_FOLDER,
    CONFIDENCE_THRESHOLD, IMG_SIZE,
)
from ml_pipeline.model import SinhalaCNN
from ml_pipeline.preprocessing import preprocess_for_inference


# Singleton predictor
_predictor_instance = None


class MLPredictor:
    """
    Stateful predictor that loads the model once and caches it.
    Handles stroke-to-prediction pipeline.
    """

    def __init__(self, model_path=BEST_MODEL_PATH, device='cpu'):
        self.device = device
        self.model = None
        self.model_path = model_path
        self.temperature = 1.0  # default; overwritten if checkpoint contains it
        self._load_model()

    def _load_model(self):
        """Load or reload the model from disk (supports both old and new checkpoint formats)."""
        if not os.path.exists(self.model_path):
            print(f"[MLPredictor] Model not found: {self.model_path}")
            self.model = None
            return

        try:
            self.model = SinhalaCNN().to(self.device)
            checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=False)

            if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                # New format: {model_state_dict, temperature}
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.temperature = checkpoint.get('temperature', 1.0)
                print(f"[MLPredictor] Loaded checkpoint (temperature={self.temperature:.4f})")
            else:
                # Legacy format: raw state_dict
                self.model.load_state_dict(checkpoint)
                self.temperature = 1.0

            self.model.eval()
            print(f"[MLPredictor] Model loaded from {self.model_path}")
        except Exception as e:
            print(f"[MLPredictor] Failed to load model: {e}")
            self.model = None

    def predict(self, path_points):
        """
        Predict which Sinhala letter was drawn.
        
        Args:
            path_points: List of {x, y, t} dicts from frontend canvas
        
        Returns:
            dict with:
                class_id: int (folder ID, e.g., 12 for ක)
                class_index: int (0-13)
                letter: str (Sinhala character)
                confidence: float (0-1)
                probabilities: dict mapping folder_id → probability
                is_confident: bool (above threshold)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Train the model first.")

        if not path_points or len(path_points) < 2:
            return self._empty_result()

        # Preprocess strokes → tensor
        tensor = preprocess_for_inference(path_points)
        tensor = tensor.to(self.device)

        # Forward pass with temperature scaling
        with torch.no_grad():
            logits = self.model(tensor)
            scaled_logits = logits / self.temperature
            probs = F.softmax(scaled_logits, dim=1).squeeze(0)  # (NUM_CLASSES,)

        # Get top prediction
        confidence, class_idx = probs.max(0)
        confidence = confidence.item()
        class_idx = class_idx.item()

        # Map back to folder ID and letter
        folder_id = CLASS_TO_FOLDER[class_idx]
        letter = CLASS_TO_LETTER[class_idx]

        # Build probability dict for all classes
        all_probs = {}
        for i in range(NUM_CLASSES):
            fid = CLASS_TO_FOLDER[i]
            all_probs[str(fid)] = round(probs[i].item(), 4)

        return {
            'class_id': folder_id,
            'class_index': class_idx,
            'letter': letter,
            'confidence': round(confidence, 4),
            'probabilities': all_probs,
            'is_confident': confidence >= CONFIDENCE_THRESHOLD,
        }

    def predict_top_k(self, path_points, k=3):
        """Get top-k predictions with probabilities."""
        result = self.predict(path_points)
        if result['confidence'] == 0:
            return result

        # Sort probabilities
        sorted_probs = sorted(
            result['probabilities'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:k]

        result['top_k'] = [
            {
                'folder_id': int(fid),
                'letter': CLASS_TO_LETTER.get(
                    next((idx for idx, f in CLASS_TO_FOLDER.items() if f == int(fid)), -1), '?'
                ),
                'probability': prob,
            }
            for fid, prob in sorted_probs
        ]

        return result

    def _empty_result(self):
        """Return a safe empty result when prediction fails."""
        all_probs = {str(CLASS_TO_FOLDER[i]): 0.0 for i in range(NUM_CLASSES)}
        return {
            'class_id': 0,
            'class_index': -1,
            'letter': '?',
            'confidence': 0.0,
            'probabilities': all_probs,
            'is_confident': False,
        }

    def reload_model(self):
        """Reload model from disk (after retraining)."""
        self._load_model()


def get_ml_predictor(model_path=BEST_MODEL_PATH):
    """Get or create singleton MLPredictor instance."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = MLPredictor(model_path=model_path)
    return _predictor_instance


def ml_only_evaluate(ml_result, target_letter=None, gatekeeper_result=None):
    """
    Full scoring pipeline using ONLY the ML model (no template data).
    Used when StrokePathJSON is empty but the letter is ML-supported.
    
    The target-specific confidence IS the quality signal:
    - High confidence for correct letter = well-written = high score
    - Low confidence = poorly written or ambiguous = low score
    
    Args:
        ml_result: dict from MLPredictor.predict()
        target_letter: str, the Sinhala character being practiced
        gatekeeper_result: dict from LetterRecognizer.validate_letter()
    
    Returns:
        dict matching evaluate_stroke() output format, with all required keys
    """
    from ml_pipeline.ml_config import LETTER_TO_CLASS, CLASS_TO_FOLDER

    # Get target-specific confidence
    target_conf = 0.0
    if gatekeeper_result and gatekeeper_result.get('target_confidence') is not None:
        target_conf = float(gatekeeper_result['target_confidence'])
    elif target_letter and target_letter in LETTER_TO_CLASS and ml_result:
        t_class = LETTER_TO_CLASS[target_letter]
        t_folder = CLASS_TO_FOLDER[t_class]
        target_conf = float(ml_result.get('probabilities', {}).get(str(t_folder), 0))

    # Score = target confidence scaled to 0-100
    score = round(target_conf * 100, 1)
    stars = _calc_stars(score)

    # Determine feedback level
    if score >= 90:
        feedback_level = 'excellent'
    elif score >= 75:
        feedback_level = 'good'
    elif score >= 60:
        feedback_level = 'fair'
    else:
        feedback_level = 'needs_practice'

    # Generate error analysis from ML prediction
    error_types = {
        'wrong_start': [],
        'missing_stroke': [],
        'extra_stroke': [],
        'wrong_direction': [],
        'poor_shape': [],
    }

    predicted_letter = ml_result.get('letter', '?') if ml_result else '?'
    is_match = gatekeeper_result.get('match', False) if gatekeeper_result else (predicted_letter == target_letter)
    overall_conf = ml_result.get('confidence', 0) if ml_result else 0

    # Infer error types from ML signals
    if not is_match and overall_conf > 0.3:
        # Model confidently sees a DIFFERENT letter → likely shape error
        error_types['poor_shape'] = list(range(10))
    elif target_conf < 0.4:
        # Very low target confidence → unclear writing
        error_types['poor_shape'] = list(range(5))
        if target_conf < 0.2:
            error_types['missing_stroke'] = [0, 1]
    elif target_conf < 0.6:
        # Medium confidence → minor issues
        error_types['poor_shape'] = [0, 1, 2]

    return {
        'score': score,
        'stars': stars,
        'error_indices': [],
        'error_types': error_types,
        'error_regions': [],
        'breakdown': {
            'ml_target_confidence': round(target_conf, 4),
            'ml_top_confidence': round(overall_conf, 4),
            'ml_predicted': predicted_letter,
        },
        'feedback_level': feedback_level,
        'scoring_method': 'ml_only',
        'ml_confidence': round(target_conf, 4),
        'ml_quality_score': score,
        'template_base_score': 0,
    }


def hybrid_score(template_result, ml_result, ml_weight=0.6, target_confidence=None):
    """
    Combine template-based scoring with ML prediction.
    
    When template_score is 0 (empty template data), uses ML as 100% of score
    to avoid artificially capping the result.
    
    Args:
        template_result: dict from vision_engine.evaluate_stroke()
        ml_result: dict from MLPredictor.predict()
        ml_weight: Weight for ML influence (0-1)
        target_confidence: float, confidence specifically for the target letter class.
    
    Returns:
        Updated template_result dict with hybrid scoring
    """
    template_score = template_result.get('score', 0)

    # Calculate ML quality score
    if target_confidence is not None and target_confidence > 0:
        ml_quality = target_confidence * 100
    else:
        ml_confidence = ml_result.get('confidence', 0) if ml_result else 0
        ml_quality = ml_confidence * 100

    # If template score is effectively zero (empty template data),
    # use ML as 100% of the score — don't penalize for missing template
    if template_score < 1.0:
        hybrid = ml_quality
        method = 'ml_dominant'
    else:
        template_weight = 1.0 - ml_weight
        hybrid = template_weight * template_score + ml_weight * ml_quality
        method = 'hybrid'

    hybrid = max(0.0, min(100.0, hybrid))

    # Update result
    template_result['score'] = round(hybrid, 2)
    template_result['stars'] = _calc_stars(hybrid)
    template_result['scoring_method'] = method
    template_result['ml_confidence'] = target_confidence if target_confidence else (ml_result.get('confidence', 0) if ml_result else 0)
    template_result['ml_quality_score'] = round(ml_quality, 2)
    template_result['template_base_score'] = round(template_score, 2)

    return template_result


def _calc_stars(score):
    if score >= 90: return 3
    if score >= 75: return 2
    if score >= 60: return 1
    return 0
