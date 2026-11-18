"""Quorum device node: one Qdrant Edge shard per device, synced through a hub.

Isolation happens here, before anything imports fastembed or huggingface_hub: this machine exports
HF_HOME globally (pointing at another project's cache), so we overwrite it rather than default it.
"""
import os
import sys
from pathlib import Path

CHECKOUT_ROOT = Path(__file__).resolve().parents[2]
# The device also starts from app/, while the shared lab lives at the checkout root.
if str(CHECKOUT_ROOT) not in sys.path:
    sys.path.append(str(CHECKOUT_ROOT))

QUORUM_ROOT = Path(os.environ.get("QUORUM_ROOT") or CHECKOUT_ROOT)
MODELS_DIR = QUORUM_ROOT / "models"

os.environ["HF_HOME"] = str(MODELS_DIR / "hf")
os.environ["FASTEMBED_CACHE_PATH"] = str(MODELS_DIR / "fastembed")
