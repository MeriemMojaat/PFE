"""
Step 5: XAI Layer – Rule‑based + LLM Judge
===========================================
- Rule‑based: checks for product condition, client data citation, forbidden words.
- LLM: evaluates clarity and overall coherence.
- Combined score = weighted average.
"""

import pandas as pd
import re
import requests
import json
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b"
CLIENTS_FILE = "data/client_rfm_profiles.csv"
RECOMMENDATIONS_FILE = "recommendations.csv"
OUTPUT_FILE = "xai_scores_final.csv"

# List of forbidden words that indicate hallucination or assumption
FORBIDDEN_WORDS = ['probable', 'peut-être', 'sans doute', 'voyagez', 'voyage', 'loisirs', 'projet', 'envisagez']

def load_clients():
    df = pd.read_csv(CLIENTS_FILE)
    df['client_id'] = df['client_id'].astype(str).str.strip()
    return df

def load_recommendations():
    df = pd.read_csv(RECOMMENDATIONS_FILE)
    if df.columns[0] != 'client_id':
        df.rename(columns={df.columns[0]: 'client_id'}, inplace=True)
    df['client_id'] = df['client_id'].astype(str).str.replace('Client ', '', regex=False).str.strip()
    return df

def get_client_profile(client_id, clients_df):
    row = clients_df[clients_df['client_id'] == client_id]
    if row.empty:
        return None
    return row.iloc[0].to_dict()

def rule_based_scoring(explanation: str, client: dict, product_name: str) -> dict:
    """Return factual, relevance, hallucination scores based on rules."""
    exp_lower = explanation.lower()
    client_data_terms = [
        str(client.get('age', '')),
        client.get('rfm_segment', '').lower(),
        str(client.get('spending_capacity', '')),
        'pharmacien' if 'pharmacien' in client.get('job_position', '').lower() else '',
        'marié' if client.get('marital_status', '').lower() == 'marié(e)' else ''
    ]
    # Check if explanation cites any client data
    cites_client_data = any(term in exp_lower for term in client_data_terms if term)
    factual_score = 10 if cites_client_data else 4
    
    # Check if explanation mentions a product condition (common conditions list)
    product_conditions = ['domiciliation', 'salaire', 'assurance', 'cotisation', 'frais', 'plafond', 'retrait', 'paiement']
    cites_condition = any(cond in exp_lower for cond in product_conditions)
    relevance_score = 10 if cites_condition else 5
    
    # Check for forbidden words (hallucination)
    forbidden_found = [w for w in FORBIDDEN_WORDS if w in exp_lower]
    hallucination_score = 10 if not forbidden_found else max(10 - len(forbidden_found) * 3, 0)
    
    return {
        "factual_score": factual_score,
        "relevance_score": relevance_score,
        "hallucination_score": hallucination_score,
        "cites_client_data": cites_client_data,
        "cites_condition": cites_condition,
        "forbidden_found": forbidden_found
    }

def llm_clarity_score(explanation: str) -> int:
    word_count = len(explanation.split())
    if word_count > 20:
        # Base clarity reduced if too long
        length_penalty = min(3, word_count - 20)
    else:
        length_penalty = 0
    # LLM still evaluates readability, but we penalise length
    prompt = f"""Évalue la clarté de cette explication (0 à 10). Réponds uniquement par un chiffre.
Explication: "{explanation}"
Règles: 10 = très claire et concise; 8 = claire mais un peu longue; 5 = confuse; 0 = incompréhensible."""
    payload = {"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1, "num_predict": 10}}
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            response = resp.json().get("response", "").strip()
            match = re.search(r'\b([0-9]|10)\b', response)
            if match:
                score = int(match.group(1))
                return max(score - length_penalty, 0)
    except:
        pass
    return max(7 - length_penalty, 0)
def main():
    clients_df = load_clients()
    recs_df = load_recommendations()
    print(f"Clients: {len(clients_df)}, Recommendations: {len(recs_df)}")
    if recs_df.empty:
        print("No recommendations found.")
        return
    
    evaluations = []
    for _, row in recs_df.iterrows():
        client_id = row['client_id']
        product_name = row['product_name']
        explanation = row['explanation']
        client = get_client_profile(client_id, clients_df)
        if not client:
            print(f"Client {client_id} not found. Skipping.")
            continue
        
        print(f"Evaluating {client_id} -> {product_name}")
        # Rule-based scores
        rule_scores = rule_based_scoring(explanation, client, product_name)
        # LLM clarity score
        clarity = llm_clarity_score(explanation)
        # Overall = average of factual, relevance, clarity, hallucination
        overall = (rule_scores["factual_score"] + rule_scores["relevance_score"] + clarity + rule_scores["hallucination_score"]) / 4
        
        evaluations.append({
            "client_id": client_id,
            "product_name": product_name,
            "factual_score": rule_scores["factual_score"],
            "relevance_score": rule_scores["relevance_score"],
            "clarity_score": clarity,
            "hallucination_score": rule_scores["hallucination_score"],
            "overall_score": round(overall, 1),
            "cites_client_data": rule_scores["cites_client_data"],
            "cites_condition": rule_scores["cites_condition"],
            "forbidden_words": ", ".join(rule_scores["forbidden_found"]) if rule_scores["forbidden_found"] else "",
            "evaluated_at": datetime.now()
        })
    
    eval_df = pd.DataFrame(evaluations)
    eval_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved {len(evaluations)} evaluations to {OUTPUT_FILE}")
    print("\nScore distribution:")
    print(eval_df[['factual_score', 'relevance_score', 'clarity_score', 'hallucination_score', 'overall_score']].describe())
def evaluate_recommendation(recommendation: dict, client: dict) -> dict:
    """Compute XAI scores for a single recommendation dictionary."""
    explanation = recommendation.get('explanation', '')
    product_name = recommendation.get('product_name', '')
    rule_scores = rule_based_scoring(explanation, client, product_name)
    clarity = llm_clarity_score(explanation)
    overall = (rule_scores["factual_score"] + rule_scores["relevance_score"] + clarity + rule_scores["hallucination_score"]) / 4
    return {
        "factual_score": rule_scores["factual_score"],
        "relevance_score": rule_scores["relevance_score"],
        "clarity_score": clarity,
        "hallucination_score": rule_scores["hallucination_score"],
        "overall_score": round(overall, 1),
        "judge_feedback": f"Cites client data: {rule_scores['cites_client_data']}, Cites condition: {rule_scores['cites_condition']}, Forbidden: {rule_scores['forbidden_found']}"
    }
if __name__ == "__main__":
    main()