import os
import sys
import numpy as np
import onnxruntime as ort

print("=" * 80)
print("PHASE 1: NEURAL MODEL LOADING & SPECIFICATION AUDIT")
print("=" * 80)

models_to_check = [
    {
        "name": "RawNet2",
        "path": "backend/models_weights/rawnet2.onnx",
        "expected_input_shape": [1, 64600],
        "expected_output_shape": [1, 2],
    },
    {
        "name": "AASIST",
        "path": "backend/models_weights/aasist.onnx",
        "expected_input_shape": [1, 64600],
        "expected_output_shape": [1, 2],
    },
    {
        "name": "ECAPA-TDNN",
        "path": "backend/models_weights/ecapa_tdnn.onnx",
        "expected_input_shape": None,
        "expected_output_shape": None,
    }
]

model_reports = {}

for m in models_to_check:
    name = m["name"]
    path = m["path"]
    exists = os.path.exists(path)
    size_mb = os.path.getsize(path) / (1024 * 1024) if exists else 0
    print(f"\n--- Model: {name} ---")
    print(f"Path: {path}")
    print(f"File Exists: {exists} (Size: {size_mb:.2f} MB)")
    
    if not exists:
        model_reports[name] = {"status": "MISSING", "error": "File not found"}
        continue

    try:
        so = ort.SessionOptions()
        so.enable_cpu_mem_arena = False
        so.intra_op_num_threads = 1
        session = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])
        
        inputs = [(inp.name, inp.shape, inp.type) for inp in session.get_inputs()]
        outputs = [(out.name, out.shape, out.type) for out in session.get_outputs()]
        
        print(f"Session Loaded: SUCCESS")
        print(f"Inputs: {inputs}")
        print(f"Outputs: {outputs}")
        
        # Test dummy forward pass
        in_name = inputs[0][0]
        in_shape = inputs[0][1]
        
        # Build test tensor
        if name in ("RawNet2", "AASIST"):
            dummy = np.random.randn(1, 64600).astype(np.float32)
        else:
            dummy = np.random.randn(1, 48000).astype(np.float32)
            
        out = session.run(None, {in_name: dummy})[0]
        print(f"Forward Pass Shape: {out.shape}")
        print(f"Forward Pass Sample Raw Values: {out[0][:5] if out.ndim > 1 else out[:5]}")
        
        model_reports[name] = {
            "status": "LOADED",
            "size_mb": round(size_mb, 2),
            "inputs": inputs,
            "outputs": outputs,
            "forward_shape": list(out.shape)
        }
    except Exception as exc:
        print(f"Session Loaded: FAILED - {exc}")
        model_reports[name] = {"status": "FAILED", "error": str(exc)}

print("\n" + "=" * 80)
print("PHASE 1 SUMMARY:")
for k, v in model_reports.items():
    print(f"  {k}: {v['status']} | Info: {v}")
print("=" * 80)
