"""Test loading official SpeechBrain ECAPA-TDNN model and extracting embeddings."""

import time
import torch
import numpy as np
from speechbrain.inference.speaker import SpeakerRecognition
from speechbrain.utils.fetching import LocalStrategy

savedir = "weights/spkrec-ecapa-voxceleb"
print(f"Loading official pretrained model 'speechbrain/spkrec-ecapa-voxceleb' into '{savedir}'...")

t0 = time.perf_counter()
model = SpeakerRecognition.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir=savedir,
    run_opts={"device": "cpu"},
    local_strategy=LocalStrategy.COPY,
)
t1 = time.perf_counter()
print(f"Model loaded in {t1 - t0:.2f} seconds!")

# Create a dummy 16kHz audio tensor (e.g. 2 seconds = 32000 samples)
dummy_waveform = torch.randn(1, 32000)

print("\nExtracting speaker embeddings...")
embedding = model.encode_batch(dummy_waveform)
print("Embedding tensor shape:", embedding.shape)
# Shape should be [1, 1, 192] or [1, 192]
emb_np = embedding.squeeze().detach().cpu().numpy()
print("Squeezed embedding shape:", emb_np.shape)
print("Embedding dimension:", emb_np.shape[-1])
print("Embedding norm before L2 normalization:", np.linalg.norm(emb_np))

# L2 normalize
norm_emb = emb_np / (np.linalg.norm(emb_np) + 1e-12)
print("Embedding norm after L2 normalization:", np.linalg.norm(norm_emb))

# Cosine similarity self-check
cos_sim = float(np.dot(norm_emb, norm_emb))
print("Self cosine similarity:", cos_sim)
