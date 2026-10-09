import os
import sys
import requests
from env_loader import load_env, get_url

def main():
    load_env()
    api_key = os.environ.get("DRIFT_API_KEY", "")
    model = os.environ.get("DRIFT_MODEL", "gemma-4-31b-it")
    url = get_url()

    if not url:
        print("FAIL: DRIFT_BASE_URL not set in .env")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say hello in one word."}]
    }

    try:
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            print(f"PASS: Text call to {model} succeeded.")
        else:
            print(f"FAIL: HTTP {resp.status_code}")
            print(f"Reason: {resp.text}")
            
            # Try fetching models if models endpoint exists
            try:
                models_url = url.replace("/chat/completions", "/models")
                m_resp = requests.get(models_url, headers=headers)
                if m_resp.status_code == 200:
                    models = [m["id"] for m in m_resp.json().get("data", [])]
                    print("Available models:", models)
            except Exception:
                pass
    except Exception as e:
        print(f"FAIL: Exception occurred: {e}")

if __name__ == "__main__":
    main()
