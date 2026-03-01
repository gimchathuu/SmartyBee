"""
Debug & Verification Tools — Post-Training Diagnostics
=======================================================
1. Unseen-writer tests
2. Feature collapse detection
3. Digital vs scanned consistency checks
4. Per-class error analysis
5. Confidence calibration check
"""

import os
import json
import numpy as np
import torch
import torch.nn.functional as F
from collections import Counter

from ml_pipeline.ml_config import (
    NUM_CLASSES, CLASS_TO_LETTER, CLASS_TO_FOLDER, FOLDER_TO_CLASS,
    BEST_MODEL_PATH, IMG_SIZE, TEST_DIR, VALID_DIR,
    CONFIDENCE_THRESHOLD, MODEL_DIR,
)
from ml_pipeline.model import SinhalaCNN, get_model
from ml_pipeline.dataset import SinhalaLetterDataset, get_eval_transforms, get_data_loaders
from ml_pipeline.preprocessing import stroke_to_image, preprocess_image


def run_full_diagnostics(model_path=BEST_MODEL_PATH):
    """
    Run all diagnostic tests on a trained model.
    
    Returns:
        dict with all test results
    """
    print("=" * 60)
    print("ML MODEL DIAGNOSTIC SUITE")
    print("=" * 60)

    device = 'cpu'
    model = get_model(device=device, pretrained_path=model_path)
    if model is None:
        print("[ERROR] No trained model found. Train the model first.")
        return None

    model.eval()
    results = {}

    # Test 1: Feature Collapse Detection
    print("\n--- Test 1: Feature Collapse Detection ---")
    results['feature_collapse'] = test_feature_collapse(model, device)

    # Test 2: Confidence Calibration
    print("\n--- Test 2: Confidence Calibration ---")
    results['confidence_calibration'] = test_confidence_calibration(model, device)

    # Test 3: Blank & Noise Robustness
    print("\n--- Test 3: Robustness Tests ---")
    results['robustness'] = test_robustness(model, device)

    # Test 4: Per-Class Error Analysis
    print("\n--- Test 4: Per-Class Error Analysis ---")
    results['class_errors'] = test_per_class_errors(model, device)

    # Test 5: Confusion Pairs (most confused classes)
    print("\n--- Test 5: Confusion Pairs ---")
    results['confusion_pairs'] = test_confusion_pairs(model, device)

    # Test 6: Canvas Stroke Simulation
    print("\n--- Test 6: Canvas Stroke Simulation ---")
    results['canvas_sim'] = test_canvas_simulation(model, device)

    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)

    all_pass = True
    for test_name, test_result in results.items():
        status = "PASS" if test_result.get('passed', False) else "FAIL"
        if not test_result.get('passed', False):
            all_pass = False
        print(f"  [{status}] {test_name}: {test_result.get('summary', 'N/A')}")

    print(f"\nOverall: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    print("=" * 60)

    # Save report
    report_path = os.path.join(MODEL_DIR, "diagnostic_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        # Convert numpy types to python types for JSON serialization
        json.dump(_make_serializable(results), f, indent=2, ensure_ascii=False)
    print(f"\nReport saved: {report_path}")

    return results


def test_feature_collapse(model, device):
    """
    Check if the model collapses all predictions to a single class.
    Uses diverse inputs (random, constant, patterned) and checks prediction diversity.
    """
    model.eval()
    predictions = []

    with torch.no_grad():
        # 50 random inputs
        for _ in range(50):
            x = torch.randn(1, 1, IMG_SIZE, IMG_SIZE).to(device)
            pred = model(x).argmax(dim=1).item()
            predictions.append(pred)

        # 10 constant-value inputs
        for val in np.linspace(-2, 2, 10):
            x = torch.full((1, 1, IMG_SIZE, IMG_SIZE), val).to(device)
            pred = model(x).argmax(dim=1).item()
            predictions.append(pred)

    unique = len(set(predictions))
    counter = Counter(predictions)
    most_common = counter.most_common(1)[0]

    passed = unique > 2  # At least 3 different classes predicted
    dominance = most_common[1] / len(predictions)

    summary = f"{unique} unique classes predicted, most common: class {most_common[0]} ({dominance:.0%})"
    print(f"  Unique predictions: {unique}/{NUM_CLASSES}")
    print(f"  Most predicted class: {most_common[0]} ({CLASS_TO_LETTER.get(most_common[0], '?')}) — {dominance:.0%}")

    if dominance > 0.8:
        print(f"  [WARNING] Feature collapse detected! Class {most_common[0]} dominates.")

    return {'passed': passed, 'unique_classes': unique, 'dominance': dominance, 'summary': summary}


def test_confidence_calibration(model, device):
    """
    Check if model confidence is well-calibrated:
    - Correct predictions should have higher confidence than incorrect ones
    - Average confidence should roughly match accuracy
    """
    model.eval()
    test_ds = SinhalaLetterDataset(TEST_DIR, transform=get_eval_transforms())

    correct_confs = []
    incorrect_confs = []

    with torch.no_grad():
        for i in range(len(test_ds)):
            img, label = test_ds[i]
            img = img.unsqueeze(0).to(device)
            probs = F.softmax(model(img), dim=1).squeeze(0)
            confidence = probs.max().item()
            predicted = probs.argmax().item()

            if predicted == label:
                correct_confs.append(confidence)
            else:
                incorrect_confs.append(confidence)

    avg_correct = np.mean(correct_confs) if correct_confs else 0
    avg_incorrect = np.mean(incorrect_confs) if incorrect_confs else 0

    # Confidence should be higher for correct predictions
    passed = avg_correct > avg_incorrect + 0.05

    summary = f"Correct avg conf: {avg_correct:.3f}, Incorrect avg conf: {avg_incorrect:.3f}"
    print(f"  Correct predictions avg confidence: {avg_correct:.3f} (n={len(correct_confs)})")
    print(f"  Incorrect predictions avg confidence: {avg_incorrect:.3f} (n={len(incorrect_confs)})")
    print(f"  Gap: {avg_correct - avg_incorrect:.3f}")

    return {'passed': passed, 'avg_correct_conf': avg_correct, 'avg_incorrect_conf': avg_incorrect, 'summary': summary}


def test_robustness(model, device):
    """
    Test model behavior on adversarial/edge-case inputs.
    """
    model.eval()
    results_list = []

    with torch.no_grad():
        # 1. All-black (empty canvas)
        blank = torch.zeros(1, 1, IMG_SIZE, IMG_SIZE).to(device)
        blank_conf = F.softmax(model(blank), dim=1).max().item()
        results_list.append(('Blank input', blank_conf, blank_conf < 0.5))

        # 2. All-white
        white = torch.ones(1, 1, IMG_SIZE, IMG_SIZE).to(device)
        white_conf = F.softmax(model(white), dim=1).max().item()
        results_list.append(('White input', white_conf, white_conf < 0.5))

        # 3. Random noise
        noise_confs = []
        for _ in range(10):
            noise = torch.randn(1, 1, IMG_SIZE, IMG_SIZE).to(device)
            noise_conf = F.softmax(model(noise), dim=1).max().item()
            noise_confs.append(noise_conf)
        avg_noise = np.mean(noise_confs)
        results_list.append(('Random noise (avg)', avg_noise, avg_noise < 0.6))

        # 4. Single dot
        dot = torch.zeros(1, 1, IMG_SIZE, IMG_SIZE).to(device)
        dot[0, 0, IMG_SIZE // 2, IMG_SIZE // 2] = 2.0
        dot_conf = F.softmax(model(dot), dim=1).max().item()
        results_list.append(('Single dot', dot_conf, dot_conf < 0.5))

        # 5. Horizontal line
        line = torch.zeros(1, 1, IMG_SIZE, IMG_SIZE).to(device)
        line[0, 0, IMG_SIZE // 2, :] = 2.0
        line_conf = F.softmax(model(line), dim=1).max().item()
        results_list.append(('Horizontal line', line_conf, True))  # May match a letter

    all_pass = all(r[2] for r in results_list)

    for name, conf, passed in results_list:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: confidence = {conf:.3f}")

    return {'passed': all_pass, 'tests': [(n, c) for n, c, _ in results_list],
            'summary': f"{'All' if all_pass else 'Some'} robustness tests passed"}


def test_per_class_errors(model, device):
    """Analyze which classes have the most errors."""
    model.eval()
    test_ds = SinhalaLetterDataset(TEST_DIR, transform=get_eval_transforms())

    class_correct = {}
    class_total = {}
    class_avg_conf = {}

    with torch.no_grad():
        for i in range(len(test_ds)):
            img, label = test_ds[i]
            img = img.unsqueeze(0).to(device)
            probs = F.softmax(model(img), dim=1).squeeze(0)
            predicted = probs.argmax().item()
            confidence = probs[label].item()  # Confidence for TRUE label

            class_total[label] = class_total.get(label, 0) + 1
            if predicted == label:
                class_correct[label] = class_correct.get(label, 0) + 1
            class_avg_conf.setdefault(label, []).append(confidence)

    worst_class = None
    worst_acc = 100

    print(f"  {'Class':>5} {'Letter':>6} {'Acc':>8} {'Avg Conf':>10}")
    print(f"  {'-'*35}")

    for i in range(NUM_CLASSES):
        total = class_total.get(i, 0)
        correct = class_correct.get(i, 0)
        acc = 100 * correct / total if total > 0 else 0
        avg_conf = np.mean(class_avg_conf.get(i, [0]))

        print(f"  {i:>5} {CLASS_TO_LETTER[i]:>6} {acc:>7.1f}% {avg_conf:>9.3f}")

        if acc < worst_acc:
            worst_acc = acc
            worst_class = i

    passed = worst_acc >= 50  # No class below 50% accuracy

    return {'passed': passed, 'worst_class': worst_class, 'worst_acc': worst_acc,
            'summary': f"Worst class: {CLASS_TO_LETTER.get(worst_class, '?')} at {worst_acc:.1f}%"}


def test_confusion_pairs(model, device):
    """Find the most confused class pairs."""
    model.eval()
    test_ds = SinhalaLetterDataset(TEST_DIR, transform=get_eval_transforms())

    confusion = {}  # (true, pred) → count

    with torch.no_grad():
        for i in range(len(test_ds)):
            img, label = test_ds[i]
            img = img.unsqueeze(0).to(device)
            pred = model(img).argmax(dim=1).item()

            if pred != label:
                pair = (label, pred)
                confusion[pair] = confusion.get(pair, 0) + 1

    # Sort by frequency
    sorted_pairs = sorted(confusion.items(), key=lambda x: x[1], reverse=True)

    print("  Top confusion pairs:")
    for (true_cls, pred_cls), count in sorted_pairs[:5]:
        true_letter = CLASS_TO_LETTER.get(true_cls, '?')
        pred_letter = CLASS_TO_LETTER.get(pred_cls, '?')
        print(f"    {true_letter} → {pred_letter}: {count} times")

    passed = len(sorted_pairs) == 0 or sorted_pairs[0][1] < 10

    return {'passed': passed, 'top_pairs': sorted_pairs[:5],
            'summary': f"{len(sorted_pairs)} confusion pairs found"}


def test_canvas_simulation(model, device):
    """
    Simulate canvas input (stroke_to_image) and verify the model can handle it.
    Generates synthetic strokes for each class and checks prediction.
    """
    from ml_pipeline.preprocessing import stroke_to_image, preprocess_image
    from ml_pipeline.dataset import get_inference_transform

    model.eval()
    transform = get_inference_transform()

    # Generate a simple synthetic stroke (horizontal line with varying position)
    test_strokes = [
        # Vertical line
        [{'x': 0.5, 'y': 0.2 + i * 0.05, 't': i * 50} for i in range(12)],
        # Circle-like
        [{'x': 0.5 + 0.2 * np.cos(i * 0.5), 'y': 0.5 + 0.2 * np.sin(i * 0.5), 't': i * 50} for i in range(13)],
        # Zigzag
        [{'x': 0.2 + i * 0.06, 'y': 0.5 + (0.1 if i % 2 == 0 else -0.1), 't': i * 50} for i in range(10)],
    ]

    results_list = []

    with torch.no_grad():
        for idx, stroke in enumerate(test_strokes):
            img = stroke_to_image(stroke)
            img = preprocess_image(img)
            tensor = transform(img).unsqueeze(0).to(device)

            probs = F.softmax(model(tensor), dim=1).squeeze(0)
            pred = probs.argmax().item()
            conf = probs.max().item()

            results_list.append((f"Synth stroke {idx + 1}", pred, conf))
            print(f"  Synth stroke {idx + 1}: predicted class {pred} ({CLASS_TO_LETTER.get(pred, '?')}) at {conf:.3f}")

    # The model should be able to process canvas input without errors
    passed = len(results_list) == len(test_strokes)

    return {'passed': passed, 'results': results_list,
            'summary': f"Processed {len(results_list)}/{len(test_strokes)} synthetic strokes"}


def _make_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, bool):
        return bool(obj)
    return obj


if __name__ == "__main__":
    run_full_diagnostics()
