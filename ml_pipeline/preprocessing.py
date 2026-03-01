"""
Preprocessing Module — Bridge Scanned Handwriting ↔ Digital Air-Writing
========================================================================
Converts both scanned handwriting images AND canvas/air-writing strokes
into a common representation for the CNN.

Key operations:
1. Binarization (Otsu/fixed threshold)
2. Morphological cleanup (dilation to thicken thin strokes)
3. Skeletonization (reduce to 1-pixel-wide skeleton for structure)
4. Centering & padding (writer-invariant normalization)
5. Stroke-to-image conversion (for air-writing input)
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import io

from ml_pipeline.ml_config import (
    IMG_SIZE, BINARIZE_THRESH, DILATION_KERNEL,
    BLUR_KERNEL, SKELETON_ENABLED, INVERT_COLORS,
)


def stroke_to_image(path_points, img_size=IMG_SIZE, line_width=3):
    """
    Convert air-writing stroke data [{x, y, t}, ...] to a PIL grayscale image.
    
    This is the CRITICAL bridge between the web canvas input and the CNN.
    The stroke coordinates are normalized [0, 1] from the frontend canvas.
    
    Args:
        path_points: List of dicts with 'x', 'y' keys (normalized 0-1)
        img_size: Output image size (square)
        line_width: Stroke thickness in pixels
    
    Returns:
        PIL Image (grayscale, white strokes on black background)
    """
    if not path_points or len(path_points) < 2:
        return Image.new('L', (img_size, img_size), 0)

    # Create black background
    img = Image.new('L', (img_size, img_size), 0)
    draw = ImageDraw.Draw(img)

    # Add margin (10% padding to prevent edge clipping)
    margin = int(img_size * 0.1)
    draw_size = img_size - 2 * margin

    # Extract coordinates
    points = []
    for p in path_points:
        x = p.get('x', 0)
        y = p.get('y', 0)
        # Clamp to [0, 1]
        x = max(0.0, min(1.0, float(x)))
        y = max(0.0, min(1.0, float(y)))
        # Scale to image coordinates with margin
        px = int(x * draw_size + margin)
        py = int(y * draw_size + margin)
        points.append((px, py))

    # Detect stroke breaks (large gaps = pen lift)
    # Use time gaps if available, otherwise spatial distance
    segments = []
    current_segment = [points[0]]

    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        dist = (dx ** 2 + dy ** 2) ** 0.5

        # If gap > 15% of image size, treat as pen lift
        if dist > img_size * 0.15:
            if len(current_segment) >= 2:
                segments.append(current_segment)
            current_segment = [points[i]]
        else:
            current_segment.append(points[i])

    if len(current_segment) >= 2:
        segments.append(current_segment)

    # Draw all segments
    for segment in segments:
        if len(segment) >= 2:
            draw.line(segment, fill=255, width=line_width)

    # Also draw single points as dots (for very short strokes)
    if not segments and len(points) >= 1:
        for p in points:
            r = line_width
            draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=255)

    return img


def preprocess_image(img, target_size=IMG_SIZE):
    """
    Full preprocessing pipeline for a single image (scanned or generated).
    
    Steps:
    1. Convert to grayscale
    2. Binarize
    3. Ensure white-on-black (normalize polarity)
    4. Morphological dilation (thicken thin strokes)
    5. Gaussian blur (smooth noise)
    6. Center the content with padding
    7. Resize to target size
    
    Args:
        img: PIL Image (any mode)
        target_size: Output size (square)
    
    Returns:
        PIL Image (grayscale, preprocessed)
    """
    # 1. Convert to grayscale
    if img.mode != 'L':
        img = img.convert('L')

    # 2. Convert to numpy for processing
    arr = np.array(img, dtype=np.uint8)

    # 3. Binarize using Otsu-like thresholding
    # Use simple threshold since our images are clean
    mean_val = np.mean(arr)
    if mean_val > 127:
        # Dark strokes on light background → invert for white-on-black
        arr = 255 - arr
    
    # Apply fixed threshold
    arr = np.where(arr > BINARIZE_THRESH // 2, 255, 0).astype(np.uint8)

    # 4. Morphological dilation (thicken strokes)
    if DILATION_KERNEL > 1:
        from scipy.ndimage import binary_dilation
        binary = arr > 127
        kernel = np.ones((DILATION_KERNEL, DILATION_KERNEL), dtype=bool)
        dilated = binary_dilation(binary, structure=kernel, iterations=1)
        arr = (dilated * 255).astype(np.uint8)

    # 5. Gaussian blur for smoothing
    img = Image.fromarray(arr)
    if BLUR_KERNEL > 1:
        img = img.filter(ImageFilter.GaussianBlur(radius=BLUR_KERNEL // 2))

    # 6. Center content with padding
    img = center_content(img, target_size)

    return img


def center_content(img, target_size=IMG_SIZE):
    """
    Center the stroke content within the image.
    Finds the bounding box of non-zero pixels and centers it.
    This provides writer-invariant position normalization.
    
    Args:
        img: PIL Image (grayscale)
        target_size: Output size
    
    Returns:
        PIL Image centered and padded
    """
    arr = np.array(img)

    # Find bounding box of content
    rows = np.any(arr > 20, axis=1)
    cols = np.any(arr > 20, axis=0)

    if not np.any(rows) or not np.any(cols):
        # Empty image
        return Image.new('L', (target_size, target_size), 0)

    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    # Crop to content
    content = arr[rmin:rmax + 1, cmin:cmax + 1]

    # Calculate scaling to fit in target with margin
    margin = int(target_size * 0.1)
    available = target_size - 2 * margin

    h, w = content.shape
    if h == 0 or w == 0:
        return Image.new('L', (target_size, target_size), 0)

    # Scale preserving aspect ratio
    scale = min(available / w, available / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    content_img = Image.fromarray(content).resize((new_w, new_h), Image.BILINEAR)

    # Place centered on black canvas
    result = Image.new('L', (target_size, target_size), 0)
    x_offset = (target_size - new_w) // 2
    y_offset = (target_size - new_h) // 2
    result.paste(content_img, (x_offset, y_offset))

    return result


def skeletonize_image(img):
    """
    Reduce strokes to 1-pixel-wide skeleton.
    Preserves structure while removing appearance bias (thickness, style).
    
    This is key for fair comparison between different writers
    and between scanned vs digital input.
    
    Args:
        img: PIL Image (grayscale, white-on-black)
    
    Returns:
        PIL Image with skeletonized strokes
    """
    try:
        from skimage.morphology import skeletonize
    except ImportError:
        print("[WARNING] scikit-image not installed, skipping skeletonization")
        return img

    arr = np.array(img)
    binary = arr > 127

    if not np.any(binary):
        return img

    skeleton = skeletonize(binary)
    # Thicken skeleton slightly for visibility (2px)
    from scipy.ndimage import binary_dilation
    kernel = np.ones((2, 2), dtype=bool)
    thickened = binary_dilation(skeleton, structure=kernel, iterations=1)
    result = (thickened * 255).astype(np.uint8)

    return Image.fromarray(result)


def preprocess_for_inference(path_points, apply_skeleton=False):
    """
    Complete pipeline: air-writing strokes → CNN-ready tensor.
    
    IMPORTANT: stroke_to_image() already produces clean white-on-black images
    matching the training data format. We apply ONLY the same transforms used
    during training evaluation (Resize → ToTensor → Normalize) to avoid
    domain mismatch caused by preprocess_image()'s binarization/dilation.
    
    Args:
        path_points: [{x, y, t}, ...] from frontend
        apply_skeleton: Whether to skeletonize (usually False for real-time)
    
    Returns:
        torch.Tensor of shape (1, 1, IMG_SIZE, IMG_SIZE)
    """
    import torch
    from ml_pipeline.dataset import get_inference_transform

    # 1. Convert strokes to image (white strokes on black background)
    img = stroke_to_image(path_points)

    # 2. Optional skeletonization
    if apply_skeleton and SKELETON_ENABLED:
        img = skeletonize_image(img)

    # 3. Apply inference transforms — SAME as training eval transforms
    #    (Resize → ToTensor → Normalize) to match training domain exactly
    transform = get_inference_transform()
    tensor = transform(img)

    # 4. Add batch dimension
    return tensor.unsqueeze(0)


def preprocess_for_comparison(path_points):
    """
    Create both raw and skeleton versions for structural comparison.
    Used by the scoring module.
    
    Returns:
        (raw_image, skeleton_image) — both PIL Images
    """
    img = stroke_to_image(path_points)
    img = preprocess_image(img)

    skeleton = skeletonize_image(img) if SKELETON_ENABLED else img

    return img, skeleton
