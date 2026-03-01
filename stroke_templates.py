"""
Sinhala Letter Reference Stroke Templates
==========================================
Normalized stroke paths for all 32 Sinhala letters in the database.
Each letter is defined as an ordered list of {x, y} points in [0, 1] space
tracing the ideal writing path.

Coordinate system:
  (0, 0) = top-left
  (1, 1) = bottom-right
  Points are ordered in the direction of natural writing.

These templates are used by vision_engine.py for geometric comparison
via DTW, Chamfer, Hausdorff, Procrustes, and Coverage algorithms.
"""

import math

# ── Curve generation helpers ──

def _arc(cx, cy, rx, ry, start_deg, end_deg, n=20):
    """Generate points along an elliptical arc."""
    pts = []
    for i in range(n):
        t = i / max(n - 1, 1)
        angle = math.radians(start_deg + (end_deg - start_deg) * t)
        pts.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    return pts


def _bezier2(p0, p1, p2, n=15):
    """Quadratic Bezier curve through 3 control points."""
    pts = []
    for i in range(n):
        t = i / max(n - 1, 1)
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts


def _bezier3(p0, p1, p2, p3, n=20):
    """Cubic Bezier curve through 4 control points."""
    pts = []
    for i in range(n):
        t = i / max(n - 1, 1)
        x = ((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0]
             + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0])
        y = ((1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1]
             + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1])
        pts.append((x, y))
    return pts


def _line(x1, y1, x2, y2, n=8):
    """Generate points along a straight line segment."""
    pts = []
    for i in range(n):
        t = i / max(n - 1, 1)
        pts.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return pts


def _loop(cx, cy, rx, ry, n=25):
    """Full loop (counterclockwise from top)."""
    return _arc(cx, cy, rx, ry, -90, 270, n)


def _to_dicts(points):
    """Convert (x,y) tuples to [{x, y}, ...] dicts, rounded to 4dp."""
    return [{"x": round(float(p[0]), 4), "y": round(float(p[1]), 4)} for p in points]


# ================================================================
# TEMPLATE DEFINITIONS — All 32 Sinhala letters
# ================================================================
# Each function returns a list of (x, y) tuples tracing the letter.
# The shapes are designed to capture the essential structural features
# of each character for geometric comparison purposes.
# ================================================================

def _template_a():
    """අ — Loop at top-left, descending curve, small tail."""
    pts = []
    # Small loop at top (clockwise)
    pts += _arc(0.35, 0.22, 0.12, 0.12, 180, -180, 25)
    # Descending curve to bottom-right
    pts += _bezier3((0.35, 0.34), (0.42, 0.50), (0.50, 0.65), (0.50, 0.82), 20)
    return pts


def _template_aa():
    """ආ — Like අ with rightward horizontal extension."""
    pts = _template_a()
    # Horizontal tail extending right
    pts += _bezier2((0.50, 0.82), (0.60, 0.82), (0.72, 0.78), 12)
    return pts


def _template_ae():
    """ඇ — Like අ with a bottom curl."""
    pts = _template_a()
    # Bottom curl going left
    pts += _bezier2((0.50, 0.82), (0.45, 0.88), (0.35, 0.85), 12)
    return pts


def _template_aae():
    """ඈ — Like ඇ with horizontal extension."""
    pts = _template_ae()
    pts += _line(0.35, 0.85, 0.20, 0.82, 8)
    return pts


def _template_i():
    """ඉ — Compact upward curve then down-right."""
    pts = []
    pts += _bezier3((0.25, 0.55), (0.30, 0.25), (0.55, 0.20), (0.60, 0.40), 20)
    pts += _bezier2((0.60, 0.40), (0.58, 0.60), (0.50, 0.75), 15)
    return pts


def _template_ii():
    """ඊ — Like ඉ with downward tail."""
    pts = _template_i()
    pts += _bezier2((0.50, 0.75), (0.48, 0.85), (0.42, 0.90), 10)
    return pts


def _template_u():
    """උ — Rounded shape starting from top, curving around bottom."""
    pts = []
    pts += _bezier3((0.50, 0.20), (0.25, 0.25), (0.20, 0.55), (0.30, 0.70), 20)
    pts += _bezier2((0.30, 0.70), (0.45, 0.80), (0.60, 0.65), 15)
    pts += _bezier2((0.60, 0.65), (0.65, 0.50), (0.55, 0.40), 12)
    return pts


def _template_uu():
    """ඌ — Like උ with extension."""
    pts = _template_u()
    pts += _bezier2((0.55, 0.40), (0.50, 0.30), (0.60, 0.22), 10)
    return pts


