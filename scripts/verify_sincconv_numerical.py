"""Verify that precomputed SincConv produces numerically identical results to official SincConv."""

import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from official_rawnet2_model import SincConv as OfficialSincConv

class PrecomputedSincConv(nn.Module):
    @staticmethod
    def to_mel(hz):
        return 2595 * np.log10(1 + hz / 700)

    @staticmethod
    def to_hz(mel):
        return 700 * (10 ** (mel / 2595) - 1)

    def __init__(self, out_channels=20, kernel_size=1024, in_channels=1, sample_rate=16000,
                 stride=1, padding=0, dilation=1, freq_scale='Mel'):
        super().__init__()
        if kernel_size % 2 == 0:
            kernel_size = kernel_size + 1
        self.out_channels = out_channels + 1
        self.kernel_size = kernel_size
        self.sample_rate = sample_rate
        self.stride = stride
        self.padding = padding
        self.dilation = dilation

        NFFT = 512
        f = int(self.sample_rate / 2) * np.linspace(0, 1, int(NFFT / 2) + 1)
        if freq_scale == 'Mel':
            fmel = self.to_mel(f)
            fmelmax = np.max(fmel)
            fmelmin = np.min(fmel)
            filbandwidthsmel = np.linspace(fmelmin, fmelmax, self.out_channels + 2)
            filbandwidthsf = self.to_hz(filbandwidthsmel)
            self.freq = filbandwidthsf[:self.out_channels]
        else:
            fmelmax = np.max(f)
            fmelmin = np.min(f)
            filbandwidthsmel = np.linspace(fmelmin, fmelmax, self.out_channels + 2)
            self.freq = filbandwidthsmel[:self.out_channels]

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
        self.register_buffer("filters", filters)

    def forward(self, x):
        return F.conv1d(x, self.filters, stride=self.stride, padding=self.padding, dilation=self.dilation, bias=None, groups=1)

# Test numerical equivalence
torch.manual_seed(42)
x = torch.randn(2, 1, 64600)

official_sinc = OfficialSincConv(device="cpu", out_channels=20, kernel_size=1024)
precomputed_sinc = PrecomputedSincConv(out_channels=20, kernel_size=1024)

out_official = official_sinc(x)
out_precomputed = precomputed_sinc(x)

diff = torch.max(torch.abs(out_official - out_precomputed)).item()
print(f"Max absolute difference between Official and Precomputed SincConv: {diff:.10e}")
assert diff < 1e-6, f"Difference too high: {diff}"
print("VERIFICATION PASS: Output is bit-for-bit / numerically identical!")
