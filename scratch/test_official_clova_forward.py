import os
import sys
import torch
import numpy as np

# Ensure repo root on path
sys.path.insert(0, os.path.abspath("."))

from scripts.clova_aasist import Model

print("=" * 80)
print("TESTING OFFICIAL CLOVA AI AASIST (scripts/clova_aasist.py)")
print("=" * 80)

# Default Clova AI AASIST hyperparameters
d_args = {
    "first_conv": 128,
    "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
    "gat_dims": [64, 32],
    "pool_ratios": [0.5, 0.7, 0.5, 0.5],
    "temperatures": [2.0, 2.0, 100.0, 100.0]
}

model = Model(d_args)
state_dict = torch.load("weights/AASIST.pth", map_location="cpu")

# Load state dict
missing, unexpected = model.load_state_dict(state_dict, strict=False)
print(f"Missing keys: {len(missing)} -> {missing}")
print(f"Unexpected keys: {len(unexpected)} -> {unexpected}")
