"""Test loading RawNet2 model with the checkpoint and verifying forward pass."""

import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import torch
import numpy as np
from official_rawnet2_model import RawNet

ckpt_path = "weights/pre_trained_DF_RawNet2.pth"
print(f"Loading checkpoint from: {ckpt_path}")
state_dict = torch.load(ckpt_path, map_location="cpu")

# Model configuration for RawNet2 anti-spoofing
d_args = {
    'nb_samp': 64600,
    'first_conv': 1024,
    'in_channels': 1,
    'filts': [20, [20, 20], [20, 128], [128, 128]],
    'nb_fc_node': 1024,
    'gru_node': 1024,
    'nb_gru_layer': 3,
    'nb_classes': 2
}

model = RawNet(d_args, device="cpu")
missing, unexpected = model.load_state_dict(state_dict, strict=True)
print(f"Loaded successfully! Missing keys: {len(missing)}, Unexpected keys: {len(unexpected)}")

# Test forward pass with dummy tensor [1, 64600]
model.eval()
dummy_input = torch.randn(1, 64600)
with torch.no_grad():
    out = model(dummy_input)
    print("Forward pass successful! Output shape:", out.shape, "Output values:", out)
