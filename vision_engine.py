"""
SmartyBee — Vision Engine
Complete AI-Powered Stroke Evaluation Pipeline

Pipeline stages:
  1. Preprocessing  — normalize, filter, smooth
  2. Alignment      — Procrustes analysis
  3. Distance       — Hausdorff, Chamfer, DTW, Fréchet
  4. Scoring        — weighted combination → 0-100
  5. Error Detection — classify & locate errors
"""

import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean, directed_hausdorff, cdist
from scipy.ndimage import median_filter as scipy_median_filter

# ============================================================
# CONSTANTS
# ============================================================

# Number of points to resample strokes to (for equal-length comparison)
RESAMPLE_N = 128

# Weights for geometric score (sum to 0.75)
# CNN contributes the remaining 25% — handled in app.py blend step.
# When CNN is not available, geometric score is used as-is (0-100).
W_PROCRUSTES = 0.10
W_HAUSDORFF  = 0.15
W_CHAMFER    = 0.15
W_DTW        = 0.15
W_COVERAGE   = 0.20   # Most important: completeness

# Max expected distances for normalization to [0, 1]
# Calibrated for Procrustes-normalized coordinates (unit Frobenius norm)
# Relaxed for child-friendly scoring — small geometric errors should
# not cause catastrophic score drops.
# These are also published from ml_config.py for cross-module consistency.
from ml_pipeline.ml_config import (
    MAX_PROCRUSTES, MAX_HAUSDORFF, MAX_CHAMFER, MAX_DTW,
    STAR_5_THRESHOLD, STAR_4_THRESHOLD, STAR_3_THRESHOLD, STAR_2_THRESHOLD, STAR_1_THRESHOLD,
)
MAX_FRECHET    = 0.30

# Coverage calculation threshold (adaptive — set to None for auto)
COVERAGE_DISTANCE_THRESHOLD = None  # auto-calculated from shape extent

# Error detection thresholds (relaxed to prevent false positive wrong start/shape for children)
ERROR_THRESHOLD_POINT   = 0.25   # was 0.20
START_POINT_THRESHOLD   = 0.35   # was 0.30
DIRECTION_CHECK_WINDOW  = 10     # points to check for direction errors

# Star thresholds (imported from ml_config for consistency)
STAR_THRESHOLDS = {
    5: STAR_5_THRESHOLD, 
    4: STAR_4_THRESHOLD, 
    3: STAR_3_THRESHOLD, 
    2: STAR_2_THRESHOLD, 
    1: STAR_1_THRESHOLD
}


# ============================================================
# 1. PREPROCESSING MODULE
# ============================================================

def _extract_points(path):
    """
    Convert raw path data to NumPy arrays.
    Input:  [{'x': float, 'y': float, 't': int (optional)}, ...]
    Output: (Nx2 xy_array, Nx1 timestamps_or_None)
    """
    if not path or len(path) < 2:
        return np.array([]), None

    points = np.array([[p['x'], p['y']] for p in path], dtype=np.float64)

    # Extract timestamps if available
    timestamps = None
    if 't' in path[0]:
        timestamps = np.array([p.get('t', 0) for p in path], dtype=np.float64)

    return points, timestamps


def normalize_coordinates(points):
    """
    Step 1 — Coordinate Normalization.
    Centers stroke on origin and scales to unit box [-1, 1],
    preserving aspect ratio. Makes comparison device-independent.
    """
    if len(points) < 2:
        return points.copy()

    pts = points.copy()

    # Translate centroid to origin
    centroid = np.mean(pts, axis=0)
    pts -= centroid

    # Scale to unit box preserving aspect ratio
    max_dev = np.max(np.abs(pts))
    if max_dev > 1e-8:
        pts /= max_dev

    return pts


