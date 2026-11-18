import onnxruntime as ort
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

model_path = "models/rawnet2.onnx"
audio_path = "sontu1.mpeg"

session = ort.InferenceSession(
    model_path,
    providers=["CPUExecutionProvider"]
)

# Load audio
audio, sr = sf.read(audio_path)

# Convert stereo to mono
if audio.ndim == 2:
    audio = audio.mean(axis=1)

# Convert sample rate to 16 kHz
if sr != 16000:
    from math import gcd
    g = gcd(sr, 16000)
    audio = resample_poly(audio, 16000 // g, sr // g)

# Prepare audio length
audio = audio.astype(np.float32)

if len(audio) < 64600:
    audio = np.pad(audio, (0, 64600 - len(audio)))
else:
    audio = audio[:64600]

audio = np.expand_dims(audio, axis=0)

# Run inference
input_name = session.get_inputs()[0].name

output = session.run(
    None,
    {input_name: audio}
)[0]

print("\nRAW MODEL OUTPUT:")
print(output)

# Softmax
exp_values = np.exp(output - np.max(output, axis=1, keepdims=True))
probabilities = exp_values / np.sum(exp_values, axis=1, keepdims=True)

print("\nOUTPUT PROBABILITIES:")
print(probabilities)

print("\nINDEX 0:", probabilities[0][0] * 100, "%")
print("INDEX 1:", probabilities[0][1] * 100, "%")
