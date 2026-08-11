import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:3b-instruct",
        "prompt": "Say hello",
        "stream": False
    }
)

print(response.json()["response"])