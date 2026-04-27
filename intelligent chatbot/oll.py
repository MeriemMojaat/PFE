# test_ollama.py
import requests

try:
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    print(f"✅ Ollama is running!")
    print(f"Available models: {response.json()}")
except Exception as e:
    print(f"❌ Cannot connect: {e}")