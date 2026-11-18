import os
import sys
import torch
import numpy as np
import soundfile as sf
import yaml

# Ensure repo root on path
sys.path.insert(0, os.path.abspath("."))

print("=" * 80)
print("INSPECTING ORIGINAL AASIST PYTORCH CHECKPOINT: weights/AASIST.pth")
print("=" * 80)

ckpt_path = "weights/AASIST.pth"
raw_dict = torch.load(ckpt_path, map_location="cpu")
print(f"Type of raw_dict: {type(raw_dict)}")

if isinstance(raw_dict, dict):
    print(f"Top-level keys: {list(raw_dict.keys())[:10]}")
    if "state_dict" in raw_dict:
        state_dict = raw_dict["state_dict"]
    elif "model" in raw_dict:
        state_dict = raw_dict["model"]
    else:
        state_dict = raw_dict
else:
    state_dict = raw_dict

print(f"Total keys in state_dict: {len(state_dict)}")
first_keys = list(state_dict.keys())[:15]
print("First 15 keys in state_dict:")
for k in first_keys:
    print(f"  {k}: shape {state_dict[k].shape}")

last_keys = list(state_dict.keys())[-10:]
print("\nLast 10 keys in state_dict:")
for k in last_keys:
    print(f"  {k}: shape {state_dict[k].shape}")