def apply_kalman_filter(points, process_noise=1e-3, measurement_noise=1e-1):
    """
    Step 2a — Kalman Filter.
    Smooths stroke by predicting next position based on motion history
    and correcting with the measurement. Good for continuous smoothing.
    Implements a simple 1D Kalman filter independently on x and y.
    """
    if len(points) < 3:
        return points.copy()

    n = len(points)
    smoothed = np.zeros_like(points)

    for dim in range(2):  # x=0, y=1
        # Initial state
        x_est = points[0, dim]
        p_est = 1.0  # initial uncertainty

        Q = process_noise    # process noise covariance
        R = measurement_noise  # measurement noise covariance

        for i in range(n):
            # Prediction step (constant velocity model simplified to random walk)
            x_pred = x_est
            p_pred = p_est + Q

            # Update step
            K = p_pred / (p_pred + R)  # Kalman gain
            x_est = x_pred + K * (points[i, dim] - x_pred)
            p_est = (1 - K) * p_pred

            smoothed[i, dim] = x_est

    return smoothed


def apply_median_filter(points, kernel_size=3):
    """
    Step 2b — Median Filter.
    Replaces each point with the median of its neighbors.
    Best for removing sudden jumps or outliers.
    """
    if len(points) < kernel_size:
        return points.copy()

    filtered = np.zeros_like(points)
    filtered[:, 0] = scipy_median_filter(points[:, 0], size=kernel_size)
    filtered[:, 1] = scipy_median_filter(points[:, 1], size=kernel_size)
    return filtered


def resample_points(points, n_points=RESAMPLE_N):
    """
    Resample stroke to a fixed number of evenly-spaced points along the path.
    Required for Procrustes (equal-length arrays) and consistent comparison.
    """
    if len(points) < 2:
        return points.copy()

    # Calculate cumulative arc length
    diffs = np.diff(points, axis=0)
    segment_lengths = np.sqrt(np.sum(diffs ** 2, axis=1))
    cumulative = np.zeros(len(points))
    cumulative[1:] = np.cumsum(segment_lengths)
    total_length = cumulative[-1]

    if total_length < 1e-8:
        return np.tile(points[0], (n_points, 1))

    # Evenly-spaced target distances
    target_distances = np.linspace(0, total_length, n_points)

    # Interpolate
    resampled = np.zeros((n_points, 2))
    resampled[:, 0] = np.interp(target_distances, cumulative, points[:, 0])
    resampled[:, 1] = np.interp(target_distances, cumulative, points[:, 1])

    return resampled


def preprocess_stroke(raw_path):
    """
    Full preprocessing pipeline (Steps 1-3 from technical doc).

    Input:  [{'x': float, 'y': float, 't': int}, ...]
    Output: (preprocessed Nx2 array, timestamps or None)
    """
    points, timestamps = _extract_points(raw_path)

    if len(points) < 2:
        return np.array([]), None

    # Step 1: Coordinate normalization
    points = normalize_coordinates(points)

    # Step 2a: Kalman filter (continuous smoothing)
    points = apply_kalman_filter(points)

    # Step 2b: Median filter (remove outlier jumps)
    points = apply_median_filter(points, kernel_size=3)

    # Resample to fixed number of points
    points = resample_points(points, RESAMPLE_N)

    return points, timestamps


# ============================================================
# 2. PROCRUSTES ANALYSIS — Alignment Stage
# ============================================================

def procrustes_align(child_points, template_points):
    """
    Procrustes Analysis — Run FIRST before any other algorithm.
    Aligns child stroke with template by removing:
      - Translation (position difference)
      - Rotation
      - Scale (size difference)

    Both inputs must be Nx2 arrays of equal length (use resample_points first).

    Returns: (aligned_child, aligned_template, residual_error)
      residual_error = sqrt( Σ ||Xi - Yi||² )
    """
    if len(child_points) != len(template_points):
        # Force equal length via resampling
        n = min(len(child_points), len(template_points))
        child_points = resample_points(child_points, n)
        template_points = resample_points(template_points, n)

    # Center both on origin
    child_centered = child_points - np.mean(child_points, axis=0)
    template_centered = template_points - np.mean(template_points, axis=0)

    # Scale both to unit norm (Frobenius)
    child_norm = np.linalg.norm(child_centered)
    template_norm = np.linalg.norm(template_centered)

    if child_norm < 1e-8 or template_norm < 1e-8:
        return child_points, template_points, 1.0

    child_scaled = child_centered / child_norm
    template_scaled = template_centered / template_norm

    # Find optimal rotation using SVD
    M = template_scaled.T @ child_scaled
    U, S, Vt = np.linalg.svd(M)
    R = U @ Vt  # Optimal rotation matrix

    # Handle reflection
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = U @ Vt

    # Apply rotation to child
    child_aligned = child_scaled @ R.T

    # Calculate residual error: d = sqrt(Σ ||Xi - Yi||²)
    residual = np.sqrt(np.sum((child_aligned - template_scaled) ** 2))

    return child_aligned, template_scaled, residual


