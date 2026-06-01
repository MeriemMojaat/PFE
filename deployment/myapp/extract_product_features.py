"""
Step 3 (Enhanced): Product Attribute Extraction with max_age
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
MODEL = "llama3:8b"          # or "mistral:7b"
INPUT_JSON = "data/product_contents.json"
OUTPUT_CSV = "data/product_features.csv"

def call_llm(prompt: str) -> dict:
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
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        return {}
    except Exception as e:
        print(f"  Error: {e}")
        return {}

def extract_max_age_from_text(content: str) -> int:
    """Fallback regex to extract max_age from product description."""
    patterns = [
        r'entre\s+(\d+)\s+et\s+(\d+)\s+ans',          # "entre 13 et 18 ans" -> max=18
        r'âgées? entre\s+(\d+)\s+et\s+(\d+)\s+ans',
        r'âge\s+minimum\s+(\d+)\s+ans\s+et\s+maximum\s+(\d+)\s+ans',
        r'ne\s+peut\s+pas\s+dépasser\s+(\d+)\s+ans',
        r'jusqu\'à\s+(\d+)\s+ans',
        r'limite\s+d\'âge\s+supérieure\s*:\s*(\d+)',
        r'(?i)(?:max|maximum)\s+(\d+)\s+ans'
    ]
    for pat in patterns:
        match = re.search(pat, content, re.IGNORECASE)
        if match:
            if len(match.groups()) == 2:
                return int(match.group(2))   # second number is max
            else:
                return int(match.group(1))
    return 120   # default

def extract_product_attributes(product: dict) -> dict:
    name = product['name']
    category = product['category']
    subcategory = product['subcategory'] or ""
    content = product['content'][:3500]
    
    prompt = f"""Tu es un expert en produits bancaires. Extrais les attributs suivants de la fiche produit ci-dessous.

Produit: {name}
Catégorie: {category}
Sous-catégorie: {subcategory}
Description:
{content}

Attributs à extraire (utilise UNIQUEMENT le vocabulaire ci-dessous):
1. target_audience: public cible (parmi: "jeunes", "seniors", "hauts revenus", "professionnels", "particuliers", "jeunes actifs", "familles", "général")
2. min_age: âge minimum requis (nombre entier, 0 si non spécifié)
3. max_age: âge maximum autorisé (nombre entier, 120 si non spécifié). Important pour les cartes jeunes (ex: "entre 13 et 18 ans" -> max_age=18)
4. conditions: liste des conditions requises, séparées par des virgules (ex: "domiciliation de salaire, épargne préalable"). Si aucune, mets "".
5. benefits: principal avantage en une phrase courte (max 15 mots). Tire-le directement du texte.

Réponds UNIQUEMENT avec un JSON valide, sans aucun texte avant ou après. Exemple:
{{"target_audience": "jeunes", "min_age": 13, "max_age": 18, "conditions": "domiciliation de salaire", "benefits": "Cotisation annuelle de 7 DT"}}"""

    result = call_llm(prompt)
    
    # Use LLM result or fallback for max_age
    max_age = result.get("max_age", 0)
    if not max_age or max_age == 0:
        max_age = extract_max_age_from_text(content)
    
    return {
        "name": name,
        "category": category,
        "subcategory": subcategory,
        "target_audience": result.get("target_audience", "général"),
        "min_age": int(result.get("min_age", 0)) if str(result.get("min_age", "0")).isdigit() else 0,
        "max_age": int(max_age) if str(max_age).isdigit() else 120,
        "conditions": result.get("conditions", ""),
        "benefits": result.get("benefits", "Avantage non spécifié")[:200],
        "confidence": "high" if result else "low"
    }

def main():
    print("Loading product_contents.json...")
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    products = data["products"]
    print(f"Loaded {len(products)} products. Extracting attributes with max_age...")
    
    rows = []
    for i, prod in enumerate(products):
        print(f"Processing {i+1}/{len(products)}: {prod['name'][:50]}...")
        attrs = extract_product_attributes(prod)
        rows.append(attrs)
        time.sleep(0.5)
    
    df = pd.DataFrame(rows)
    # Order columns
    ordered = ["name", "category", "subcategory", "target_audience", "min_age", "max_age", "conditions", "benefits", "confidence"]
    df = df[ordered]
    df.to_csv(OUTPUT_CSV, index=False)
    
    print(f"\n✅ Saved product features to {OUTPUT_CSV}")
    print("\nConfidence summary:")
    print(df['confidence'].value_counts())
    print("\nSample age limits:")
    print(df[['name', 'min_age', 'max_age']].head(10))

if __name__ == "__main__":
    main()