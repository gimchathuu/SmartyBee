"""
CNN Model — Small-Data-Safe Architecture for Sinhala Letter Recognition
========================================================================
Designed for ~190 training samples per class (14 classes).

Architecture principles:
1. Progressive channel widening (32→64→128) — not too deep
2. Heavy dropout (0.4) — prevents overfitting on small data
3. Batch normalization — stabilizes training
4. Global average pooling — reduces parameters vs FC flatten
5. Small input (64×64) — appropriate for dataset size
6. No pretrained backbone — dataset is too domain-specific
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from ml_pipeline.ml_config import (
    NUM_CLASSES, DROPOUT_RATE, HIDDEN_DIM, CONV_CHANNELS, IMG_SIZE
)


class ConvBlock(nn.Module):
    """Conv → BatchNorm → ReLU → Conv → BatchNorm → ReLU → MaxPool → Dropout"""

    def __init__(self, in_channels, out_channels, dropout=0.25):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.pool = nn.MaxPool2d(2, 2)
        self.dropout = nn.Dropout2d(dropout)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = self.pool(x)
        x = self.dropout(x)
        return x


class SinhalaCNN(nn.Module):
    """
    Small-data-safe CNN for 14-class Sinhala letter recognition.
    
    Architecture:
        Input: (B, 1, 64, 64)
        Block 1: 1→32 channels, output 32×32
        Block 2: 32→64 channels, output 16×16
        Block 3: 64→128 channels, output 8×8
        Global Average Pool: 128
        FC: 128→128→14
    
    Total params: ~250K (deliberately small for small dataset)
    """

    def __init__(self, num_classes=NUM_CLASSES, dropout=DROPOUT_RATE):
        super().__init__()

        ch = CONV_CHANNELS  # [32, 64, 128]

        # Convolutional blocks with progressive channel widening
        self.block1 = ConvBlock(1, ch[0], dropout=0.15)      # 64→32
        self.block2 = ConvBlock(ch[0], ch[1], dropout=0.20)   # 32→16
        self.block3 = ConvBlock(ch[1], ch[2], dropout=0.25)   # 16→8

        # Global Average Pooling (reduces 8×8 → 1×1)
        # Much fewer params than flatten, better generalization
        self.gap = nn.AdaptiveAvgPool2d(1)

        # Classification head
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(ch[2], HIDDEN_DIM),
            nn.BatchNorm1d(HIDDEN_DIM),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(HIDDEN_DIM, num_classes),
        )

        # Weight initialization
        self._initialize_weights()

    def _initialize_weights(self):
        """Kaiming initialization for Conv layers, Xavier for Linear."""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d) or isinstance(m, nn.BatchNorm1d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x):
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.gap(x)
        x = self.classifier(x)
        return x

    def extract_features(self, x):
        """Extract feature maps before classification (for debugging/analysis)."""
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.gap(x)
        return x.view(x.size(0), -1)


def get_model(device='cpu', pretrained_path=None):
    """
    Create model instance, optionally loading pretrained weights.
    
    Args:
        device: 'cpu' or 'cuda'
        pretrained_path: Path to .pth file to load
    
    Returns:
        SinhalaCNN model on specified device
    """
    model = SinhalaCNN().to(device)

    if pretrained_path:
        import os
        if os.path.exists(pretrained_path):
            state_dict = torch.load(pretrained_path, map_location=device, weights_only=True)
            model.load_state_dict(state_dict)
            print(f"[Model] Loaded weights from {pretrained_path}")
        else:
            print(f"[Model] WARNING: {pretrained_path} not found, using random weights")

    return model


def count_parameters(model):
    """Count trainable parameters."""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[Model] Total params: {total:,} | Trainable: {trainable:,}")
    return trainable


if __name__ == "__main__":
    # Quick sanity check
    model = SinhalaCNN()
    count_parameters(model)

    # Test forward pass
    x = torch.randn(2, 1, IMG_SIZE, IMG_SIZE)
    out = model(x)
    print(f"Input shape:  {x.shape}")
    print(f"Output shape: {out.shape}")
    print(f"Output (logits): {out}")
    
    probs = F.softmax(out, dim=1)
    print(f"Probabilities sum: {probs.sum(dim=1)}")
