import os
import base64
import requests
from PIL import Image, ImageDraw, ImageFont
from env_loader import load_env, get_url

def generate_image(filepath):
    img = Image.new('RGB', (600, 200), color=(30, 30, 30))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("consola.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    
    text = "$ npm run dev:local\nready on http://localhost:3000"
    
    if hasattr(font, "getbbox"):
         bbox = font.getbbox(text)
         d.text((20, 20), text, fill=(200, 200, 200), font=font)
    else:
         d.text((20, 20), text, fill=(200, 200, 200), font=font)
         
    img.save(filepath)

def main():
    load_env()
    api_key = os.environ.get("DRIFT_API_KEY", "")
    model = os.environ.get("DRIFT_MODEL", "gemma-4-31b-it")
    url = get_url()

    img_path = os.path.join(os.path.dirname(__file__), "terminal.png")
    generate_image(img_path)

    if not url:
        print("FAIL: DRIFT_BASE_URL not set in .env")
        return

    with open(img_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the command and port from this image. Return JSON with 'command' and 'port' keys."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            print(f"PASS: Image call to {model} succeeded.")
            print("Output:", resp.json()["choices"][0]["message"]["content"])
        else:
            print(f"FAIL: Image call HTTP {resp.status_code}")
            print(f"Reason: {resp.text}")
    except Exception as e:
        print(f"FAIL: Exception occurred: {e}")

if __name__ == "__main__":
    main()
