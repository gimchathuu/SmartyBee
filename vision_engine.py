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
    Calculates similarity score and identifies error segments.
    Returns: (score, error_indices)
    """
    try:
        user_seq = normalize_path(user_path_json)
        template_seq = normalize_path(template_path_json)
        
        if len(user_seq) == 0 or len(template_seq) == 0:
            return 0.0, []

        # Dynamic Time Warping
        # fastdtw returns (distance, path)
        distance, path = fastdtw(user_seq, template_seq, dist=euclidean)
        
        # Calculate error indices
        # Identify user points that are too far from their matched template point
        ERROR_THRESHOLD = 0.15 # Normalized distance threshold (0.0 - 1.0 box)
        error_indices = set()
        
        for u_idx, t_idx in path:
            dist = euclidean(user_seq[u_idx], template_seq[t_idx])
            if dist > ERROR_THRESHOLD:
                error_indices.add(int(u_idx)) # Convert numpy int to standard int for JSON serializing
        
        # Normalize distance relative to complexity
        path_len = len(user_seq) + len(template_seq)
        avg_dist = distance / path_len
        
        # Tune this weight: Higher means stricter
        WEIGHT = 200 
        
        score = 100 - (avg_dist * WEIGHT)
        final_score = max(0.0, min(100.0, score))
        
        return final_score, list(error_indices)
        
    except Exception as e:
        print(f"Scoring Error: {e}")
        return 0.0, []
