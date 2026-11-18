"""Inspect RawNet2 checkpoint keys and tensor shapes."""

import torch

ckpt_path = "weights/pre_trained_DF_RawNet2.pth"
print(f"Loading checkpoint: {ckpt_path}")

ckpt = torch.load(ckpt_path, map_location="cpu")

if isinstance(ckpt, dict):
    print("Checkpoint type: dict")
    print(f"Top-level keys: {list(ckpt.keys())}")
    
    # Check if nested state dict
    if "state_dict" in ckpt:
        state_dict = ckpt["state_dict"]
    elif "model" in ckpt:
        state_dict = ckpt["model"]
    else:
        state_dict = ckpt
else:
    state_dict = ckpt

print(f"\nTotal tensor keys in state_dict: {len(state_dict)}")
total_params = 0
for k, v in state_dict.items():
    if hasattr(v, "shape"):
        numel = v.numel()
        total_params += numel
        print(f"  {k:45s} : shape={list(v.shape)!s:20s} dtype={v.dtype} ({numel:,} params)")
    else:
        print(f"  {k:45s} : {type(v)}")

print(f"\nTotal parameters: {total_params:,}")
