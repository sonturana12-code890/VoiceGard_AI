"""
VOICEGUARD AI — Official AASIST PyTorch to ONNX Exporter
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.

Exports the official Clova AI AASIST pretrained checkpoint (weights/AASIST.pth)
to an optimized ONNX model (backend/models_weights/aasist.onnx) for production inference.

Architecture:
- Full AASIST: Heterogeneous Stacking Graph Attention Network (Jung et al., ICASSP 2022)
- Front-End: SincNet analytical bandpass filterbank (CONV)
- Encoder: 6 Residual_blocks with 2D convolutions & MaxPool2d
- Graph: 2 Homo-GATs (Spectral, Temporal) + 4 Hetero-GATs (ST11, ST12, ST21, ST22) with master nodes
- Readout: GraphPool projections -> 160-dim feature vector -> out_layer (2 classes)

Output Class Mapping Contract (UNIFIED ACROSS VOICEGUARD AI):
- Index 0 = AI_GENERATED / SPOOF
- Index 1 = REAL_HUMAN / BONAFIDE
* Exact 1:1 match with official weights/AASIST.pth (no permutation/swapping).

Usage:
    python scripts/export_aasist_to_onnx.py --checkpoint weights/AASIST.pth --output backend/models_weights/aasist.onnx
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Prevent OpenBLAS thread allocation issues on Windows before importing numpy/torch
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:
    print(
        "ERROR: PyTorch is required to run the export script.\n"
        "Run this script in the Python environment where PyTorch is installed."
    )
    sys.exit(1)

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from scripts.clova_aasist import Model as ClovaAASISTModel

DEFAULT_D_ARGS: Dict[str, Any] = {
    "first_conv": 128,
    "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
    "gat_dims": [64, 32],
    "pool_ratios": [0.5, 0.7, 0.5, 0.5],
    "temperatures": [2.0, 2.0, 100.0, 100.0],
}


class AASISTExportWrapper(nn.Module):
    """
    ONNX Export wrapper around the official Clova AI AASIST architecture.
    Strips the intermediate feature representation and outputs class logits.
    """

    def __init__(self, model: ClovaAASISTModel, swap_classes_for_voiceguard: bool = False):
        super().__init__()
        self.model = model
        self.swap_classes_for_voiceguard = swap_classes_for_voiceguard

    def forward(self, audio_waveform: torch.Tensor) -> torch.Tensor:
        """
        Input: [batch_size, 64600] float32 at 16kHz
        Output: [batch_size, 2] logits:
            Index 0 = AI_GENERATED / SPOOF
            Index 1 = REAL_HUMAN / BONAFIDE
        """
        _, raw_output = self.model(audio_waveform)
        if self.swap_classes_for_voiceguard:
            return raw_output[:, [1, 0]]
        return raw_output


def export_aasist(
    checkpoint_path: Path,
    output_path: Path,
    opset: int = 17,
    swap_classes: bool = False,
) -> None:
    """
    Loads weights/AASIST.pth, instantiates official ClovaAASISTModel,
    verifies 229 parameter tensors, and exports to optimized ONNX graph.
    """
    print(f"[1] Loading official checkpoint: {checkpoint_path}")
    raw_dict = torch.load(checkpoint_path, map_location="cpu")
    if isinstance(raw_dict, dict) and "state_dict" in raw_dict:
        raw_dict = raw_dict["state_dict"]
    elif isinstance(raw_dict, dict) and "model" in raw_dict:
        raw_dict = raw_dict["model"]

    # Clean module. prefix if present
    cleaned = {k[7:] if k.startswith("module.") else k: v for k, v in raw_dict.items()}

    print("[2] Instantiating official Clova AI AASIST architecture...")
    base_model = ClovaAASISTModel(DEFAULT_D_ARGS)
    missing, unexpected = base_model.load_state_dict(cleaned, strict=True)

    print(f"    State dict loaded: {len(cleaned)} keys (Missing: {len(missing)}, Unexpected: {len(unexpected)})")
    base_model.eval()

    wrapper = AASISTExportWrapper(base_model, swap_classes_for_voiceguard=swap_classes)
    wrapper.eval()

    dummy_input = torch.randn(1, 64600, dtype=torch.float32)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[3] Exporting ONNX graph to: {output_path} (opset {opset})...")
    print(f"    Class mapping: Index 0 = {'REAL_HUMAN' if swap_classes else 'AI_GENERATED'}, Index 1 = {'AI_GENERATED' if swap_classes else 'REAL_HUMAN'}")

    torch.onnx.export(
        wrapper,
        dummy_input,
        str(output_path),
        export_params=True,
        opset_version=opset,
        do_constant_folding=True,
        input_names=["audio_waveform"],
        output_names=["logits"],
        dynamic_axes={
            "audio_waveform": {0: "batch_size"},
            "logits": {0: "batch_size"},
        },
        dynamo=False,
    )
    print(f"[4] SUCCESS: Exported {output_path} ({output_path.stat().st_size / (1024*1024):.2f} MB)")

    if ort is not None:
        print("[5] Validating exported ONNX graph with ONNXRuntime against PyTorch reference...")
        sess = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
        in_name = sess.get_inputs()[0].name
        
        for bs in [1, 2, 4]:
            test_x = torch.randn(bs, 64600, dtype=torch.float32)
            with torch.no_grad():
                py_out = wrapper(test_x).numpy()
            onnx_out = sess.run(None, {in_name: test_x.numpy()})[0]
            max_diff = float(np.max(np.abs(py_out - onnx_out)))
            print(f"    Batch Size {bs:2d}: PyTorch shape={py_out.shape}, ONNX shape={onnx_out.shape}, Max Abs Error={max_diff:.6e}")
            assert max_diff < 1e-4, f"Export verification failed on batch size {bs}: diff={max_diff}"

        print("    --> All export verification checks PASSED successfully.")


def main():
    parser = argparse.ArgumentParser(description="VoiceGuard AI — AASIST Official Exporter")
    parser.add_argument("--checkpoint", type=str, default="weights/AASIST.pth", help="Input .pth path")
    parser.add_argument("--output", type=str, default="backend/models_weights/aasist.onnx", help="Output .onnx path")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version")
    parser.add_argument("--swap-classes", action="store_true", default=False, help="Explicitly swap classes (NOT recommended)")
    args = parser.parse_args()

    export_aasist(
        checkpoint_path=Path(args.checkpoint),
        output_path=Path(args.output),
        opset=args.opset,
        swap_classes=args.swap_classes,
    )


if __name__ == "__main__":
    main()
