"""
Recommendation Engine – Mistral 7b, French, Highly Personalised
Now loads merchants and merges category into operations.
"""

import json
import re
import os
import pandas as pd
import requests
from datetime import datetime
from typing import List, Dict, Optional
from django.conf import settings

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
BASE_DIR = settings.BASE_DIR
DATA_DIR = os.path.join(BASE_DIR, 'myapp', 'data')

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral:7b"

CLIENTS_FILE = os.path.join(DATA_DIR, "client_rfm_profiles.csv")
PRODUCTS_FILE = os.path.join(DATA_DIR, "product_features.csv")
OPERATIONS_FILE = os.path.join(DATA_DIR, "operations_filtered.xlsx")
MERCHANTS_FILE = os.path.join(DATA_DIR, "merchants_clean.csv")
GOLDEN_EXAMPLES_FILE = os.path.join(DATA_DIR, "golden_examples.json")

FORBIDDEN_WORDS = []
SAFE_EXPLANATION = ""

CATEGORY_PRODUCT_MAP = {
    "Travel": ["voyage", "travel", "bh travel", "assurvoyage"],
    "Banking Services": ["gab", "distributeur", "cash", "retrait", "atm"],
    "Food & Beverages": ["carte", "go", "cool"],
    "Healthcare": ["assur", "dhamen", "santé"],
    "Retail": ["carte", "pack"],
}

def repair_json(json_str: str) -> str:
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    json_str = re.sub(r'\}\s*\{', '},{', json_str)
    return json_str