def _template_e():
    """එ — S-curve shape."""
    pts = []
    pts += _bezier3((0.30, 0.20), (0.55, 0.20), (0.65, 0.40), (0.50, 0.50), 20)
    pts += _bezier3((0.50, 0.50), (0.35, 0.60), (0.30, 0.75), (0.50, 0.82), 20)
    return pts


def _template_ee():
    """ඒ — Like එ with top horizontal bar."""
    pts = []
    # Top bar
    pts += _line(0.20, 0.15, 0.55, 0.15, 8)
    # S-body
    pts += _bezier3((0.55, 0.15), (0.65, 0.30), (0.55, 0.48), (0.45, 0.50), 18)
    pts += _bezier3((0.45, 0.50), (0.35, 0.55), (0.30, 0.70), (0.50, 0.80), 18)
    return pts


def _template_o():
    """ඔ — Round loop with descending tail."""
    pts = []
    # Rounded top part
    pts += _arc(0.45, 0.35, 0.18, 0.18, 180, -90, 18)
    pts += _arc(0.45, 0.35, 0.18, 0.18, -90, 0, 10)
    # Descending part
    pts += _bezier2((0.63, 0.35), (0.60, 0.60), (0.50, 0.80), 15)
    return pts


def _template_oo():
    """ඕ — Like ඔ with top bar."""
    pts = []
    pts += _line(0.25, 0.12, 0.60, 0.12, 8)
    pts += _arc(0.45, 0.38, 0.18, 0.18, -90, 270, 22)
    pts += _bezier2((0.45, 0.56), (0.50, 0.70), (0.48, 0.82), 12)
    return pts


def _template_ka():
    """ක — Loop at top, vertical downstroke, small hook."""
    pts = []
    # Top loop (counterclockwise)
    pts += _arc(0.45, 0.25, 0.14, 0.14, 0, 360, 25)
    # Vertical descent
    pts += _line(0.45, 0.39, 0.45, 0.65, 12)
    # Small bottom hook right
    pts += _bezier2((0.45, 0.65), (0.48, 0.75), (0.55, 0.78), 10)
    return pts


def _template_ga():
    """ග — Loop at top with wider body and left tail."""
    pts = []
    # Top loop
    pts += _arc(0.50, 0.28, 0.16, 0.14, 90, -270, 25)
    # Descending curve going left
    pts += _bezier3((0.50, 0.42), (0.48, 0.55), (0.40, 0.68), (0.35, 0.80), 18)
    return pts


def _template_ta():
    """ට — Compact shape with inner curve, loop top-right."""
    pts = []
    # Start from left
    pts += _bezier2((0.25, 0.35), (0.30, 0.22), (0.50, 0.20), 12)
    # Top loop
    pts += _arc(0.55, 0.30, 0.12, 0.12, -90, 180, 20)
    # Descending stroke
    pts += _bezier2((0.43, 0.30), (0.40, 0.55), (0.45, 0.75), 15)
    # Tail
    pts += _bezier2((0.45, 0.75), (0.50, 0.82), (0.58, 0.80), 8)
    return pts


def _template_da_hard():
    """ඩ — Round body with downward tail."""
    pts = []
    # Main round body
    pts += _arc(0.45, 0.35, 0.17, 0.17, 90, -270, 25)
    # Descending tail
    pts += _bezier2((0.45, 0.52), (0.48, 0.65), (0.42, 0.80), 12)
    return pts


def _template_na_retroflex():
    """ණ — Complex shape with multiple curves."""
    pts = []
    # Top curve
    pts += _bezier3((0.25, 0.30), (0.35, 0.18), (0.55, 0.18), (0.60, 0.30), 18)
    # Middle connection
    pts += _bezier2((0.60, 0.30), (0.55, 0.45), (0.40, 0.50), 12)
    # Bottom curve
    pts += _bezier3((0.40, 0.50), (0.30, 0.58), (0.35, 0.72), (0.50, 0.78), 18)
    return pts


def _template_tha():
    """ත — Curved shape with characteristic loop."""
    pts = []
    # Start with curve from left
    pts += _bezier2((0.25, 0.30), (0.30, 0.20), (0.48, 0.20), 12)
    # Top right curve
    pts += _bezier3((0.48, 0.20), (0.62, 0.22), (0.65, 0.38), (0.55, 0.48), 18)
    # Bottom curve
    pts += _bezier3((0.55, 0.48), (0.42, 0.58), (0.35, 0.70), (0.45, 0.82), 16)
    return pts


