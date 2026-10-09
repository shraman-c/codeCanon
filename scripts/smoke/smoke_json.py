import os
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
        "messages": [{"role": "user", "content": 'Return {"status":"success"} as JSON.'}],
        "response_format": {"type": "json_object"}
    }

    try:
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            clean_json = content.strip().startswith("{") and content.strip().endswith("}")
            fenced = content.strip().startswith("```")
            print(f"PASS: JSON call to {model} succeeded.")
            print(f"Details: Clean JSON: {clean_json}, Wrapped in fences: {fenced}")
            print(f"Raw Output: {content}")
        else:
            print(f"FAIL: HTTP {resp.status_code} with response_format json_object")
            print(f"Reason: {resp.text}")
            
            # Retry without response_format
            payload.pop("response_format")
            resp2 = requests.post(url, json=payload, headers=headers)
            if resp2.status_code == 200:
                content2 = resp2.json()["choices"][0]["message"]["content"]
                clean_json = content2.strip().startswith("{") and content2.strip().endswith("}")
                fenced = content2.strip().startswith("```")
                print(f"PASS (Fallback without response_format): Call succeeded.")
                print(f"Details: Clean JSON: {clean_json}, Wrapped in fences: {fenced}")
            else:
                print(f"FAIL (Fallback): HTTP {resp2.status_code}")

    except Exception as e:
        print(f"FAIL: Exception occurred: {e}")

if __name__ == "__main__":
    main()
