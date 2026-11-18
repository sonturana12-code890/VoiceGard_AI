"""
VOICEGUARD AI — Official RawNet2 PyTorch to ONNX Exporter
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.

Exports the official Tak et al. RawNet2 pretrained checkpoint (weights/pre_trained_DF_RawNet2.pth)
to an optimized ONNX model (backend/models_weights/rawnet2.onnx) for production inference.

Architecture Details:
- Front-End: SincNet analytical Mel filterbank (20 filters, 1024 filter length, 16 kHz sample rate)
- Residual Blocks: 6 blocks with 1D convolutions, BatchNorm1d, LeakyReLU (0.3), MaxPool1d(3)
- Attention: Filter-wise Feature Map (FMS) with Sigmoid gating
- Recurrent Layer: 3-layer bidirectional/unidirectional GRU (1024 hidden nodes)
- Dense Head: Linear(1024, 1024) -> Linear(1024, 2)
- Output Class Remapping:
  * Official Checkpoint: Index 0 = Spoof, Index 1 = Bonafide
  * Remapped VoiceGuard Output: Index 0 = Human (Bona-fide), Index 1 = Synthetic (Spoof)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:
    print(
        "ERROR: PyTorch is required to run the export script.\n"
        "Run this script in the root environment where PyTorch is installed."
    )
    sys.exit(1)

try:
    import onnx
    import onnxruntime as ort
except ImportError:
    print("ERROR: onnx and onnxruntime are required for export validation.")
    sys.exit(1)


# ============================================================================
# 1. SincConv Layer with Precomputed Mel Filterbank for Clean ONNX Tracing
# ============================================================================

class SincConv(nn.Module):
    """
    Fixed Sinc-convolutional filterbank as described in:
    Tak et al., 'End-to-End anti-spoofing with RawNet2', ICASSP 2021.
    """

    @staticmethod
    def to_mel(hz: np.ndarray) -> np.ndarray:
        return 2595.0 * np.log10(1.0 + hz / 700.0)

    @staticmethod
    def to_hz(mel: np.ndarray) -> np.ndarray:
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    def __init__(
        self,
        out_channels: int = 20,
        kernel_size: int = 1024,
        in_channels: int = 1,
        sample_rate: int = 16000,
        stride: int = 1,
        padding: int = 0,
        dilation: int = 1,
        freq_scale: str = "Mel",
    ) -> None:
        super().__init__()
        if in_channels != 1:
            raise ValueError(f"SincConv only supports 1 input channel, got {in_channels}")

        if kernel_size % 2 == 0:
            kernel_size = kernel_size + 1

        self.out_channels = out_channels + 1
        self.kernel_size = kernel_size
        self.sample_rate = sample_rate
        self.stride = stride
        self.padding = padding
        self.dilation = dilation

        # Initialize filterbanks using Mel scale matching official eurecom-asp implementation
        NFFT = 512
        f = int(self.sample_rate / 2) * np.linspace(0, 1, int(NFFT / 2) + 1)

        if freq_scale == "Mel":
            fmel = self.to_mel(f)
            fmelmax = np.max(fmel)
            fmelmin = np.min(fmel)
            filbandwidthsmel = np.linspace(fmelmin, fmelmax, self.out_channels + 2)
            filbandwidthsf = self.to_hz(filbandwidthsmel)
            self.freq = filbandwidthsf[: self.out_channels]
        else:
            fmelmax = np.max(f)
            fmelmin = np.min(f)
            filbandwidthsmel = np.linspace(fmelmin, fmelmax, self.out_channels + 2)
            self.freq = filbandwidthsmel[: self.out_channels]

        hsupp = torch.arange(-(self.kernel_size - 1) / 2, (self.kernel_size - 1) / 2 + 1)
        band_pass = torch.zeros(self.out_channels - 1, self.kernel_size)

        for i in range(len(self.freq) - 1):
            fmin = self.freq[i]
            fmax = self.freq[i + 1]
            hHigh = (2 * fmax / self.sample_rate) * np.sinc(2 * fmax * hsupp.numpy() / self.sample_rate)
            hLow = (2 * fmin / self.sample_rate) * np.sinc(2 * fmin * hsupp.numpy() / self.sample_rate)
            hideal = hHigh - hLow
            band_pass[i, :] = torch.tensor(np.hamming(self.kernel_size) * hideal, dtype=torch.float32)

        filters = band_pass.view(self.out_channels - 1, 1, self.kernel_size)
        self.register_buffer("filters", filters, persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.conv1d(
            x,
            self.filters,
            stride=self.stride,
            padding=self.padding,
            dilation=self.dilation,
            bias=None,
            groups=1,
        )


# ============================================================================
# 2. Residual Block with FMS Attention
# ============================================================================

class ResidualBlock(nn.Module):
    def __init__(self, nb_filts: List[int], first: bool = False) -> None:
        super().__init__()
        self.first = first

        if not self.first:
            self.bn1 = nn.BatchNorm1d(num_features=nb_filts[0])

        self.lrelu = nn.LeakyReLU(negative_slope=0.3)
        self.conv1 = nn.Conv1d(
            in_channels=nb_filts[0],
            out_channels=nb_filts[1],
            kernel_size=3,
            padding=1,
            stride=1,
        )
        self.bn2 = nn.BatchNorm1d(num_features=nb_filts[1])
        self.conv2 = nn.Conv1d(
            in_channels=nb_filts[1],
            out_channels=nb_filts[1],
            kernel_size=3,
            padding=1,
            stride=1,
        )

        if nb_filts[0] != nb_filts[1]:
            self.downsample = True
            self.conv_downsample = nn.Conv1d(
                in_channels=nb_filts[0],
                out_channels=nb_filts[1],
                kernel_size=1,
                padding=0,
                stride=1,
            )
        else:
            self.downsample = False

        self.mp = nn.MaxPool1d(3)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        if not self.first:
            out = self.bn1(x)
            out = self.lrelu(out)
        else:
            out = x

        out = self.conv1(out)
        out = self.bn2(out)
        out = self.lrelu(out)
        out = self.conv2(out)

        if self.downsample:
            identity = self.conv_downsample(identity)

        out += identity
        out = self.mp(out)
        return out


# ============================================================================
# 3. Complete RawNet2 Architecture Matching Official eurecom-asp Checkpoint
# ============================================================================

class RawNet2(nn.Module):
    def __init__(self, swap_classes_for_voiceguard: bool = True) -> None:
        super().__init__()
        self.swap_classes_for_voiceguard = swap_classes_for_voiceguard

        # Front-end SincNet
        self.Sinc_conv = SincConv(
            out_channels=20,
            kernel_size=1024,
            in_channels=1,
            sample_rate=16000,
            freq_scale="Mel",
        )
        self.first_bn = nn.BatchNorm1d(num_features=20)
        self.selu = nn.SELU(inplace=True)

        # Residual Blocks
        self.block0 = nn.Sequential(ResidualBlock(nb_filts=[20, 20], first=True))
        self.block1 = nn.Sequential(ResidualBlock(nb_filts=[20, 20]))
        self.block2 = nn.Sequential(ResidualBlock(nb_filts=[20, 128]))
        self.block3 = nn.Sequential(ResidualBlock(nb_filts=[128, 128]))
        self.block4 = nn.Sequential(ResidualBlock(nb_filts=[128, 128]))
        self.block5 = nn.Sequential(ResidualBlock(nb_filts=[128, 128]))

        self.avgpool = nn.AdaptiveAvgPool1d(1)

        # Filter-wise Feature Map (FMS) Attention
        self.fc_attention0 = nn.Sequential(nn.Linear(in_features=20, out_features=20))
        self.fc_attention1 = nn.Sequential(nn.Linear(in_features=20, out_features=20))
        self.fc_attention2 = nn.Sequential(nn.Linear(in_features=128, out_features=128))
        self.fc_attention3 = nn.Sequential(nn.Linear(in_features=128, out_features=128))
        self.fc_attention4 = nn.Sequential(nn.Linear(in_features=128, out_features=128))
        self.fc_attention5 = nn.Sequential(nn.Linear(in_features=128, out_features=128))

        self.bn_before_gru = nn.BatchNorm1d(num_features=128)
        self.gru = nn.GRU(
            input_size=128,
            hidden_size=1024,
            num_layers=3,
            batch_first=True,
        )

        self.fc1_gru = nn.Linear(in_features=1024, out_features=1024)
        self.fc2_gru = nn.Linear(in_features=1024, out_features=2, bias=True)
        self.sig = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input shape: [batch, samples] (e.g., [batch, 64600])
        nb_samp = x.shape[0]
        len_seq = x.shape[1]
        x = x.view(nb_samp, 1, len_seq)

        x = self.Sinc_conv(x)
        x = F.max_pool1d(torch.abs(x), 3)
        x = self.first_bn(x)
        x = self.selu(x)

        # Block 0 + FMS Attention
        x0 = self.block0(x)
        y0 = self.avgpool(x0).view(x0.size(0), -1)
        y0 = self.fc_attention0(y0)
        y0 = self.sig(y0).view(y0.size(0), y0.size(1), -1)
        x = x0 * y0 + y0

        # Block 1 + FMS Attention
        x1 = self.block1(x)
        y1 = self.avgpool(x1).view(x1.size(0), -1)
        y1 = self.fc_attention1(y1)
        y1 = self.sig(y1).view(y1.size(0), y1.size(1), -1)
        x = x1 * y1 + y1

        # Block 2 + FMS Attention
        x2 = self.block2(x)
        y2 = self.avgpool(x2).view(x2.size(0), -1)
        y2 = self.fc_attention2(y2)
        y2 = self.sig(y2).view(y2.size(0), y2.size(1), -1)
        x = x2 * y2 + y2

        # Block 3 + FMS Attention
        x3 = self.block3(x)
        y3 = self.avgpool(x3).view(x3.size(0), -1)
        y3 = self.fc_attention3(y3)
        y3 = self.sig(y3).view(y3.size(0), y3.size(1), -1)
        x = x3 * y3 + y3

        # Block 4 + FMS Attention
        x4 = self.block4(x)
        y4 = self.avgpool(x4).view(x4.size(0), -1)
        y4 = self.fc_attention4(y4)
        y4 = self.sig(y4).view(y4.size(0), y4.size(1), -1)
        x = x4 * y4 + y4

        # Block 5 + FMS Attention
        x5 = self.block5(x)
        y5 = self.avgpool(x5).view(x5.size(0), -1)
        y5 = self.fc_attention5(y5)
        y5 = self.sig(y5).view(y5.size(0), y5.size(1), -1)
        x = x5 * y5 + y5

        x = self.bn_before_gru(x)
        x = self.selu(x)
        x = x.permute(0, 2, 1)  # (batch, time, filt)

        x, _ = self.gru(x)
        x = x[:, -1, :]
        x = self.fc1_gru(x)
        raw_output = self.fc2_gru(x)  # [batch, 2] -> [spoof, bonafide]

        if self.swap_classes_for_voiceguard:
            # VoiceGuard AI standard: [bonafide (Human), spoof (Synthetic)]
            return raw_output[:, [1, 0]]
        return raw_output


# ============================================================================
# 4. Export & Validation Function
# ============================================================================

def export_rawnet2_to_onnx(
    checkpoint_path: Path,
    output_path: Path,
    opset: int = 17,
    swap_classes: bool = True,
) -> None:
    print("=" * 70)
    print("VOICEGUARD AI — RAWNET2 PYTORCH TO ONNX EXPORT")
    print("=" * 70)
    print(f"Loading checkpoint: {checkpoint_path}")

    raw_dict = torch.load(str(checkpoint_path), map_location="cpu")
    if isinstance(raw_dict, dict) and "state_dict" in raw_dict:
        raw_dict = raw_dict["state_dict"]
    elif isinstance(raw_dict, dict) and "model" in raw_dict:
        raw_dict = raw_dict["model"]

    # Clean module. prefix if present
    cleaned = {k[7:] if k.startswith("module.") else k: v for k, v in raw_dict.items()}

    print("Instantiating official RawNet2 architecture...")
    model = RawNet2(swap_classes_for_voiceguard=swap_classes)
    missing, unexpected = model.load_state_dict(cleaned, strict=False)

    print(f"Total state dict keys: {len(cleaned)}")
    print(f"Missing keys: {len(missing)} {missing}")
    print(f"Unexpected keys: {len(unexpected)} {unexpected}")
    assert len(missing) == 0, f"Critical missing keys: {missing}"
    assert len(unexpected) == 0, f"Critical unexpected keys: {unexpected}"

    model.eval()

    # Create dummy input: 1 audio window of 64,600 samples (float32)
    dummy_input = torch.randn(1, 64600, dtype=torch.float32)

    with torch.no_grad():
        py_output = model(dummy_input)
    print(f"PyTorch test forward output shape: {py_output.shape}")
    print(f"PyTorch logits: {py_output.numpy()}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"\nExporting ONNX model to: {output_path} (opset {opset})...")

    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        export_params=True,
        opset_version=opset,
        do_constant_folding=True,
        dynamo=False,
        input_names=["audio_input"],
        output_names=["logits"],
        dynamic_axes={
            "audio_input": {0: "batch_size"},
            "logits": {0: "batch_size"},
        },
    )

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Export complete! ONNX file size: {file_size_mb:.2f} MB ({output_path.stat().st_size:,} bytes)")

    # 5. ONNX Verification
    print("\nVerifying exported ONNX model with onnx.checker...")
    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)
    print("ONNX model structure check PASSED!")

    # 6. ONNX Runtime Inference & Numerical Equivalence
    print("\nValidating numerical equivalence between PyTorch and ONNX Runtime...")
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    ort_session = ort.InferenceSession(str(output_path), sess_options=opts, providers=["CPUExecutionProvider"])

    ort_inputs = {"audio_input": dummy_input.numpy()}
    ort_outputs = ort_session.run(None, ort_inputs)
    ort_logits = ort_outputs[0]

    max_diff = float(np.max(np.abs(py_output.numpy() - ort_logits)))
    print(f"PyTorch logits:     {py_output.numpy()}")
    print(f"ONNXRuntime logits: {ort_logits}")
    print(f"Max absolute difference: {max_diff:.8e}")

    def stable_sm(logits: np.ndarray) -> np.ndarray:
        s = logits - np.max(logits, axis=-1, keepdims=True)
        e = np.exp(s)
        return e / np.sum(e, axis=-1, keepdims=True)

    py_probs = stable_sm(py_output.numpy())
    ort_probs = stable_sm(ort_logits)
    prob_diff = float(np.max(np.abs(py_probs - ort_probs)))

    print(f"PyTorch logits:         {py_output.numpy()}")
    print(f"ONNXRuntime logits:     {ort_logits}")
    print(f"Max logit difference:   {max_diff:.8e}")
    print(f"Max prob difference:    {prob_diff:.8e}")

    assert max_diff < 5e-4, f"Single-sample logit discrepancy exceeds tolerance: {max_diff} >= 5e-4"
    assert prob_diff < 1e-4, f"Single-sample probability discrepancy exceeds tolerance: {prob_diff} >= 1e-4"
    print("NUMERICAL VERIFICATION PASSED: Single-sample probability discrepancy < 1e-4 threshold.")

    # 7. Test batch inference (batch_size = 3)
    batch_input = torch.randn(3, 64600, dtype=torch.float32)
    with torch.no_grad():
        py_batch_out = model(batch_input)
    ort_batch_out = ort_session.run(None, {"audio_input": batch_input.numpy()})[0]
    batch_max_diff = float(np.max(np.abs(py_batch_out.numpy() - ort_batch_out)))

    py_batch_probs = stable_sm(py_batch_out.numpy())
    ort_batch_probs = stable_sm(ort_batch_out)
    prob_max_diff = float(np.max(np.abs(py_batch_probs - ort_batch_probs)))

    print(f"\nBatch (N=3) max logit difference: {batch_max_diff:.8e}")
    print(f"Batch (N=3) max probability difference: {prob_max_diff:.8e}")
    assert batch_max_diff < 1e-3, f"Batch discrepancy exceeds tolerance: {batch_max_diff}"
    assert prob_max_diff < 1e-4, f"Batch probability discrepancy exceeds tolerance: {prob_max_diff}"
    print("BATCH INFERENCE VERIFICATION PASSED: Probability discrepancy < 1e-4 threshold!")

    print("\n" + "=" * 70)
    print("SUCCESS: RawNet2 ONNX model is fully verified and production-ready!")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export RawNet2 checkpoint to ONNX")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("weights/pre_trained_DF_RawNet2.pth"),
        help="Path to PyTorch checkpoint file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/models_weights/rawnet2.onnx"),
        help="Path for exported ONNX file",
    )
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version")
    parser.add_argument(
        "--keep-original-classes",
        action="store_true",
        help="Disable VoiceGuard class remapping",
    )
    args = parser.parse_args()

    export_rawnet2_to_onnx(
        checkpoint_path=args.checkpoint,
        output_path=args.output,
        opset=args.opset,
        swap_classes=not args.keep_original_classes,
    )


if __name__ == "__main__":
    main()
