import requests
import json

url = "http://localhost:11434/api/generate"
payload = {
    "model": "mistral:7b",
    "prompt": "Dis bonjour en une phrase",
    "stream": False,
    "options": {"max_tokens": 50}
}
try:
    response = requests.post(url, json=payload, timeout=10)
    print("Status:", response.status_code)
    print("Response:", response.json().get('response', 'No response'))
except Exception as e:
    print("Error:", e)