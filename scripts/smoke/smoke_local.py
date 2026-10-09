import requests
import json

def main():
    url = "http://localhost:11434/v1/chat/completions"
    model = "gemma4:e4b"
    
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say hello from Ollama."}]
    }

    try:
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            print(f"PASS: Local text call to {model} succeeded.")
            print("Output:", resp.json()["choices"][0]["message"]["content"])
        else:
            print(f"FAIL: Local HTTP {resp.status_code}")
            print(f"Reason: {resp.text}")
            
    except requests.exceptions.ConnectionError:
        print("SKIP: Ollama is not running on localhost:11434")
    except Exception as e:
        print(f"FAIL: Exception occurred: {e}")

if __name__ == "__main__":
    main()

