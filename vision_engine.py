import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean

def normalize_path(path):
    """
    Normalizes a list of points (dictionaries or tuples) to a standardized 0-1 box,
    preserving aspect ratio and centering.
    Input: [{'x': 0.5, 'y': 0.1}, ...]
    Output: Nx2 NumPy array
    """
    if not path or len(path) < 2:
        return np.array([])

    # Convert to array
    points = np.array([[p['x'], p['y']] for p in path])
    
    # 1. Shift to origin (Center it)
    centroid = np.mean(points, axis=0)
    points = points - centroid
    
    # 2. Scale to unit box (maintain aspect ratio)
    # Find max dimension deviation
    max_dev = np.max(np.abs(points))
    if max_dev > 0:
        points = points / max_dev
        
    return points

def calculate_score(user_path_json, template_path_json):
    """
    Calculates similarity score between user path and template.
    Returns: Float (0.0 to 100.0)
    """
    try:
        user_seq = normalize_path(user_path_json)
        template_seq = normalize_path(template_path_json)
        
        if len(user_seq) == 0 or len(template_seq) == 0:
            return 0.0

        # Dynamic Time Warping
        # fastdtw returns (distance, path)
        distance, _ = fastdtw(user_seq, template_seq, dist=euclidean)
        
        # Normalize distance relative to complexity (length of path)
        # Average distance per point
        # Note: Depending on implementation, distance is the sum of euclidean distances of aligned points.
        # Max reasonable distance (if completely wrong) is ~2.0 per point (top-left to bottom-right in 1x1 box is sqrt(2) * 2 roughly).
        
        path_len = len(user_seq) + len(template_seq)
        avg_dist = distance / path_len
        
        # Heuristic mapping to 0-100 Score
        # If avg_dist is 0.0 -> Perfect -> 100
        # If avg_dist is > 0.5 -> Poor -> 0
        
        # Tune this weight: Higher means stricter
        WEIGHT = 200 
        
        score = 100 - (avg_dist * WEIGHT)
        return max(0.0, min(100.0, score))
        
    except Exception as e:
        print(f"Scoring Error: {e}")
        return 0.0
