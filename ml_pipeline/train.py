"""
Training Pipeline — Complete Training Loop with Writer-Holdout Strategy
========================================================================
Features:
1. Writer-holdout via predefined train/valid/test splits
2. Learning rate scheduling (cosine annealing)
3. Early stopping with patience
4. Per-class accuracy tracking
5. Confusion matrix generation
6. Sanity tests (blank input, noise input)
7. Model checkpointing (saves best validation accuracy)
8. Training log persistence
"""

import os
import json
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

from ml_pipeline.ml_config import (
    NUM_CLASSES, CLASS_TO_LETTER, FOLDER_IDS,
    BATCH_SIZE, LEARNING_RATE, WEIGHT_DECAY,
    NUM_EPOCHS, EARLY_STOP_PATIENCE,
    MODEL_DIR, BEST_MODEL_PATH, TRAINING_LOG_PATH,
    IMG_SIZE,
)
from ml_pipeline.dataset import get_data_loaders, validate_dataset
from ml_pipeline.model import SinhalaCNN, count_parameters, get_model


def train_model(
    epochs=NUM_EPOCHS,
    batch_size=BATCH_SIZE,
    lr=LEARNING_RATE,
    weight_decay=WEIGHT_DECAY,
    patience=EARLY_STOP_PATIENCE,
    device=None,
    validate_first=True,
):
    """
    Full training pipeline.
    
    Args:
        epochs: Maximum training epochs
        batch_size: Batch size
        lr: Initial learning rate
        weight_decay: L2 regularization strength
        patience: Early stopping patience
        device: 'cpu' or 'cuda' (auto-detected if None)
        validate_first: Run dataset validation before training
    
    Returns:
        dict with training history and final metrics
    """
    # Auto-detect device
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"[Train] Using device: {device}")

    # Ensure model directory exists
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Step 1: Validate dataset
    if validate_first:
        print("\n[Step 1] Validating dataset...")
        if not validate_dataset():
            print("[ABORT] Dataset validation failed. Fix issues before training.")
            return None

    # Step 2: Load data
    print("\n[Step 2] Loading data...")
    train_loader, valid_loader, test_loader = get_data_loaders(
        batch_size=batch_size, num_workers=0
    )
    print(f"  Train batches: {len(train_loader)}")
    print(f"  Valid batches: {len(valid_loader)}")
    print(f"  Test batches:  {len(test_loader)}")

    # Step 3: Create model
    print("\n[Step 3] Creating model...")
    model = SinhalaCNN().to(device)
    count_parameters(model)

    # Step 4: Sanity tests BEFORE training
    print("\n[Step 4] Running sanity tests...")
    run_sanity_tests(model, device)

    # Step 5: Setup training
    print("\n[Step 5] Setting up training...")
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr * 0.01)

    # Training state
    best_val_acc = 0.0
    best_epoch = 0
    epochs_without_improvement = 0
    history = {
        'train_loss': [], 'train_acc': [],
        'val_loss': [], 'val_acc': [],
        'lr': [], 'epoch_times': [],
    }

    # Step 6: Training loop
    print("\n[Step 6] Starting training...")
    print(f"{'Epoch':>5} | {'Train Loss':>10} | {'Train Acc':>9} | {'Val Loss':>8} | {'Val Acc':>7} | {'LR':>10} | {'Time':>6}")
    print("-" * 75)

    for epoch in range(1, epochs + 1):
        epoch_start = time.time()

        # Train one epoch
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)

        # Validate
        val_loss, val_acc = evaluate(model, valid_loader, criterion, device)

        # Step scheduler
        scheduler.step()
        current_lr = scheduler.get_last_lr()[0]

        epoch_time = time.time() - epoch_start

        # Record history
        history['train_loss'].append(train_loss)
        history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        history['lr'].append(current_lr)
        history['epoch_times'].append(epoch_time)

        # Print progress
        print(f"{epoch:>5} | {train_loss:>10.4f} | {train_acc:>8.2f}% | {val_loss:>8.4f} | {val_acc:>6.2f}% | {current_lr:>10.6f} | {epoch_time:>5.1f}s")

        # Check for improvement
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            epochs_without_improvement = 0

        # Save best model (state_dict + temperature placeholder)
            torch.save({
                'model_state_dict': model.state_dict(),
                'temperature': 1.0,  # will be calibrated post-training
            }, BEST_MODEL_PATH)
            print(f"  → Saved best model (val_acc={val_acc:.2f}%)")
        else:
            epochs_without_improvement += 1

        # Early stopping
        if epochs_without_improvement >= patience:
            print(f"\n[Early Stop] No improvement for {patience} epochs. Stopping.")
            break

    # Step 7: Final evaluation on test set
    print(f"\n[Step 7] Final evaluation (best model from epoch {best_epoch})...")
    checkpoint = torch.load(BEST_MODEL_PATH, map_location=device, weights_only=False)
    model = SinhalaCNN().to(device)
    if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'])
    else:
        model.load_state_dict(checkpoint)
    model.eval()

    test_loss, test_acc = evaluate(model, test_loader, criterion, device)
    print(f"  Test Loss: {test_loss:.4f}")
    print(f"  Test Accuracy: {test_acc:.2f}%")

    # Per-class accuracy
    class_acc = evaluate_per_class(model, test_loader, device)

    # Confusion matrix
    cm = compute_confusion_matrix(model, test_loader, device)

    # Step 8: Save training log
    log = {
        'version': '1.0',
        'best_epoch': best_epoch,
        'best_val_acc': best_val_acc,
        'test_acc': test_acc,
        'test_loss': test_loss,
        'class_accuracies': {CLASS_TO_LETTER[i]: acc for i, acc in class_acc.items()},
        'confusion_matrix': cm.tolist(),
        'history': history,
        'config': {
            'epochs': epochs,
            'batch_size': batch_size,
            'lr': lr,
            'weight_decay': weight_decay,
            'img_size': IMG_SIZE,
            'num_classes': NUM_CLASSES,
        },
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    with open(TRAINING_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print(f"\n[Step 8] Training log saved to {TRAINING_LOG_PATH}")

    # Step 9: Post-training sanity
    print("\n[Step 9] Post-training sanity tests...")
    run_sanity_tests(model, device, trained=True)

    print("\n" + "=" * 60)
    print(f"TRAINING COMPLETE")
    print(f"  Best validation accuracy: {best_val_acc:.2f}% (epoch {best_epoch})")
    print(f"  Test accuracy: {test_acc:.2f}%")
    print(f"  Model saved: {BEST_MODEL_PATH}")
    print("=" * 60)

    return log


def train_one_epoch(model, loader, criterion, optimizer, device):
    """Train for one epoch."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for batch_idx, (images, labels) in enumerate(loader):
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()

        # Gradient clipping (prevents exploding gradients)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)

        optimizer.step()

        running_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    avg_loss = running_loss / total if total > 0 else 0
    accuracy = 100.0 * correct / total if total > 0 else 0
    return avg_loss, accuracy


def evaluate(model, loader, criterion, device):
    """Evaluate model on a DataLoader."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            loss = criterion(outputs, labels)

            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

    avg_loss = running_loss / total if total > 0 else 0
    accuracy = 100.0 * correct / total if total > 0 else 0
    return avg_loss, accuracy


def evaluate_per_class(model, loader, device):
    """Compute per-class accuracy."""
    model.eval()
    class_correct = {}
    class_total = {}

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            _, predicted = outputs.max(1)

            for lab, pred in zip(labels, predicted):
                lab = lab.item()
                class_total[lab] = class_total.get(lab, 0) + 1
                if lab == pred.item():
                    class_correct[lab] = class_correct.get(lab, 0) + 1

    accs = {}
    print("\n  Per-class accuracy:")
    for i in range(NUM_CLASSES):
        total = class_total.get(i, 0)
        correct = class_correct.get(i, 0)
        acc = 100.0 * correct / total if total > 0 else 0.0
        accs[i] = acc
        letter = CLASS_TO_LETTER[i]
        print(f"    Class {i:2d} ({letter}): {correct}/{total} = {acc:.1f}%")

    return accs


def compute_confusion_matrix(model, loader, device):
    """Compute NxN confusion matrix."""
    model.eval()
    cm = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=int)

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            _, predicted = outputs.max(1)

            for lab, pred in zip(labels.numpy(), predicted.cpu().numpy()):
                cm[lab][pred] += 1

    return cm


def run_sanity_tests(model, device, trained=False):
    """
    Sanity tests to catch common training failures.
    
    Tests:
    1. Blank input → should NOT predict any class with high confidence
    2. Random noise → should have low confidence
    3. Output sums to 1 (valid probability distribution)
    4. No single class dominance (feature collapse detection)
    """
    import torch.nn.functional as F

    model.eval()
    results = []

    with torch.no_grad():
        # Test 1: Blank (all zeros) input
        blank = torch.zeros(1, 1, IMG_SIZE, IMG_SIZE).to(device)
        blank_out = F.softmax(model(blank), dim=1)
        max_conf = blank_out.max().item()
        results.append(("Blank input max confidence", max_conf, max_conf < 0.5 if trained else True))

        # Test 2: Random noise input
        noise = torch.randn(1, 1, IMG_SIZE, IMG_SIZE).to(device)
        noise_out = F.softmax(model(noise), dim=1)
        noise_conf = noise_out.max().item()
        results.append(("Noise input max confidence", noise_conf, noise_conf < 0.7 if trained else True))

        # Test 3: Probability sums to 1
        prob_sum = blank_out.sum().item()
        results.append(("Probability sum", prob_sum, abs(prob_sum - 1.0) < 0.01))

        # Test 4: Feature collapse — check if all predictions go to same class
        if trained:
            # Generate 10 different random inputs
            random_inputs = torch.randn(10, 1, IMG_SIZE, IMG_SIZE).to(device)
            random_preds = model(random_inputs).argmax(dim=1)
            unique_preds = len(random_preds.unique())
            results.append(("Unique predictions from 10 random", unique_preds, unique_preds > 1))

    all_pass = True
    for name, value, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}: {value:.4f}" if isinstance(value, float) else f"  [{status}] {name}: {value}")

    if not all_pass:
        print("  [WARNING] Some sanity tests failed!")

    return all_pass