def _template_da_soft():
    """ද — Similar to ත with a different ending."""
    pts = []
    pts += _bezier2((0.28, 0.28), (0.35, 0.18), (0.52, 0.18), 12)
    pts += _bezier3((0.52, 0.18), (0.65, 0.20), (0.68, 0.38), (0.55, 0.50), 18)
    pts += _bezier3((0.55, 0.50), (0.45, 0.60), (0.38, 0.72), (0.32, 0.82), 15)
    return pts


def _template_na():
    """න — Curved shape in the ත family."""
    pts = []
    pts += _bezier2((0.30, 0.32), (0.35, 0.20), (0.52, 0.22), 12)
    pts += _bezier3((0.52, 0.22), (0.62, 0.25), (0.60, 0.42), (0.50, 0.50), 16)
    pts += _bezier3((0.50, 0.50), (0.38, 0.58), (0.32, 0.70), (0.40, 0.82), 16)
    pts += _bezier2((0.40, 0.82), (0.46, 0.88), (0.55, 0.85), 8)
    return pts


def _template_pa():
    """ප — Round body with short tail."""
    pts = []
    # Round body (almost a circle)
    pts += _arc(0.45, 0.38, 0.18, 0.20, 90, -270, 28)
    # Short descending tail
    pts += _bezier2((0.45, 0.58), (0.50, 0.70), (0.48, 0.82), 10)
    return pts


def _template_ba():
    """බ — Similar to ප with wider bottom."""
    pts = []
    pts += _arc(0.45, 0.35, 0.17, 0.18, 90, -270, 25)
    pts += _bezier3((0.45, 0.53), (0.42, 0.62), (0.35, 0.72), (0.40, 0.82), 15)
    pts += _bezier2((0.40, 0.82), (0.48, 0.88), (0.58, 0.82), 10)
    return pts


def _template_ma():
    """ම — Double loop / connected curves."""
    pts = []
    # First loop
    pts += _arc(0.32, 0.32, 0.13, 0.13, 90, -270, 22)
    # Connection
    pts += _bezier2((0.32, 0.45), (0.40, 0.48), (0.48, 0.42), 8)
    # Second loop / curve
    pts += _arc(0.55, 0.35, 0.12, 0.12, 180, -180, 20)
    # Tail
    pts += _bezier2((0.55, 0.47), (0.52, 0.65), (0.48, 0.80), 12)
    return pts


def _template_ya():
    """ය — Flowing curve with characteristic shape."""
    pts = []
    pts += _bezier3((0.25, 0.25), (0.35, 0.18), (0.55, 0.18), (0.62, 0.30), 18)
    pts += _bezier3((0.62, 0.30), (0.65, 0.45), (0.55, 0.55), (0.42, 0.55), 15)
    pts += _bezier3((0.42, 0.55), (0.32, 0.55), (0.28, 0.68), (0.38, 0.80), 15)
    return pts


def _template_ra():
    """ර — Small compact loop."""
    pts = []
    # Small top loop
    pts += _arc(0.48, 0.30, 0.10, 0.10, 0, 360, 22)
    # Short tail
    pts += _bezier2((0.48, 0.40), (0.50, 0.55), (0.48, 0.68), 12)
    return pts


def _template_cha():
    """ච — Complex curved shape."""
    pts = []
    pts += _bezier3((0.28, 0.25), (0.40, 0.15), (0.58, 0.18), (0.62, 0.32), 18)
    pts += _bezier2((0.62, 0.32), (0.60, 0.48), (0.48, 0.52), 12)
    pts += _bezier3((0.48, 0.52), (0.35, 0.55), (0.30, 0.68), (0.38, 0.78), 16)
    pts += _bezier2((0.38, 0.78), (0.45, 0.85), (0.55, 0.80), 10)
    return pts


def _template_ja():
    """ජ — Similar to ච with different ending."""
    pts = []
    pts += _bezier3((0.30, 0.22), (0.42, 0.14), (0.58, 0.16), (0.62, 0.30), 18)
    pts += _bezier3((0.62, 0.30), (0.65, 0.45), (0.52, 0.55), (0.42, 0.52), 15)
    pts += _bezier3((0.42, 0.52), (0.30, 0.50), (0.25, 0.65), (0.35, 0.80), 15)
    return pts


def _template_la():
    """ල — Long flowing curve."""
    pts = []
    pts += _bezier3((0.30, 0.18), (0.50, 0.15), (0.60, 0.28), (0.55, 0.42), 18)
    pts += _bezier3((0.55, 0.42), (0.48, 0.55), (0.38, 0.62), (0.35, 0.75), 16)
    pts += _bezier2((0.35, 0.75), (0.38, 0.85), (0.48, 0.88), 10)
    return pts


