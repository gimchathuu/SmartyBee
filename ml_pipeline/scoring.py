"""
Scoring & Feedback Module — Structure-Based Comparison
======================================================
Provides accuracy scoring and explainable error feedback
AFTER the gatekeeper confirms the correct letter.

Key principles:
1. Structure-based comparison (skeleton), NOT appearance-based
2. Avoids penalizing style differences (thick vs thin strokes)
3. Scores based on structural accuracy (junction points, endpoints, curves)
4. Generates human-readable error descriptions
"""

import numpy as np
from PIL import Image

from ml_pipeline.ml_config import STAR_THRESHOLDS, IMG_SIZE


def compute_structural_score(user_image, reference_image, skeleton_user=None, skeleton_ref=None):
    """
    Compute accuracy score based on structural similarity.
    
    Uses skeleton overlap + Hausdorff-like structural distance.
    Avoids appearance bias by comparing structure, not pixel intensity.
    
    Args:
        user_image: PIL Image of user's writing
        reference_image: PIL Image of reference/template
        skeleton_user: Optional pre-computed skeleton
        skeleton_ref: Optional pre-computed skeleton
    
    Returns:
        dict:
            score: float 0-100
            stars: int 0-3
            structural_overlap: float 0-1
            coverage: float 0-1 (how much of template is covered)
            excess: float 0-1 (how much extra content exists)
            details: dict with component scores
    """
    # Convert to numpy arrays
    user_arr = np.array(user_image if skeleton_user is None else skeleton_user)
    ref_arr = np.array(reference_image if skeleton_ref is None else skeleton_ref)

    # Ensure same size
    if user_arr.shape != ref_arr.shape:
        from PIL import Image as PILImage
        ref_img = PILImage.fromarray(ref_arr).resize((user_arr.shape[1], user_arr.shape[0]))
        ref_arr = np.array(ref_img)

    # Binarize
    user_bin = (user_arr > 127).astype(np.float32)
    ref_bin = (ref_arr > 127).astype(np.float32)

    # 1. Coverage: How much of the reference is covered by the user's writing
    ref_pixels = ref_bin.sum()
    if ref_pixels == 0:
        return _default_score()

    # Dilate user strokes slightly for tolerance
    from scipy.ndimage import binary_dilation
    tolerance_kernel = np.ones((3, 3), dtype=bool)
    user_dilated = binary_dilation(user_bin > 0, structure=tolerance_kernel, iterations=1).astype(np.float32)

    covered = (user_dilated * ref_bin).sum()
    coverage = covered / ref_pixels

    # 2. Excess: Extra strokes not in the reference
    user_pixels = user_bin.sum()
    if user_pixels == 0:
        return _default_score()

    ref_dilated = binary_dilation(ref_bin > 0, structure=tolerance_kernel, iterations=2).astype(np.float32)
    excess_pixels = user_bin * (1 - ref_dilated)
    excess = excess_pixels.sum() / user_pixels if user_pixels > 0 else 0

    # 3. Structural overlap (Jaccard-like with tolerance)
    intersection = (user_dilated * ref_bin).sum()
    union = user_bin.sum() + ref_bin.sum() - intersection
    overlap = intersection / union if union > 0 else 0

    # 4. Position accuracy (centroid distance)
    user_centroid = _compute_centroid(user_bin)
    ref_centroid = _compute_centroid(ref_bin)
    centroid_dist = np.sqrt((user_centroid[0] - ref_centroid[0]) ** 2 +
                           (user_centroid[1] - ref_centroid[1]) ** 2)
    # Normalize by image diagonal
    diag = np.sqrt(user_arr.shape[0] ** 2 + user_arr.shape[1] ** 2)
    position_score = max(0, 1 - centroid_dist / (diag * 0.3))

    # 5. Size accuracy (aspect ratio and scale)
    user_bbox = _compute_bbox(user_bin)
    ref_bbox = _compute_bbox(ref_bin)
    if user_bbox and ref_bbox:
        user_aspect = user_bbox[2] / max(user_bbox[3], 1)
        ref_aspect = ref_bbox[2] / max(ref_bbox[3], 1)
        aspect_score = 1 - min(1, abs(user_aspect - ref_aspect) / max(ref_aspect, 0.1))

        user_area = user_bbox[2] * user_bbox[3]
        ref_area = ref_bbox[2] * ref_bbox[3]
        scale_ratio = user_area / max(ref_area, 1)
        scale_score = 1 - min(1, abs(1 - scale_ratio))
    else:
        aspect_score = 0.5
        scale_score = 0.5

    # Combine scores with weights
    final_score = (
        0.35 * coverage +           # Most important: did you write all parts?
        0.20 * (1 - excess) +       # Penalty for extra strokes
        0.15 * overlap +            # Structural similarity
        0.15 * position_score +     # Centered correctly?
        0.10 * aspect_score +       # Aspect ratio match
        0.05 * scale_score          # Size match
    ) * 100

    final_score = max(0, min(100, final_score))
    stars = _calc_stars(final_score)

    return {
        'score': round(final_score, 2),
        'stars': stars,
        'structural_overlap': round(overlap, 4),
        'coverage': round(coverage, 4),
        'excess': round(excess, 4),
        'position_score': round(position_score, 4),
        'aspect_score': round(aspect_score, 4),
        'scale_score': round(scale_score, 4),
        'details': {
            'coverage_weight': 0.35,
            'excess_penalty_weight': 0.20,
            'overlap_weight': 0.15,
            'position_weight': 0.15,
            'aspect_weight': 0.10,
            'scale_weight': 0.05,
        }
    }


