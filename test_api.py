"""End-to-end API test for the geometric evaluation engine."""
import urllib.request
import json
import math

BASE = 'http://127.0.0.1:5000'

def post_json(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, body, {'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

def get_json(url):
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


# ── TEST 1: ML letter (LetterID 15 = ක) ──
print("=" * 60)
print("TEST 1: Submit attempt — ML letter (LetterID 15 = ක)")
print("=" * 60)

stroke_ka = []
# Loop part (matches ක template)
for i in range(20):
    angle = math.radians(0 + 360 * i / 20)
    stroke_ka.append({"x": 0.45 + 0.14 * math.cos(angle), "y": 0.25 + 0.14 * math.sin(angle)})
# Downstroke
for i in range(10):
    t = i / 9
    stroke_ka.append({"x": 0.45, "y": 0.39 + 0.26 * t})
# Hook
for i in range(5):
    t = i / 4
    stroke_ka.append({"x": 0.45 + 0.1 * t, "y": 0.65 + 0.13 * t})

data = post_json(BASE + '/api/submit_attempt', {"path": stroke_ka, "letter_id": 15})
print("Score:", data.get("score"))
print("Stars:", data.get("stars"))
print("Method:", data.get("scoring_method"))
print("Errors:", data.get("errors"))
print("Breakdown:", json.dumps(data.get("breakdown"), indent=2))
print("Feedback:", data.get("feedback_text"))
print("Blocked:", data.get("blocked", False))
print()

# ── TEST 2: Non-ML letter (LetterID 3 = අ) ──
print("=" * 60)
print("TEST 2: Submit attempt — Non-ML letter (LetterID 3 = අ)")
print("=" * 60)

stroke_a = []
for i in range(20):
    angle = math.radians(180 + (-360) * i / 20)
    stroke_a.append({"x": 0.35 + 0.12 * math.cos(angle), "y": 0.22 + 0.12 * math.sin(angle)})
for i in range(15):
    t = i / 14
    stroke_a.append({"x": 0.35 + 0.15 * t, "y": 0.34 + 0.48 * t})

data2 = post_json(BASE + '/api/submit_attempt', {"path": stroke_a, "letter_id": 3})
print("Score:", data2.get("score"))
print("Stars:", data2.get("stars"))
print("Method:", data2.get("scoring_method"))
print("Errors:", data2.get("errors"))
print("Breakdown:", json.dumps(data2.get("breakdown"), indent=2))
print("Feedback:", data2.get("feedback_text"))
print()

# ── TEST 3: Live score ──
print("=" * 60)
print("TEST 3: Live score (LetterID 20 = ත)")
print("=" * 60)

stroke_tha = []
for i in range(25):
    t = i / 24
    stroke_tha.append({"x": 0.25 + 0.4 * t, "y": 0.3 - 0.1 * t + 0.52 * t * t})

data3 = post_json(BASE + '/api/live-score', {"path": stroke_tha, "letter_id": 20})
print("Score:", data3.get("score"))
print("Quality:", data3.get("quality"))
print("Coverage:", data3.get("coverage"))
print()

# ── TEST 4: GET /evaluate-letter ──
print("=" * 60)
print("TEST 4: GET /evaluate-letter?letter_id=3")
print("=" * 60)
try:
    data4 = get_json(BASE + '/evaluate-letter?letter_id=3')
    print("Success:", data4.get("success"))
    print("Accuracy:", data4.get("accuracy"))
    print("Stars:", data4.get("stars"))
    print("Error Score:", data4.get("error_score"))
    print("Errors:", data4.get("errors"))
    print("Breakdown:", json.dumps(data4.get("metric_breakdown"), indent=2))
    print("Feedback:", data4.get("feedback_text"))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}")
print()

# ── TEST 5: Non-ML letter (LetterID 21 = ද) — geometric only ──
print("=" * 60)
print("TEST 5: Submit — LetterID 21 = ද (geometric only, no CNN)")
print("=" * 60)

stroke_da = []
# Approximate ද shape
for i in range(15):
    t = i / 14
    stroke_da.append({"x": 0.28 + 0.24 * t, "y": 0.28 - 0.10 * t})
for i in range(20):
    t = i / 19
    stroke_da.append({"x": 0.52 + 0.13 * t * (1 - t), "y": 0.18 + 0.32 * t})
for i in range(15):
    t = i / 14
    stroke_da.append({"x": 0.55 - 0.23 * t, "y": 0.50 + 0.32 * t})

data5 = post_json(BASE + '/api/submit_attempt', {"path": stroke_da, "letter_id": 21})
print("Score:", data5.get("score"))
print("Stars:", data5.get("stars"))
print("Method:", data5.get("scoring_method"))
print("Breakdown:", json.dumps(data5.get("breakdown"), indent=2))
print("Feedback:", data5.get("feedback_text"))
print()

# ── TEST 6: Bad attempt (random scribble on LetterID 27 = ර) ──
print("=" * 60)
print("TEST 6: Bad attempt — random scribble on LetterID 27 = ර")
print("=" * 60)

stroke_bad = []
for i in range(30):
    t = i / 29
    stroke_bad.append({"x": 0.1 + 0.8 * t, "y": 0.5 + 0.3 * math.sin(t * 6)})

data6 = post_json(BASE + '/api/submit_attempt', {"path": stroke_bad, "letter_id": 27})
print("Score:", data6.get("score"))
print("Stars:", data6.get("stars"))
print("Errors:", data6.get("errors"))
print("Breakdown:", json.dumps(data6.get("breakdown"), indent=2))
print("Feedback:", data6.get("feedback_text"))
print("Blocked:", data6.get("blocked", False))
if data6.get("blocked"):
    print("Block reason:", data6.get("reason"))
print()

print("=" * 60)
print("ALL TESTS COMPLETE")
print("=" * 60)
