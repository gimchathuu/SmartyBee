"""Direct test of geometric evaluation engine — no API, no CNN."""
from vision_engine import evaluate_stroke
from stroke_templates import get_template_for_char
import random
import json

random.seed(42)

print("Testing geometric scoring directly (bypassing CNN gatekeeper)")
print()

# Test letters from different families
test_chars = ["ක", "ර", "අ", "ත", "ම", "ව", "ද", "ළ", "එ", "ට"]

print("── GOOD attempts (slight noise on template tracing) ──")
for char in test_chars:
    template = get_template_for_char(char)
    # Simulate tracing with slight noise
    user = [{"x": pt["x"] + random.gauss(0, 0.02),
             "y": pt["y"] + random.gauss(0, 0.02)} for pt in template]
    result = evaluate_stroke(user, template)
    bd = result.get("breakdown", {})
    score = result["score"]
    stars = result["stars"]
    cov = bd.get("coverage", 0)
    errors_list = result.get("errors", [])
    print(f"  {char}  Score={score:5.1f}  Stars={stars}  Coverage={cov:5.1f}%  Errors={errors_list}")

print()
print("── POOR attempts (only first half, shifted) ──")
for char in ["ක", "අ", "ම", "ර"]:
    template = get_template_for_char(char)
    half = template[:len(template) // 2]
    user = [{"x": pt["x"] + 0.15, "y": pt["y"] + 0.1} for pt in half]
    result = evaluate_stroke(user, template)
    bd = result.get("breakdown", {})
    score = result["score"]
    stars = result["stars"]
    cov = bd.get("coverage", 0)
    errors_list = result.get("errors", [])
    fb = result.get("feedback_text", "")
    print(f"  {char}  Score={score:5.1f}  Stars={stars}  Coverage={cov:5.1f}%  Errors={errors_list}")
    print(f"       Feedback: {fb}")

print()
print("── WRONG letter (draw අ template on ක target) ──")
template_ka = get_template_for_char("ක")
stroke_a = get_template_for_char("අ")
user = [{"x": pt["x"] + random.gauss(0, 0.01),
         "y": pt["y"] + random.gauss(0, 0.01)} for pt in stroke_a]
result = evaluate_stroke(user, template_ka)
bd = result.get("breakdown", {})
print(f"  WRONG: Score={result['score']:5.1f}  Stars={result['stars']}  Coverage={bd.get('coverage', 0):5.1f}%")
print(f"         Errors={result.get('errors', [])}")
print(f"         Feedback: {result.get('feedback_text', '')}")

print()
print("── Detailed breakdown for ක (good attempt) ──")
template = get_template_for_char("ක")
user = [{"x": pt["x"] + random.gauss(0, 0.015),
         "y": pt["y"] + random.gauss(0, 0.015)} for pt in template]
result = evaluate_stroke(user, template)
print(json.dumps({
    "score": result["score"],
    "stars": result["stars"],
    "error_score": result.get("error_score"),
    "errors": result.get("errors"),
    "metric_breakdown": result.get("breakdown"),
    "feedback_text": result.get("feedback_text"),
}, indent=2))
