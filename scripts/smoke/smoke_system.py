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

    # Test 1: Native system role
    payload_system = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Reply only with the word PINEAPPLE"},
            {"role": "user", "content": "hello"}
        ]
    }

    # Test 2: Folded system role
    payload_folded = {
        "model": model,
        "messages": [
            {"role": "user", "content": "System: Reply only with the word PINEAPPLE\nUser: hello"}
        ]
    }

    try:
        # 1
        resp_sys = requests.post(url, json=payload_system, headers=headers)
        sys_success = False
        if resp_sys.status_code == 200:
            ans = resp_sys.json()["choices"][0]["message"]["content"].strip()
            print(f"System role response: {ans}")
            sys_success = ("PINEAPPLE" in ans.upper())
            if sys_success:
                print("PASS: System role is accepted and followed.")
            else:
                print("FAIL: System role accepted but not followed properly.")
        else:
            print(f"FAIL: System role rejected with HTTP {resp_sys.status_code}")
            print(f"Reason: {resp_sys.text}")

        # 2
        resp_fold = requests.post(url, json=payload_folded, headers=headers)
        fold_success = False
        if resp_fold.status_code == 200:
            ans = resp_fold.json()["choices"][0]["message"]["content"].strip()
            print(f"Folded role response: {ans}")
            fold_success = ("PINEAPPLE" in ans.upper())
            if fold_success:
                print("PASS: Folded instructions work.")
            else:
                print("FAIL: Folded instructions not followed properly.")
        else:
            print(f"FAIL: Folded instructions HTTP {resp_fold.status_code}")
        
        if sys_success:
            print("Recommendation: DRIFT_FOLD_SYSTEM=false")
        elif fold_success:
            print("Recommendation: DRIFT_FOLD_SYSTEM=true")
        else:
            print("Recommendation: Unable to determine (both failed to output PINEAPPLE).")

    except Exception as e:
        print(f"FAIL: Exception occurred: {e}")

if __name__ == "__main__":
    main()

