"""
Recognition Gatekeeper — Validates Letter Identity Before Scoring
=================================================================
Flow:
1. User selects target letter (e.g., "ක")
2. User writes in the air
3. Gatekeeper runs ML recognition
4. IF predicted ≠ target → BLOCK scoring, show error, log attempt
5. IF predicted = target → ALLOW scoring pipeline to continue

This prevents scoring a completely wrong letter and giving feedback
that doesn't make sense (e.g., scoring "ක" against template when "ග" was written).
"""

import torch
import torch.nn.functional as F

from ml_pipeline.ml_config import (
    CONFIDENCE_THRESHOLD, WRONG_LETTER_BLOCK_THRESHOLD,
    REJECT_THRESHOLD, CLASS_TO_LETTER, CLASS_TO_FOLDER,
    LETTER_TO_CLASS, FOLDER_TO_CLASS, NUM_CLASSES,
)
from ml_pipeline.predict import get_ml_predictor


# Singleton recognizer
_recognizer_instance = None


class LetterRecognizer:
    """
    Gatekeeper that determines:
    1. WHAT letter was drawn (recognition)
    2. WHETHER it matches the target (validation)
    3. WHETHER to allow scoring (gating decision)
    """

    def __init__(self):
        self.predictor = get_ml_predictor()

    def predict(self, path_points):
        """
        Raw prediction — identify what letter was drawn.
        
        Returns:
            dict with class_id, letter, confidence, probabilities, is_confident
        """
        return self.predictor.predict(path_points)

    def validate_letter(self, path_points, target_letter=None, target_folder_id=None):
        """
        Full gatekeeper validation.
        
        Args:
            path_points: [{x, y, t}, ...] from frontend
            target_letter: Target Sinhala character (e.g., "ක")
            target_folder_id: Target folder ID (e.g., 12)
            
        At least one of target_letter or target_folder_id must be provided.
        
        Returns:
            dict:
                allowed: bool — whether to proceed to scoring
                predicted_letter: str — what the model thinks was drawn
                target_letter: str — what was expected
                confidence: float — model confidence
                match: bool — whether prediction matches target
                reason: str — explanation of decision
                all_probabilities: dict — full probability distribution
        """
        # Resolve target
        if target_letter and target_letter in LETTER_TO_CLASS:
            target_class = LETTER_TO_CLASS[target_letter]
        elif target_folder_id and target_folder_id in FOLDER_TO_CLASS:
            target_class = FOLDER_TO_CLASS[target_folder_id]
            target_letter = CLASS_TO_LETTER[target_class]
        else:
            # Can't validate without a target — allow scoring
            return {
                'allowed': True,
                'predicted_letter': '?',
                'target_letter': target_letter or '?',
                'confidence': 0.0,
                'match': False,
                'reason': 'No valid target specified, allowing scoring.',
                'all_probabilities': {},
            }

        # Run prediction
        prediction = self.predictor.predict(path_points)

        predicted_class = prediction.get('class_index', -1)
        predicted_letter = prediction.get('letter', '?')
        confidence = prediction.get('confidence', 0.0)
        all_probs = prediction.get('probabilities', {})

        # Get confidence specifically for the TARGET letter
        target_folder_id_resolved = CLASS_TO_FOLDER.get(target_class)
        target_confidence = float(all_probs.get(str(target_folder_id_resolved), 0.0))

        # Decision logic
        match = (predicted_class == target_class)

        if confidence < REJECT_THRESHOLD:
            # Very low confidence — can't determine letter at all
            return {
                'allowed': False,
                'predicted_letter': predicted_letter,
                'target_letter': target_letter,
                'confidence': confidence,
                'target_confidence': target_confidence,
                'match': False,
                'reason': f'Unrecognizable input (confidence {confidence:.0%}). Please try writing more clearly.',
                'all_probabilities': all_probs,
            }

        if match and confidence >= CONFIDENCE_THRESHOLD:
            # High confidence match — allow scoring
            return {
                'allowed': True,
                'predicted_letter': predicted_letter,
                'target_letter': target_letter,
                'confidence': confidence,
                'target_confidence': target_confidence,
                'match': True,
                'reason': f'Correct letter recognized ({confidence:.0%} confidence).',
                'all_probabilities': all_probs,
            }

        if match and confidence < CONFIDENCE_THRESHOLD:
            # Low confidence match — still allow but warn
            return {
                'allowed': True,
                'predicted_letter': predicted_letter,
                'target_letter': target_letter,
                'confidence': confidence,
                'target_confidence': target_confidence,
                'match': True,
                'reason': f'Letter appears correct but confidence is low ({confidence:.0%}). Score may be less reliable.',
                'all_probabilities': all_probs,
            }

        if not match and confidence >= WRONG_LETTER_BLOCK_THRESHOLD:
            # High confidence WRONG letter — BLOCK scoring
            return {
                'allowed': False,
                'predicted_letter': predicted_letter,
                'target_letter': target_letter,
                'confidence': confidence,
                'target_confidence': target_confidence,
                'match': False,
                'reason': f'Incorrect letter. You wrote "{predicted_letter}" but the target is "{target_letter}". Please try again.',
                'all_probabilities': all_probs,
            }

        # Low confidence wrong letter — allow cautiously
        # The model isn't sure, so we give the benefit of the doubt
        return {
            'allowed': True,
            'predicted_letter': predicted_letter,
            'target_letter': target_letter,
            'confidence': confidence,
            'target_confidence': target_confidence,
            'match': False,
            'reason': f'Model uncertain (predicted "{predicted_letter}" at {confidence:.0%}). Proceeding with scoring.',
            'all_probabilities': all_probs,
        }


def get_recognizer():
    """Get or create singleton LetterRecognizer."""
    global _recognizer_instance
    if _recognizer_instance is None:
        _recognizer_instance = LetterRecognizer()
    return _recognizer_instance
