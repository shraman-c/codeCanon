import os
import base64
import requests
from PIL import Image, ImageDraw, ImageFont
from env_loader import load_env

def generate_image(filepath):
    img = Image.new('RGB', (600, 200), color=(30, 30, 30))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("consola.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    
    text = "$ npm run dev:local\nready on http://localhost:3000"
    
    d.text((20, 20), text, fill=(200, 200, 200), font=font)
    img.save(filepath)

def main():
    load_env()
    api_key = os.environ.get("DRIFT_API_KEY", "")
    model = os.environ.get("DRIFT_MODEL", "gemma-4-31b-it")
    
    img_path = os.path.join(os.path.dirname(__file__), "terminal.png")
    if not os.path.exists(img_path):
        generate_image(img_path)
        
    with open(img_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [{
            "parts": [
                {"text": "Extract the command and port from this image. Return JSON with 'command' and 'port' keys."},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64_image
                    }
                }
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    try:
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            print(f"PASS: Native Image call to {model} succeeded.")
            print("Output:", resp.json()["candidates"][0]["content"]["parts"][0]["text"])
        else:
            print(f"FAIL: Native Image call HTTP {resp.status_code}")
            print(f"Reason: {resp.text}")
    except Exception as e:
        print(f"FAIL: Exception occurred: {e}")

if __name__ == "__main__":
    main()