def calibrate_temperature(model, valid_loader, device, lr=0.01, max_iter=50):
    """
    Post-training temperature scaling (Guo et al., 2017).
    Learns a single scalar T so that softmax(logits / T) is better calibrated.
    
    Args:
        model: Trained model (eval mode)
        valid_loader: Validation DataLoader
        device: torch device
        lr: Learning rate for temperature optimisation
        max_iter: Maximum LBFGS iterations
    
    Returns:
        float: Optimal temperature value
    """
    import torch.nn.functional as F

    model.eval()

    # Collect all logits and labels from validation set
    all_logits = []
    all_labels = []
    with torch.no_grad():
        for images, labels in valid_loader:
            images = images.to(device)
            logits = model(images)
            all_logits.append(logits.cpu())
            all_labels.append(labels)

    all_logits = torch.cat(all_logits, dim=0)
    all_labels = torch.cat(all_labels, dim=0)

    # Optimise temperature using NLL loss
    temperature = nn.Parameter(torch.ones(1) * 1.5)
    optimizer = optim.LBFGS([temperature], lr=lr, max_iter=max_iter)
    criterion = nn.CrossEntropyLoss()

    def _eval():
        optimizer.zero_grad()
        t = temperature.clamp(min=0.1)  # don't let T go below 0.1
        loss = criterion(all_logits / t, all_labels)
        loss.backward()
        return loss

    optimizer.step(_eval)
    optimal_temp = temperature.item()
    optimal_temp = max(0.1, min(optimal_temp, 5.0))  # clamp to safe range

    print(f"  Calibrated temperature: {optimal_temp:.4f}")
    return optimal_temp


if __name__ == "__main__":
    log = train_model()

    if log is not None:
        # Post-training temperature calibration
        print("\n[Step 10] Calibrating temperature scaling...")
        device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # Load best model
        checkpoint = torch.load(BEST_MODEL_PATH, map_location=device, weights_only=False)
        model = SinhalaCNN().to(device)
        if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
        else:
            model.load_state_dict(checkpoint)
        model.eval()

        # Get validation loader
        _, valid_loader, _ = get_data_loaders(batch_size=BATCH_SIZE, num_workers=0)

        temp = calibrate_temperature(model, valid_loader, device)

        # Re-save checkpoint with calibrated temperature
        torch.save({
            'model_state_dict': model.state_dict(),
            'temperature': temp,
        }, BEST_MODEL_PATH)
        print(f"  Model re-saved with temperature={temp:.4f}")
