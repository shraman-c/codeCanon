import os
import sys

def load_env():
    # Find .env in project root
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(root_dir, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

def get_url():
    base = os.environ.get("DRIFT_BASE_URL", "").rstrip("/")
    if base:
        if not base.endswith("/v1") and not base.endswith("/openai"):
            pass
        return f"{base}/chat/completions"
    return ""