# ============================================================
# 3. DISTANCE METRICS
# ============================================================

def hausdorff_distance(points_a, points_b):
    """
    Hausdorff Distance — Worst Error Detection.

    Finds the single largest gap between child stroke and template.
    H(X,Y) = max( max_x∈X min_y∈Y d(x,y), max_y∈Y min_x∈X d(x,y) )

    Very sensitive to outliers — catches the worst single error.
    Good for detecting: missing loops, large deviations, incomplete strokes.

    Returns: distance value H ∈ [0, ∞), lower is better
    """
    d_forward = directed_hausdorff(points_a, points_b)[0]
    d_backward = directed_hausdorff(points_b, points_a)[0]
    return max(d_forward, d_backward)


def chamfer_distance(points_a, points_b):
    """
    Chamfer Distance — Average Shape Error.

    Measures the average distance between each point in child's stroke
    and its nearest point in the template. Not sensitive to single outliers.
    Good for detecting: general neatness, overall shape accuracy.

    Returns: average distance, lower means better overall shape
    """
    dist_matrix = cdist(points_a, points_b, metric='euclidean')

    # Forward: for each point in A, find min distance to any point in B
    min_a_to_b = np.min(dist_matrix, axis=1)
    # Backward: for each point in B, find min distance to any point in A
    min_b_to_a = np.min(dist_matrix, axis=0)

    # Average of forward + backward
    return (np.mean(min_a_to_b) + np.mean(min_b_to_a)) / 2.0


def dtw_distance(points_a, points_b):
    """
    Dynamic Time Warping — Speed & Time Comparison.

    Compares stroke trajectories allowing for speed variations.
    Handles the fact that children write at different speeds.
    Good for detecting: timing variations, unequal number of points.

    A child who writes correctly but slowly should NOT be penalized.

    Returns: (normalized_distance, dtw_path)
    """
    distance, path = fastdtw(points_a, points_b, dist=euclidean)

    # Normalize by total path length
    path_len = len(points_a) + len(points_b)
    normalized = distance / path_len if path_len > 0 else 0

    return normalized, path


def frechet_distance(points_a, points_b):
    """
    Discrete Fréchet Distance — Stroke Order & Direction Check.

    Measures geometric similarity while PRESERVING the order in which
    points were traced. Most strict algorithm — checks shape AND direction.
    Good for detecting: writing backwards, wrong stroke sequence, reversed direction.

    Uses the 'dog on a leash' analogy — both paths must stay close throughout.

    Returns: Fréchet distance value, lower is better
    """
    n = len(points_a)
    m = len(points_b)

    if n == 0 or m == 0:
        return float('inf')

    # Dynamic programming table
    dp = np.full((n, m), -1.0)

    def _dist(i, j):
        return euclidean(points_a[i], points_b[j])

    def _compute(i, j):
        if dp[i, j] > -0.5:
            return dp[i, j]

        d = _dist(i, j)

        if i == 0 and j == 0:
            dp[i, j] = d
        elif i == 0:
            dp[i, j] = max(_compute(0, j - 1), d)
        elif j == 0:
            dp[i, j] = max(_compute(i - 1, 0), d)
        else:
            dp[i, j] = max(
                min(_compute(i - 1, j), _compute(i - 1, j - 1), _compute(i, j - 1)),
                d
            )

        return dp[i, j]

    # Iterative version to avoid recursion depth issues
    for i in range(n):
        for j in range(m):
            d = _dist(i, j)
            if i == 0 and j == 0:
                dp[i, j] = d
            elif i == 0:
                dp[i, j] = max(dp[0, j - 1], d)
            elif j == 0:
                dp[i, j] = max(dp[i - 1, 0], d)
            else:
                dp[i, j] = max(
                    min(dp[i - 1, j], dp[i - 1, j - 1], dp[i, j - 1]),
                    d
                )

    return dp[n - 1, m - 1]


