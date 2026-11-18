"""Download pretrained RawNet2 anti-spoofing weights from verified HuggingFace repo."""

import hashlib
import os
import sys
import urllib.request

URL = "https://huggingface.co/MattyB95/pre_trained_DF_RawNet2/resolve/main/pre_trained_DF_RawNet2.pth"
DEST = "weights/pre_trained_DF_RawNet2.pth"

os.makedirs("weights", exist_ok=True)

if os.path.exists(DEST):
    size = os.path.getsize(DEST)
    print(f"File already exists: {DEST} ({size} bytes)")
else:
    print(f"Downloading {URL} -> {DEST}...")
    def reporthook(blocknum, blocksize, totalsize):
        readsofar = blocknum * blocksize
        if totalsize > 0:
            percent = readsofar * 1e2 / totalsize
            s = f"\rProgress: {percent:5.1f}% ({readsofar}/{totalsize} bytes)"
            sys.stdout.write(s)
            sys.stdout.flush()

    urllib.request.urlretrieve(URL, DEST, reporthook=reporthook)
    print("\nDownload complete!")

# Check size & SHA256
size = os.path.getsize(DEST)
print(f"Final file size: {size} bytes ({size / (1024*1024):.2f} MB)")

hasher = hashlib.sha256()
with open(DEST, "rb") as f:
    while chunk := f.read(65536):
        hasher.update(chunk)
print(f"SHA-256: {hasher.hexdigest()}")