def _template_va():
    """ව — Compact loop shape."""
    pts = []
    pts += _bezier2((0.30, 0.30), (0.35, 0.18), (0.52, 0.20), 12)
    pts += _arc(0.52, 0.35, 0.14, 0.15, -90, 180, 20)
    pts += _bezier2((0.38, 0.35), (0.35, 0.55), (0.42, 0.72), 14)
    pts += _bezier2((0.42, 0.72), (0.48, 0.82), (0.58, 0.78), 8)
    return pts


def _template_sa():
    """ස — S-like curve."""
    pts = []
    pts += _bezier3((0.30, 0.20), (0.55, 0.15), (0.62, 0.30), (0.50, 0.45), 20)
    pts += _bezier3((0.50, 0.45), (0.38, 0.55), (0.32, 0.68), (0.45, 0.80), 20)
    pts += _bezier2((0.45, 0.80), (0.52, 0.85), (0.60, 0.80), 8)
    return pts


def _template_ha():
    """හ — Multi-curve shape with loops."""
    pts = []
    # First curve/loop
    pts += _arc(0.35, 0.28, 0.13, 0.12, 90, -270, 22)
    # Connection
    pts += _bezier2((0.35, 0.40), (0.42, 0.48), (0.52, 0.42), 10)
    # Second curve
    pts += _bezier3((0.52, 0.42), (0.62, 0.38), (0.65, 0.52), (0.55, 0.60), 16)
    # Tail down
    pts += _bezier2((0.55, 0.60), (0.50, 0.72), (0.45, 0.82), 10)
    return pts


def _template_la_alt():
    """ළ — Like ල variant with different curve."""
    pts = []
    pts += _bezier3((0.28, 0.20), (0.48, 0.14), (0.62, 0.25), (0.58, 0.42), 18)
    pts += _bezier3((0.58, 0.42), (0.52, 0.55), (0.40, 0.60), (0.32, 0.55), 15)
    pts += _bezier3((0.32, 0.55), (0.25, 0.50), (0.22, 0.68), (0.35, 0.82), 15)
    pts += _bezier2((0.35, 0.82), (0.42, 0.88), (0.52, 0.84), 8)
    return pts


# ================================================================
# MASTER TEMPLATE MAP — SinhalaChar → {x,y} point list
# ================================================================

def get_all_templates():
    """
    Return a dict mapping each Sinhala character to its reference stroke path.
    Each path is a list of {x, y} dicts in [0, 1] coordinate space.
    """
    return {
        # Vowels (LetterID 3-14)
        "අ": _to_dicts(_template_a()),
        "ආ": _to_dicts(_template_aa()),
        "ඇ": _to_dicts(_template_ae()),
        "ඈ": _to_dicts(_template_aae()),
        "ඉ": _to_dicts(_template_i()),
        "ඊ": _to_dicts(_template_ii()),
        "උ": _to_dicts(_template_u()),
        "ඌ": _to_dicts(_template_uu()),
        "එ": _to_dicts(_template_e()),
        "ඒ": _to_dicts(_template_ee()),
        "ඔ": _to_dicts(_template_o()),
        "ඕ": _to_dicts(_template_oo()),

        # Consonants (LetterID 15-34)
        "ක": _to_dicts(_template_ka()),
        "ග": _to_dicts(_template_ga()),
        "ට": _to_dicts(_template_ta()),
        "ඩ": _to_dicts(_template_da_hard()),
        "ණ": _to_dicts(_template_na_retroflex()),
        "ත": _to_dicts(_template_tha()),
        "ද": _to_dicts(_template_da_soft()),
        "න": _to_dicts(_template_na()),
        "ප": _to_dicts(_template_pa()),
        "බ": _to_dicts(_template_ba()),
        "ම": _to_dicts(_template_ma()),
        "ය": _to_dicts(_template_ya()),
        "ර": _to_dicts(_template_ra()),
        "ච": _to_dicts(_template_cha()),
        "ජ": _to_dicts(_template_ja()),
        "ල": _to_dicts(_template_la()),
        "ව": _to_dicts(_template_va()),
        "ස": _to_dicts(_template_sa()),
        "හ": _to_dicts(_template_ha()),
        "ළ": _to_dicts(_template_la_alt()),
    }


def get_template_for_char(char):
    """Get reference stroke path for a given Sinhala character."""
    templates = get_all_templates()
    return templates.get(char, [])


# ── Quick verification ──
if __name__ == "__main__":
    templates = get_all_templates()
    print(f"Generated templates for {len(templates)} characters:\n")
    for char, pts in templates.items():
        print(f"  {char}  →  {len(pts)} points  |  start=({pts[0]['x']:.2f}, {pts[0]['y']:.2f})  end=({pts[-1]['x']:.2f}, {pts[-1]['y']:.2f})")
    print(f"\nAll templates generated successfully.")