# ============================================================
# 4. SCORING MODULE
# ============================================================

def normalize_to_01(value, max_expected):
    """Normalize a distance value to [0, 1] where 0=perfect, 1=very poor."""
    return min(1.0, max(0.0, value / max_expected))


def calculate_coverage(child_aligned, template_aligned, threshold=COVERAGE_DISTANCE_THRESHOLD):
    """
    Coverage % — Completeness Check.

    Measures what percentage of the template stroke points are adequately
    'covered' by the child's writing.  For each template point, the nearest
    child point must be within *threshold* distance for it to count.

    Uses an adaptive threshold based on the template's spatial extent
    (8% of bounding diagonal) to handle Procrustes-normalized coordinates.

    Returns: float in [0, 100] — percentage of template points covered.
    """
    if len(child_aligned) < 2 or len(template_aligned) < 2:
        return 0.0

    # Adaptive threshold based on template's bounding diagonal
    if threshold is None:
        extent = np.max(template_aligned, axis=0) - np.min(template_aligned, axis=0)
        diag = np.sqrt(extent[0] ** 2 + extent[1] ** 2)
        threshold = max(0.005, diag * 0.08)  # 8% of diagonal

    dist_matrix = cdist(template_aligned, child_aligned, 'euclidean')
    min_dist_per_template = np.min(dist_matrix, axis=1)
    covered = np.sum(min_dist_per_template <= threshold)
    coverage_pct = (covered / len(template_aligned)) * 100.0
    return float(coverage_pct)


def calculate_weighted_score(procrustes_err, hausdorff_err, chamfer_err,
                             dtw_err, coverage_pct):
    """
    Combine all five geometric metric outputs into a single accuracy score (0-100).

    This produces the *geometric-only* score.  When CNN confidence is available,
    app.py blends this with the CNN component: final = 0.75 * geo + 0.25 * cnn.

    Algorithms & Weights (geometric portion — sum 0.75):
      Procrustes: 10%   — Alignment quality
      Hausdorff:  15%   — Worst single error
      Chamfer:    15%   — Average shape error
      DTW:        15%   — Timing / speed accuracy
      Coverage:   20%   — Completeness (most important)
      (CNN:       25%   — handled in app.py)

    Formula:
      coverage_error = (100 - coverage_pct) / 100
      final_error = Σ (weight_i × normalized_error_i)
      accuracy = max(0, 100 − final_error × 100)
    """
    # Normalize each distance metric to [0, 1] (0=perfect, 1=worst)
    p_norm = normalize_to_01(procrustes_err, MAX_PROCRUSTES)
    h_norm = normalize_to_01(hausdorff_err, MAX_HAUSDORFF)
    c_norm = normalize_to_01(chamfer_err, MAX_CHAMFER)
    d_norm = normalize_to_01(dtw_err, MAX_DTW)
    # Coverage: already 0-100 %, convert to error ratio [0,1]
    cov_error = 1.0 - (min(100.0, max(0.0, coverage_pct)) / 100.0)

    # Weighted combination
    final_error = (W_PROCRUSTES * p_norm +
                   W_HAUSDORFF  * h_norm +
                   W_CHAMFER    * c_norm +
                   W_DTW        * d_norm +
                   W_COVERAGE   * cov_error)

    # Convert to 0-100 score
    accuracy = (1.0 - final_error) * 100.0
    return max(0.0, min(100.0, accuracy))


