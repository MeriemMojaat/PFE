"""
Step 3 (Enhanced): Product Attribute Extraction using LLM only
==============================================================
- Uses Ollama for every product
- Outputs product_features.csv with confidence score
- Manual review recommended only for low-confidence rows
"""

import json
import pandas as pd
import requests
import time
import re

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b"  # or "llama3:8b" or "mistral"
INPUT_JSON = "data/product_contents.json"
OUTPUT_CSV = "data/product_features.csv"

def call_llm(prompt: str) -> dict:
    """Call Ollama and parse JSON response."""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 512}
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
        if resp.status_code == 200:
            response = resp.json().get("response", "")
            # Extract JSON from response (in case LLM adds extra text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                print(f"  No JSON found in response: {response[:100]}")
                return {}
        else:
            print(f"  HTTP error: {resp.status_code}")
            return {}
    except Exception as e:
        print(f"  Connection error: {e}")
        return {}

def extract_product_attributes(product: dict) -> dict:
    """Extract attributes using LLM."""
    name = product['name']
    category = product['category']
    subcategory = product['subcategory'] or ""
    # Limit content to 3000 chars to avoid token limits
    content = product['content'][:3500]
    
    prompt = f"""Tu es un expert en produits bancaires. Extrais les attributs suivants de la fiche produit ci-dessous.

Produit: {name}
Catégorie: {category}
Sous-catégorie: {subcategory}
Description:
{content}

Attributs à extraire (utilise UNIQUEMENT le vocabulaire ci-dessous):
1. target_audience: public cible (choisis parmi: "jeunes", "seniors", "hauts revenus", "professionnels", "particuliers", "jeunes actifs", "familles", "général")
2. min_age: âge minimum requis (nombre entier, 0 si non spécifié)
3. conditions: liste des conditions requises, séparées par des virgules (ex: "domiciliation de salaire, épargne préalable"). Si aucune, mets "".
4. benefits: principal avantage en une phrase courte (max 15 mots). Tire-le directement du texte.

Réponds UNIQUEMENT avec un JSON valide, sans aucun texte avant ou après. Exemple:
{{"target_audience": "jeunes", "min_age": 13, "conditions": "domiciliation de salaire", "benefits": "Cotisation annuelle de 7 DT"}}"""

    result = call_llm(prompt)
    
    # Provide defaults if extraction failed
    return {
        "name": name,
        "category": category,
        "subcategory": subcategory,
        "target_audience": result.get("target_audience", "général"),
        "min_age": int(result.get("min_age", 0)) if str(result.get("min_age", "0")).isdigit() else 0,
        "conditions": result.get("conditions", ""),
        "benefits": result.get("benefits", "Avantage non spécifié")[:200],
        "confidence": "high" if result else "low"  # if LLM returned empty, confidence low
    }

def main():
    print("Loading product_contents.json...")
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    products = data["products"]
    print(f"Loaded {len(products)} products. Extracting attributes using LLM (may take a few minutes)...")
    
    rows = []
    for i, prod in enumerate(products):
        print(f"Processing {i+1}/{len(products)}: {prod['name'][:50]}...")
        attrs = extract_product_attributes(prod)
        rows.append(attrs)
        time.sleep(0.5)  # slight delay to avoid overloading Ollama
    
    # Save to CSV
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False)
    
    print(f"\n✅ Saved product features to {OUTPUT_CSV}")
    print("\nConfidence summary:")
    print(df['confidence'].value_counts())
    print("\nNext steps:")
    print("1. Open the CSV in Excel/LibreOffice.")
    print("2. Filter rows where confidence == 'low' (if any).")
    print("3. Manually verify and correct those rows.")
    print("4. If all confidence is 'high', you can use the file as is.")

if __name__ == "__main__":
    main()