class RecommendationEngine:
    def __init__(self):
        self.clients_df = pd.read_csv(CLIENTS_FILE)
        self.products_df = pd.read_csv(PRODUCTS_FILE)
        self.products_df.columns = self.products_df.columns.str.strip().str.lower()
        for col in ['requires_domiciliation', 'max_age', 'requires_autofinancement_percent',
                    'min_income_smig', 'requires_marital_status', 'requires_profession']:
            if col not in self.products_df.columns:
                if 'percent' in col or 'income' in col:
                    self.products_df[col] = 0
                elif col == 'max_age':
                    self.products_df[col] = 120
                else:
                    self.products_df[col] = False
        self.products_df['min_age'] = self.products_df['min_age'].fillna(0).astype(int)
        self.products_df['max_age'] = self.products_df['max_age'].fillna(120).astype(int)
        self.load_transactional_behaviour()
        self.golden_examples = self.load_golden_examples()

    def load_transactional_behaviour(self):
        try:
            # Load operations
            ops = pd.read_excel(OPERATIONS_FILE)
            ops['transaction_date'] = pd.to_datetime(ops['transaction_date'])
            ops.columns = ops.columns.str.lower()
            
            # Load merchants
            merchants = pd.read_csv(MERCHANTS_FILE)
            merchants.columns = merchants.columns.str.strip().str.lower()
            # Ensure merchant_code is string
            merchants['merchant_code'] = merchants['merchant_code'].astype(str)
            ops['merchant_code'] = ops['merchant_code'].astype(str)
            
            # Merge category into operations
            ops = ops.merge(merchants[['merchant_code', 'category']], on='merchant_code', how='left')
            if 'category' not in ops.columns:
                ops['category'] = 'Unknown'
            else:
                ops['category'] = ops['category'].fillna('Unknown')
            
            # Map to client accounts
            clients_acc = self.clients_df[['client_id', 'account_number']].copy()
            clients_acc['account_number'] = clients_acc['account_number'].astype(str)
            ops['account_number'] = ops['account_number'].astype(str)
            merged = ops.merge(clients_acc, on='account_number')
            
            if merged.empty:
                self.clients_df['top_merchant_category'] = 'Unknown'
                self.clients_df['avg_transaction_amount'] = 0
                self.clients_df['summer_spending_ratio'] = 0
                return
            
            # Aggregations
            avg_tx = merged.groupby('client_id')['authorized_amount'].mean().rename('avg_transaction_amount')
            top_cat = merged.groupby('client_id')['category'].agg(lambda x: x.mode()[0] if not x.mode().empty else 'Unknown').rename('top_merchant_category')
            merged['is_summer'] = merged['transaction_date'].dt.month.isin([6,7,8])
            summer_ratio = merged.groupby('client_id').apply(
                lambda g: g[g['is_summer']]['authorized_amount'].sum() / g['authorized_amount'].sum() if g['authorized_amount'].sum() > 0 else 0
            ).rename('summer_spending_ratio')
            self.clients_df = self.clients_df.merge(avg_tx, on='client_id', how='left')
            self.clients_df = self.clients_df.merge(top_cat, on='client_id', how='left')
            self.clients_df = self.clients_df.merge(summer_ratio, on='client_id', how='left')
            self.clients_df.fillna({'avg_transaction_amount':0, 'top_merchant_category':'Unknown', 'summer_spending_ratio':0}, inplace=True)
        except Exception as e:
            print(f"Transactional behaviour skipped: {e}")

    def load_golden_examples(self):
        try:
            with open(GOLDEN_EXAMPLES_FILE) as f:
                return json.load(f)
        except:
            return []

    def get_client_profile(self, client_id: str) -> Optional[Dict]:
        client_id_str = str(client_id).strip()
        df_str = self.clients_df['client_id'].astype(str).str.strip()
        row = self.clients_df[df_str == client_id_str]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    def prefilter_products(self, client: Dict) -> List[Dict]:
        age = client['age']
        filtered = []
        for _, p in self.products_df.iterrows():
            if p['min_age'] > 0 and age < p['min_age']:
                continue
            target = p['target_audience'].lower()
            if target == 'seniors' and age < 55:
                continue
            if target == 'jeunes' and age > 30:
                continue
            if target == 'étudiants' and age > 30:
                continue
            filtered.append(p.to_dict())
        return filtered

    def boost_by_merchant_category(self, client: Dict, recommendations: List[Dict]) -> List[Dict]:
        top_cat = client.get('top_merchant_category', 'Unknown')
        if top_cat == 'Unknown' or top_cat not in CATEGORY_PRODUCT_MAP:
            return recommendations
        keywords = CATEGORY_PRODUCT_MAP.get(top_cat, [])
        if not keywords:
            return recommendations
        for rec in recommendations:
            prod_name = rec['product_name'].lower()
            base_score = rec['score']
            boost = any(kw.lower() in prod_name for kw in keywords)
            if boost:
                rec['score'] = min(base_score + 0.5, 10)
                rec['explanation'] += f" (Catégorie marchande favorite: {top_cat})"
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations

    def get_similar_example(self, client: Dict) -> str:
        if not self.golden_examples:
            return ""
        best_score = -1
        best_ex = None
        for ex in self.golden_examples:
            score = 1 - abs(client['age'] - ex['age']) / 100
            if ex.get('rfm') == client['rfm_segment']:
                score += 0.2
            if ex.get('job') == client['job_position']:
                score += 0.2
            if score > best_score:
                best_score = score
                best_ex = ex
        if best_ex and best_score > 0.5:
            return f"Exemple pour un client similaire (âge {best_ex['age']}, {best_ex['job']}) : Produit : {best_ex['product']} – Explication : {best_ex['explanation']}"
        return ""

    def build_prompt(self, client: Dict, products: List[Dict]) -> str:
        age = client['age']
        job = client['job_position']
        marital = client['marital_status']
        rfm = client['rfm_segment']
        spending = client['spending_capacity']
        top_cat = client.get('top_merchant_category', 'N/A')
        summer = client.get('summer_spending_ratio', 0) * 100

        profile = f"""
Âge: {age} ans
Profession: {job}
Situation familiale: {marital}
Segment RFM: {rfm}
Capacité d'épargne mensuelle: {spending:.2f} TND
Catégorie de magasins préférée: {top_cat}
Dépenses estivales: {summer:.1f}% du total
"""
        product_lines = []
        for i, p in enumerate(products, 1):
            product_lines.append(
                f"{i}. {p['name']} | Cible: {p['target_audience']} | Âge min: {p['min_age']} | Conditions: {p['conditions']} | Avantage: {p['benefits']}"
            )
        products_text = "\n".join(product_lines)
        example_text = self.get_similar_example(client)
        example_block = f"\n{example_text}\n" if example_text else ""

        prompt = f"""Tu es un conseiller bancaire expert. Recommande 3 produits parfaitement adaptés à ce client.

Profil du client:
{profile}

Produits disponibles (déjà filtrés par âge):
{products_text}
{example_block}

RÈGLES OBLIGATOIRES:
- Réponds UNIQUEMENT en français, y compris les explications.
- Utilise les données réelles du client (âge, profession, capacité d'épargne, catégorie marchande favorite).
- Si la catégorie marchande favorite est "Travel", privilégie les cartes de voyage.
- Pour un avocat ou pharmacien, propose des cartes premium (BH GOLD) ou des packs haut de gamme.
- Cite au moins deux attributs du client dans chaque explication.
- Réponds avec un JSON valide, sans texte avant ou après.

Exemple de bonne réponse:
{{"recommendations": [
  {{"product_name": "La carte BH GOLD Internationale","score": 9,"explanation": "Âge 36, pharmacien, capacité d'épargne élevée. Carte premium adaptée."}},
  {{"product_name": "Le Pack : BH Elite","score": 8,"explanation": "Segment Medium Value, profession libérale. Pack haut de gamme avec avantages fiscaux."}},
  {{"product_name": "Le credit Direct","score": 7,"explanation": "Investissement professionnel, revenus stables. Crédit habitat à taux préférentiel."}}
]}}

JSON:"""
        return prompt

    def extract_recommendations_from_text(self, text: str) -> List[Dict]:
        code_block = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_block:
            text = code_block.group(1)
        else:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                text = text[start:end]
        text = repair_json(text)
        try:
            data = json.loads(text)
            if "recommendations" in data:
                return data["recommendations"]
        except:
            pass
        pattern = r'"product_name"\s*:\s*"(.+?)"\s*,\s*"score"\s*:\s*(\d+)\s*,\s*"explanation"\s*:\s*"(.+?)"(?=\s*[,\}])'
        matches = re.findall(pattern, text, re.DOTALL)
        return [{"product_name": n.strip(), "score": int(s), "explanation": e.strip()} for n,s,e in matches]

    def call_llm(self, prompt: str) -> Dict:
        payload = {"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.0, "num_predict": 800}}
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
            if resp.status_code == 200:
                try:
                    response_json = resp.json()
                except:
                    print("Failed to parse JSON from Ollama response")
                    return {}
                response = response_json.get("response", "")
                if not response.strip():
                    print("Empty response from LLM")
                    return {}
                recs = self.extract_recommendations_from_text(response)
                if recs:
                    return {"recommendations": recs}
                else:
                    print("No recommendations extracted from response.")
            else:
                print(f"HTTP error: {resp.status_code}")
        except requests.exceptions.Timeout:
            print("LLM request timed out")
        except Exception as e:
            print(f"LLM error: {e}")
        return {}

    def rule_based_fallback(self, client: Dict) -> List[Dict]:
        age = client['age']
        seg = client['rfm_segment']
        job = client.get('job_position', '').lower()
        top_cat = client.get('top_merchant_category', '').lower()
        recs = []
        if 'avocat' in job or 'pharmacien' in job or 'senior' in job:
            if top_cat == 'travel':
                recs.append(("La carte BH TRAVEL", 8, "Adaptée aux voyages fréquents."))
            recs.append(("La carte BH GOLD Internationale", 9, "Carte premium pour professionnels."))
            recs.append(("Le Pack : BH Elite", 8, "Pack haut de gamme avec avantages."))
        elif age >= 55:
            recs.append(("Le Pack : Senior", 8, "Pack dédié aux seniors."))
            recs.append(("Assur Senior", 7, "Assurance santé pour seniors."))
        elif seg in ['Champion','High Value']:
            recs.append(("La carte BH GOLD Internationale", 9, "Carte premium."))
            recs.append(("Le Pack : BH Elite", 8, "Pack haut de gamme."))
        else:
            recs.append(("LA CARTE CIB", 5, "Carte de base."))
            recs.append(("Le credit Direct", 6, "Crédit habitat."))
        return [{"product_name": n, "score": s, "explanation": e} for n,s,e in recs[:3]]

    def recommend_for_client(self, client_id: str) -> List[Dict]:
        print(f"\n🔍 Génération de recommandations pour le client {client_id}")
        client = self.get_client_profile(client_id)
        if not client:
            return [{"error": f"Client {client_id} non trouvé"}]
        print(f"✅ Client: âge={client['age']}, RFM={client['rfm_segment']}, profession={client['job_position']}, top catégorie={client.get('top_merchant_category', 'N/A')}")
        filtered = self.prefilter_products(client)
        print(f"📊 Produits préfiltrés: {len(filtered)} sur {len(self.products_df)}")
        if not filtered:
            print("⚠️ Aucun produit préfiltré – utilisation du fallback")
            recs = self.rule_based_fallback(client)
            return recs[:3]
        prompt = self.build_prompt(client, filtered)
        result = self.call_llm(prompt)
        recs = result.get("recommendations", [])
        if not recs:
            print("⚠️ Échec de l'IA – utilisation du fallback")
            recs = self.rule_based_fallback(client)
        else:
            print(f"✅ L'IA a retourné {len(recs)} recommandations")
        recs = self.boost_by_merchant_category(client, recs)
        return recs[:3]

    def recommend_all_clients(self, limit=None, output_file="recommendations.csv"):
        all_recs = []
        clients = self.clients_df['client_id'].astype(str).str.strip().tolist()
        if limit:
            clients = clients[:limit]
        for cid in clients:
            recs = self.recommend_for_client(cid)
            for r in recs:
                all_recs.append({"client_id": cid, "product_name": r['product_name'], "score": r['score'], "explanation": r['explanation']})
        pd.DataFrame(all_recs).to_csv(output_file, index=False)
        return all_recs

if __name__ == "__main__":
    eng = RecommendationEngine()
    sample = eng.clients_df['client_id'].iloc[0]
    print(json.dumps(eng.recommend_for_client(sample), indent=2, ensure_ascii=False))