def calculate_stars(score):
    """
    Convert accuracy score (0-100) to stars (0-5).
    """
    if score >= STAR_THRESHOLDS[5]:
        return 5
    elif score >= STAR_THRESHOLDS[4]:
        return 4
    elif score >= STAR_THRESHOLDS[3]:
        return 3
    elif score >= STAR_THRESHOLDS[2]:
        return 2
    elif score >= STAR_THRESHOLDS[1]:
        return 1
    return 0


# ============================================================
# 5. ERROR DETECTION MODULE
# ============================================================

def detect_errors(child_aligned, template_aligned, dtw_path=None):
    """
    Real-time error detection — classifies and locates errors.

    Error Types:
      - wrong_start:    Start point too far from template start (Fréchet early deviation)
      - missing_stroke: Large gap at specific area (Hausdorff spike)
      - extra_stroke:   Chamfer increase from extra marks
      - wrong_direction: Stroke traced in wrong order (Fréchet)
      - poor_shape:     General neatness issues (Chamfer + DTW)

    Returns: {
        'error_indices': [int],           — indices of error points in child stroke
        'error_types': {type: [indices]}, — classified by type
        'error_regions': [{start, end, type, severity}]
    }
    """
    errors = {
        'error_indices': set(),
        'error_types': {
            'wrong_start': [],
            'missing_stroke': [],
            'extra_stroke': [],
            'wrong_direction': [],
            'poor_shape': []
        },
        'error_regions': []
    }

    n_child = len(child_aligned)
    n_template = len(template_aligned)

    if n_child < 2 or n_template < 2:
        return _finalize_errors(errors)

    # --- Wrong start point ---
    start_dist = euclidean(child_aligned[0], template_aligned[0])
    if start_dist > START_POINT_THRESHOLD:
        errors['error_types']['wrong_start'] = [0, 1, 2]
        errors['error_indices'].update([0, 1, 2])
        errors['error_regions'].append({
            'start': 0, 'end': 2, 'type': 'wrong_start',
            'severity': min(1.0, start_dist / (START_POINT_THRESHOLD * 2))
        })

    # --- Per-point distance analysis ---
    dist_matrix = cdist(child_aligned, template_aligned, 'euclidean')
    min_distances = np.min(dist_matrix, axis=1)  # child → nearest template point
    nearest_template_idx = np.argmin(dist_matrix, axis=1)

    for i in range(n_child):
        if min_distances[i] > ERROR_THRESHOLD_POINT:
            errors['error_indices'].add(int(i))
            errors['error_types']['poor_shape'].append(int(i))

    # --- Missing stroke detection (Hausdorff-like spikes) ---
    # Check template points that have no nearby child point
    min_template_dist = np.min(dist_matrix, axis=0)  # template → nearest child
    missing_threshold = ERROR_THRESHOLD_POINT * 1.5
    for j in range(n_template):
        if min_template_dist[j] > missing_threshold:
            # Map back to child index region
            region_start = max(0, int(j * n_child / n_template) - 3)
            region_end = min(n_child - 1, int(j * n_child / n_template) + 3)
            errors['error_types']['missing_stroke'].extend(range(region_start, region_end + 1))
            errors['error_regions'].append({
                'start': region_start, 'end': region_end,
                'type': 'missing_stroke',
                'severity': min(1.0, min_template_dist[j] / (missing_threshold * 2))
            })

    # --- Wrong direction detection ---
    # Check if order of nearest-template indices is monotonically increasing
    if len(nearest_template_idx) > DIRECTION_CHECK_WINDOW:
        for i in range(0, n_child - DIRECTION_CHECK_WINDOW, DIRECTION_CHECK_WINDOW // 2):
            window = nearest_template_idx[i:i + DIRECTION_CHECK_WINDOW]
            # If the matched template indices are decreasing, direction is wrong
            diffs = np.diff(window.astype(float))
            if np.sum(diffs < 0) > len(diffs) * 0.7:
                indices = list(range(i, i + DIRECTION_CHECK_WINDOW))
                errors['error_types']['wrong_direction'].extend(indices)
                errors['error_indices'].update(indices)
                errors['error_regions'].append({
                    'start': i, 'end': i + DIRECTION_CHECK_WINDOW,
                    'type': 'wrong_direction',
                    'severity': 0.8
                })

    # --- Extra stroke detection ---
    # Points in child stroke that are far from ALL template points
    extra_threshold = ERROR_THRESHOLD_POINT * 2.0
    for i in range(n_child):
        if min_distances[i] > extra_threshold:
            if int(i) not in errors['error_types']['missing_stroke']:
                errors['error_types']['extra_stroke'].append(int(i))

    return _finalize_errors(errors)


def _finalize_errors(errors):
    """Convert sets to sorted lists and numpy types for JSON serialization."""
    errors['error_indices'] = sorted(list(errors['error_indices']))
    # Deduplicate error type lists
    for key in errors['error_types']:
        errors['error_types'][key] = sorted(list(set(
            int(x) for x in errors['error_types'][key]
        )))
    # Ensure error_regions have native Python types
    for region in errors['error_regions']:
        region['start'] = int(region['start'])
        region['end'] = int(region['end'])
        region['severity'] = float(region['severity'])
    return errors


# ============================================================
# 6. MAIN ENTRY POINTS
# ============================================================

def calculate_score(user_path_json, template_path_json):
    """
    Legacy-compatible entry point.
    Returns: (score, error_indices) — same signature as before.
    """
    result = evaluate_stroke(user_path_json, template_path_json)
    return result['score'], result['error_indices']


def evaluate_stroke(user_path, template_path):
    """
    Complete evaluation pipeline — the main function.

    Full flow:
      MediaPipe → Preprocess → Procrustes → 5 Algorithms → Score → Errors

    Input:
      user_path:     [{'x': float, 'y': float, 't': int}, ...]
      template_path: [{'x': float, 'y': float}, ...]

    Output: {
        'score':            float (0-100),
        'stars':            int (0-5),
        'error_indices':    [int],
        'error_types':      {type: [indices]},
        'error_regions':    [{start, end, type, severity}],
        'breakdown': {
            'procrustes':   float,
            'hausdorff':    float,
            'chamfer':      float,
            'dtw':          float,
            'frechet':      float
        },
        'feedback_level':   str ('excellent'|'good'|'fair'|'needs_practice')
    }
    """
    try:
        # ---- Stage 1: Preprocess both strokes ----
        child_pts, child_timestamps = preprocess_stroke(user_path)
        template_pts, _ = preprocess_stroke(template_path)

        if len(child_pts) < 2 or len(template_pts) < 2:
            return _empty_result()

        # ---- Stage 2: Procrustes Alignment (run FIRST) ----
        child_aligned, template_aligned, procrustes_err = procrustes_align(
            child_pts, template_pts
        )

        # ---- Stage 3: Calculate all metrics ----

        # 3a. Hausdorff — worst single error
        h_dist = hausdorff_distance(child_aligned, template_aligned)

        # 3b. Chamfer — average shape error
        c_dist = chamfer_distance(child_aligned, template_aligned)

        # 3c. DTW — speed/timing comparison
        d_dist, dtw_path = dtw_distance(child_aligned, template_aligned)

        # 3d. Fréchet — stroke order/direction (used for error detection)
        f_dist = frechet_distance(child_aligned, template_aligned)

        # 3e. Coverage % — completeness (what % of template is covered)
        cov_pct = calculate_coverage(child_aligned, template_aligned)

        # ---- Stage 4: Weighted Score (5 algorithms) ----
        score = calculate_weighted_score(
            procrustes_err, h_dist, c_dist, d_dist, cov_pct
        )
        stars = calculate_stars(score)

        # ---- Stage 5: Error Detection ----
        error_info = detect_errors(child_aligned, template_aligned, dtw_path)

        # Determine feedback level
        if score >= 90:
            feedback_level = 'excellent'
        elif score >= 75:
            feedback_level = 'good'
        elif score >= 60:
            feedback_level = 'fair'
        else:
            feedback_level = 'needs_practice'

        # Build list of active error type names
        error_list = [etype for etype, indices in error_info['error_types'].items()
                      if len(indices) > 0]

        # Compute error_score (inverse of accuracy)
        error_score = round(100.0 - score, 1)

        return {
            'score': float(round(score, 1)),
            'stars': int(stars),
            'error_score': float(error_score),
            'errors': error_list,
            'error_indices': error_info['error_indices'],
            'error_types': error_info['error_types'],
            'error_regions': error_info['error_regions'],
            'breakdown': {
                'procrustes': float(round(procrustes_err, 4)),
                'hausdorff': float(round(h_dist, 4)),
                'chamfer': float(round(c_dist, 4)),
                'dtw': float(round(d_dist, 4)),
                'coverage': float(round(cov_pct, 1)),
            },
            'feedback_level': feedback_level,
            'feedback_text': generate_feedback_text(
                score, error_info, cov_pct, h_dist, procrustes_err
            ),
            'scoring_method': 'geometric',
        }

    except Exception as e:
        print(f"[VisionEngine] Evaluation Error: {e}")
        import traceback
        traceback.print_exc()
        return _empty_result()


def generate_feedback_text(score, error_info, coverage, hausdorff, procrustes):
    """
    Generate a single human-readable, encouraging feedback sentence.
    Mentions HOW to correct — not just what is wrong.
    """
    errors = error_info.get('error_types', {})
    parts = []

    if score >= 90:
        return "Excellent work! Your letter looks perfect — keep it up!"

    # Build encouraging correction advice
    if errors.get('wrong_start'):
        parts.append("try starting closer to the top of the letter")
    if errors.get('wrong_direction'):
        parts.append("follow the stroke direction shown in the example")
    if errors.get('extra_stroke'):
        parts.append("avoid adding extra lines at the end")
    if errors.get('missing_stroke'):
        parts.append("make sure to complete all parts of the letter")
    if errors.get('poor_shape') and len(errors['poor_shape']) > 8:
        parts.append("trace the letter shape more carefully")
    elif errors.get('poor_shape'):
        parts.append("smooth out some of the curves a bit more")

    if coverage < 60:
        parts.append("try to cover all parts of the letter")

    if not parts:
        if score >= 75:
            return "Great job! Just a few small details to refine."
        else:
            return "Good effort! Keep practising — look at the example and try again."

    # Join into one encouraging sentence
    base = "Your letter shape is "
    if score >= 75:
        base += "good, but "
    elif score >= 60:
        base += "getting there — "
    else:
        base += "improving — "

    return base + ", ".join(parts) + "."


def _empty_result():
    """Return a zero-score result for edge cases."""
    return {
        'score': 0.0,
        'stars': 0,
        'error_score': 100.0,
        'errors': [],
        'error_indices': [],
        'error_types': {
            'wrong_start': [], 'missing_stroke': [],
            'extra_stroke': [], 'wrong_direction': [],
            'poor_shape': []
        },
        'error_regions': [],
        'breakdown': {
            'procrustes': 0, 'hausdorff': 0,
            'chamfer': 0, 'dtw': 0, 'coverage': 0
        },
        'feedback_level': 'needs_practice',
        'feedback_text': 'Not enough stroke data to evaluate. Please try drawing the full letter.',
        'scoring_method': 'geometric',
    }


# ============================================================
# LEGACY COMPATIBILITY
# ============================================================

def normalize_path(path):
    """
    Legacy function — kept for backward compatibility.
    Normalizes a list of points to a standardized box.
    """
    if not path or len(path) < 2:
        return np.array([])
    points = np.array([[p['x'], p['y']] for p in path])
    centroid = np.mean(points, axis=0)
    points = points - centroid
    max_dev = np.max(np.abs(points))
    if max_dev > 0:
        points = points / max_dev
    return points