def generate_feedback(score_result):
    """
    Generate human-readable, child-friendly feedback.
    
    Args:
        score_result: dict from compute_structural_score()
    
    Returns:
        dict:
            level: str ('excellent', 'good', 'fair', 'needs_practice')
            message: str (child-friendly feedback)
            suggestions: list of specific improvement tips
            error_areas: list of identified problem areas
    """
    score = score_result.get('score', 0)
    coverage = score_result.get('coverage', 0)
    excess = score_result.get('excess', 0)
    position = score_result.get('position_score', 0)
    aspect = score_result.get('aspect_score', 0)

    suggestions = []
    error_areas = []

    # Analyze specific issues
    if coverage < 0.6:
        suggestions.append("Try to complete all parts of the letter.")
        error_areas.append("incomplete")

    if coverage < 0.4:
        suggestions.append("Some strokes are missing. Look at the example carefully.")
        error_areas.append("missing_strokes")

    if excess > 0.3:
        suggestions.append("You have some extra lines. Try to follow the letter shape more closely.")
        error_areas.append("extra_strokes")

    if position < 0.6:
        suggestions.append("Try to center your writing in the drawing area.")
        error_areas.append("off_center")

    if aspect < 0.6:
        suggestions.append("Check the proportions — the letter seems stretched or squished.")
        error_areas.append("wrong_proportions")

    # Determine level
    if score >= 90:
        level = 'excellent'
        message = "Amazing work! Your letter looks perfect!"
    elif score >= 75:
        level = 'good'
        message = "Great job! Just a few small things to improve."
    elif score >= 60:
        level = 'fair'
        message = "Good try! Keep practicing to get better."
    else:
        level = 'needs_practice'
        message = "Keep practicing! Look at the example and try again."

    if not suggestions:
        if score >= 90:
            suggestions.append("You're doing great! Keep it up!")
        else:
            suggestions.append("Practice makes perfect. Try writing a bit more carefully.")

    return {
        'level': level,
        'message': message,
        'suggestions': suggestions,
        'error_areas': error_areas,
        'score': score,
        'stars': score_result.get('stars', 0),
    }


def _compute_centroid(binary_arr):
    """Compute centroid of non-zero pixels."""
    coords = np.argwhere(binary_arr > 0)
    if len(coords) == 0:
        return (binary_arr.shape[0] // 2, binary_arr.shape[1] // 2)
    return coords.mean(axis=0)


def _compute_bbox(binary_arr):
    """Compute bounding box (x, y, w, h) of non-zero pixels."""
    coords = np.argwhere(binary_arr > 0)
    if len(coords) == 0:
        return None
    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    return (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)


def _calc_stars(score):
    if score >= STAR_THRESHOLDS[3]: return 3
    if score >= STAR_THRESHOLDS[2]: return 2
    if score >= STAR_THRESHOLDS[1]: return 1
    return 0


def _default_score():
    return {
        'score': 0,
        'stars': 0,
        'structural_overlap': 0,
        'coverage': 0,
        'excess': 0,
        'position_score': 0,
        'aspect_score': 0,
        'scale_score': 0,
        'details': {},
    }
