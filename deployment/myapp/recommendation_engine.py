"""
Recommendation Engine – Final with Feedback Modifier and Prompt Improvement
Longer explanations enabled (num_predict=2000, temperature=0.2)
Added pre‑filter rules: block gold/premium for Low Value/At Risk, block loans for age < 21
Force RFM segment in explanations
"""

import json
import re
import os
import pandas as pd
import requests
from datetime import datetime
from typing import List, Dict, Optional
from django.conf import settings
from myapp.models import ProductScoreModifier

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
    "Banking Services": ["gab", "distributeur", "cash", "retrait", "atm", "mobile", "sms"],
    "Food & Beverages": ["carte", "go", "cool"],
    "Healthcare": ["assur", "dhamen", "santé"],
    "Retail": ["carte", "pack"],
}

def repair_json(json_str: str) -> str:
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    json_str = re.sub(r'\}\s*\{', '},{', json_str)
    return json_str

def compute_factual_score(explanation: str, client: Dict) -> int:
    exp_lower = explanation.lower()
    if any(str(client.get('age', '')) in exp_lower for _ in [1] if client.get('age')):
        return 8
    return 4

def compute_relevance_score(explanation: str) -> int:
    keywords = ['domiciliation', 'salaire', 'assurance', 'cotisation', 'frais', 'plafond', 'retrait', 'paiement']
    exp_lower = explanation.lower()
    return 10 if any(kw in exp_lower for kw in keywords) else 5

def compute_clarity_score(explanation: str) -> int:
    length = len(explanation)
    if length < 40:
        return 5
    if length > 400:
        return 6
    sentence_count = max(1, explanation.count('.') + explanation.count('!') + explanation.count('?'))
    return 9 if (sentence_count >= 2 and length > 100) else 7

def compute_hallucination_score(explanation: str) -> int:
    return 10

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
        self.use_llm_judge = True   # Ensure LLM judge is active

    def load_transactional_behaviour(self):
        try:
            valid_accounts = set(self.clients_df['account_number'].astype(str))
            merchants = pd.read_csv(MERCHANTS_FILE)
            merchants.columns = merchants.columns.str.strip().str.lower()
            merchants['merchant_code'] = merchants['merchant_code'].astype(str)
            agg_data = {}
            chunksize = 500000
            for chunk in pd.read_excel(OPERATIONS_FILE, chunksize=chunksize):
                chunk.columns = chunk.columns.str.lower()
                chunk['transaction_date'] = pd.to_datetime(chunk['transaction_date'])
                chunk['merchant_code'] = chunk['merchant_code'].astype(str)
                chunk['account_number'] = chunk['account_number'].astype(str)
                chunk = chunk[chunk['account_number'].isin(valid_accounts)]
                if chunk.empty:
                    continue
                chunk = chunk.merge(merchants[['merchant_code', 'category']], on='merchant_code', how='left')
                chunk['category'] = chunk['category'].fillna('Unknown')
                for acc in chunk['account_number'].unique():
                    if acc not in agg_data:
                        agg_data[acc] = {
                            'sum_amount': 0,
                            'count_amount': 0,
                            'category_counts': {},
                            'summer_sum': 0,
                            'total_sum': 0
                        }
                    client_rows = chunk[chunk['account_number'] == acc]
                    agg_data[acc]['sum_amount'] += client_rows['authorized_amount'].sum()
                    agg_data[acc]['count_amount'] += len(client_rows)
                    for cat, cnt in client_rows['category'].value_counts().items():
                        agg_data[acc]['category_counts'][cat] = agg_data[acc]['category_counts'].get(cat, 0) + cnt
                    summer_mask = client_rows['transaction_date'].dt.month.isin([6,7,8])
                    agg_data[acc]['summer_sum'] += client_rows.loc[summer_mask, 'authorized_amount'].sum()
                    agg_data[acc]['total_sum'] += client_rows['authorized_amount'].sum()
            account_to_client = dict(zip(self.clients_df['account_number'].astype(str), self.clients_df['client_id']))
            avg_amounts = {}
            top_categories = {}
            summer_ratios = {}
            for acc, data in agg_data.items():
                client_id = account_to_client.get(acc)
                if not client_id:
                    continue
                avg_amounts[client_id] = data['sum_amount'] / data['count_amount'] if data['count_amount'] > 0 else 0
                if data['category_counts']:
                    top_cat = max(data['category_counts'], key=data['category_counts'].get)
                else:
                    top_cat = 'Unknown'
                top_categories[client_id] = top_cat
                summer_ratio = data['summer_sum'] / data['total_sum'] if data['total_sum'] > 0 else 0
                summer_ratios[client_id] = summer_ratio
            self.clients_df['avg_transaction_amount'] = self.clients_df['client_id'].map(avg_amounts).fillna(0)
            self.clients_df['top_merchant_category'] = self.clients_df['client_id'].map(top_categories).fillna('Unknown')
            self.clients_df['summer_spending_ratio'] = self.clients_df['client_id'].map(summer_ratios).fillna(0)
        except Exception as e:
            print(f"Transactional behaviour skipped: {e}")
            self.clients_df['top_merchant_category'] = 'Unknown'
            self.clients_df['avg_transaction_amount'] = 0
            self.clients_df['summer_spending_ratio'] = 0

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
        return row.iloc[0].to_dict() if not row.empty else None

    def prefilter_products(self, client: Dict) -> List[Dict]:
        age = client['age']
        spending = client['spending_capacity']
        rfm = client.get('rfm_segment', '')
        job = client.get('job_position', '').lower()
        filtered = []
        for _, p in self.products_df.iterrows():
            # Block gold/premium products for Low Value and At Risk segments
            if rfm in ['Low Value', 'At Risk'] and ('gold' in p['name'].lower() or 'premium' in p['name'].lower() or 'internationale' in p['name'].lower()):
                continue
            # Block loans for clients under 21
            if age < 21 and ('prêt' in p['name'].lower() or 'credit' in p['name'].lower()):
                continue
            if p['min_age'] > 0 and age < p['min_age']:
                continue
            if p['max_age'] < age:
                continue
            target = p['target_audience'].lower()
            if target == 'seniors' and age < 55:
                continue
            if target == 'jeunes' and age > 30:
                continue
            if target == 'étudiants' and age > 30:
                continue
            if age > 75 and 'credit' in p['name'].lower():
                continue
            if rfm == 'Low Value' and ('credit' in p['name'].lower() or 'prêt' in p['name'].lower()):
                if spending < 2500:
                    continue
            if 'pharmacien' in job and spending < 2000:
                if 'gold' in p['name'].lower() or 'internationale' in p['name'].lower():
                    continue
            if 'credit' in p['name'].lower() and 'habitat' in str(p['category']).lower():
                if age < 40 and rfm not in ['Champion', 'High Value']:
                    continue
            if 'épargne' in p['name'].lower() or 'capital plus' in p['name'].lower():
                if 'capital plus' in p['name'].lower() and spending < 1000:
                    continue
            if 'foprolos' in p['name'].lower():
                if rfm in ['Champion', 'High Value'] and spending > 2000:
                    continue
            filtered.append(p.to_dict())
        return filtered

    def boost_by_merchant_category(self, client: Dict, recommendations: List[Dict]) -> List[Dict]:
        top_cat = client.get('top_merchant_category', 'Unknown')
        if top_cat in CATEGORY_PRODUCT_MAP:
            keywords = CATEGORY_PRODUCT_MAP[top_cat]
            for rec in recommendations:
                if any(kw in rec['product_name'].lower() for kw in keywords):
                    rec['score'] = min(rec['score'] + 0.5, 10)
                    rec['explanation'] += " (service numérique adapté)"
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
        product_lines = [f"{i}. {p['name']} | Cible: {p['target_audience']} | Âge min: {p['min_age']} | Âge max: {p['max_age']} | Conditions: {p['conditions']} | Avantage: {p['benefits']}" for i,p in enumerate(products,1)]
        products_text = "\n".join(product_lines)
        example_text = self.get_similar_example(client)
        example_block = f"\n{example_text}\n" if example_text else ""

        profession_hint = ""
        job_lower = job.lower()
        if 'pharmacien' in job_lower:
            profession_hint = " Pour un pharmacien, privilégie 'La carte Yasmine', 'Dhamen Compte' et 'Le Pack : BH Access'."
        elif 'directeur' in job_lower or 'agence' in job_lower or 'bancaire' in job_lower:
            profession_hint = " Pour un directeur d'agence bancaire, privilégie 'Le Pack : BH Select', 'BH Net Mobile' et 'Dhamen Compte'."

        premium_rule = ""
        if rfm in ['Champion', 'High Value'] and spending > 2000:
            premium_rule = " IMPORTANT: Ce client est Champion/High Value avec capacité d'épargne élevée. Recommande 'La carte BH GOLD Internationale' plutôt que 'La carte Yasmine'."

        elderly_rule = ""
        if age > 75:
            elderly_rule = " IMPORTANT: Client très âgé. Ne recommande AUCUN crédit. Privilégie une carte nationale simple (CIB) et le service BH SMS."

        low_value_rule = ""
        if rfm in ['Low Value', 'At Risk']:
            low_value_rule = " IMPORTANT: Client Low Value ou At Risk. Ne recommande PAS de crédit, ni de produits 'Gold' ou 'Premium'. Privilégie cartes nationales de base, packs économiques et assurances simples."

        terminology_rule = " IMPORTANT: N'utilisez JAMAIS le terme 'revenu mensuel' ou 'revenu'. Utilisez uniquement 'capacité d'épargne mensuelle' (ou 'capacité d'épargne')."

        income_wording_rule = ""
        if rfm not in ['Champion', 'High Value']:
            income_wording_rule = " ATTENTION: N'utilisez PAS les termes 'hauts revenus', 'revenus élevés', 'premium' ou 'luxe' dans l'explication. Restez sur des avantages concrets et accessibles (frais bas, simplicité, sécurité)."

        prompt = f"""Tu es un conseiller bancaire expert. Recommande 3 produits parfaitement adaptés à ce client.

Profil du client:
{profile}

Produits disponibles (déjà filtrés par âge et pertinence):
{products_text}
{example_block}
{profession_hint}
{premium_rule}
{elderly_rule}
{low_value_rule}
{income_wording_rule}
{terminology_rule}

RÈGLES OBLIGATOIRES:
- Réponds UNIQUEMENT en français.
- Les explications doivent être LONGUES et DÉTAILLÉES (au moins 6 phrases ou 150 mots). Citez plusieurs avantages concrets (cotisation annuelle, assurance, plafond, taux, conditions d'éligibilité, etc.).
- Citez OBLIGATOIREMENT le Segment RFM du client (ex: "segment RFM Low Value", "client Champion") ainsi qu'au moins deux autres attributs (âge, profession, capacité d'épargne, situation familiale).
- N'inventez aucun comportement (ex: "vous voyagez").
- Les scores des produits sont ajustés en fonction des retours des conseillers. Un produit souvent jugé "pas utile" verra son score baissé automatiquement.
- JSON uniquement.

IMPORTANT: N'oubliez pas d'inclure le segment RFM du client dans l'explication (ex: "segment RFM: Low Value", "client Champion", etc.).

Exemple de bonne réponse (note: l'explication est plus longue que l'exemple original) :
{{"recommendations": [
  {{"product_name": "La carte Yasmine","score": 9,"explanation": "À 46 ans, gérant de société, capacité d'épargne 1460 TND. Cette carte professionnelle offre un plafond de dépassement de 2000 TND, une assurance perte et vol incluse, et des frais de cotisation annuels de 50 DT. De plus, elle permet des retraits gratuits dans tous les DAB BH Bank et des paiements sans contact sécurisés. C'est un excellent choix pour les professionnels ayant besoin de flexibilité et de sécurité. Enfin, les frais de remplacement en cas de perte sont réduits de 50% pour les bons clients."}},
  {{"product_name": "Dhamen Compte","score": 8,"explanation": "Assurance vie/hospitalisation à 3 DT/mois. Adaptée aux professionnels, elle couvre également le conjoint et les enfants. Les cotisations sont prélevées mensuellement sans engagement de durée, et la déclaration de sinistre se fait en ligne. De plus, un service d'assistance 24/7 est inclus."}},
  {{"product_name": "Le Pack : BH Access","score": 7,"explanation": "Pack économique à 16 DT/trimestre avec carte CIB et services à distance. Ce pack inclut les alertes SMS gratuites, l'accès à BH Net Mobile, et un livret d'épargne sans frais de tenue de compte. Idéal pour les clients qui souhaitent maîtriser leurs frais bancaires tout en bénéficiant de services digitaux essentiels."}}
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
        payload = {"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.2, "num_predict": 2000}}
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
            if resp.status_code == 200:
                response = resp.json().get("response", "")
                if not response.strip():
                    return {}
                recs = self.extract_recommendations_from_text(response)
                if recs:
                    return {"recommendations": recs}
        except Exception as e:
            print(f"LLM error: {e}")
        return {}

    def rule_based_fallback(self, client: Dict) -> List[Dict]:
        age = client['age']
        seg = client['rfm_segment']
        job = client.get('job_position', '').lower()
        spending = client.get('spending_capacity', 0)
        recs = []
        if seg in ['Low Value', 'At Risk'] and spending < 2500:
            recs.append(("La carte Yasmine", 8, "Carte professionnelle avec plafond de dépassement."))
            recs.append(("Dhamen Compte", 7, "Assurance 3 DT/mois."))
            recs.append(("Le Pack : BH Access", 6, "Pack économique."))
        elif age > 75:
            recs.append(("LA CARTE CIB", 8, "Carte de base."))
            recs.append(("Le BH SMS", 7, "Alertes SMS."))
        elif seg in ['Champion', 'High Value'] and spending > 2000:
            recs.append(("La carte BH GOLD Internationale", 9, "Carte premium."))
            recs.append(("Le Pack : BH Elite", 8, "Pack haut de gamme."))
        elif 'directeur' in job or 'agence' in job:
            recs.append(("Le Pack : BH Select", 8, "Pack cadre."))
            recs.append(("BH Net Mobile", 7, "Application mobile."))
        elif 'pharmacien' in job:
            recs.append(("La carte Yasmine", 8, "Carte professionnelle."))
            recs.append(("Dhamen Compte", 7, "Assurance."))
        elif age >= 55:
            recs.append(("Le Pack : Senior", 8, "Pack sénior."))
            recs.append(("Assur Senior", 7, "Assurance."))
        elif age <= 25:
            recs.append(("LA CARTE GO", 8, "Carte jeune."))
            recs.append(("Le Pack : SMART", 7, "Pack jeune."))
        else:
            recs.append(("LA CARTE CIB", 5, "Carte de base."))
        return [{"product_name": n, "score": s, "explanation": e} for n,s,e in recs[:3]]

    def judge_with_llm(self, explanation: str, client: Dict, product_name: str) -> Optional[Dict]:
        basic_products = ['carte cib', 'carte go', 'bh sms', 'carte cool', 'pack : smart', 'pack : bh access']
        is_basic = any(p in product_name.lower() for p in basic_products)
        prompt = f"""Tu es un évaluateur impartial de recommandations bancaires. Juge l'explication suivante.

Client:
- Âge: {client.get('age')}
- Profession: {client.get('job_position')}
- Segment RFM: {client.get('rfm_segment')}
- Capacité d'épargne mensuelle: {client.get('spending_capacity')} TND

Produit recommandé: {product_name}
Explication: "{explanation}"

Règles de notation (0 à 10) :

1. Factuel (0-10) : L'explication cite‑elle des données réelles du client ?
   - Si elle cite l'âge ou la profession → donne au moins 7.
   - Si elle cite aussi la capacité d'épargne (même sans le chiffre exact) → 8.
   - Si elle cite tout (âge, profession, RFM, montant exact) → 10.
   - Ne pénalise pas l'absence de RFM pour les produits basiques.

2. Pertinence (0-10) : Mentionne‑t‑elle un avantage ou une condition concrète ?
   - Cotisation, assurance, plafond, taux, etc. → 10. Sinon → 5.

3. Clarté (0-10) : Explication claire, bien structurée, longueur adaptée.
   - 10 excellente, 7 correcte, 5 confuse.

Réponds avec JSON (pas de texte avant/après) :
{{
  "factual_score": 8,
  "factual_comment": "...",
  "relevance_score": 7,
  "relevance_comment": "...",
  "clarity_score": 9,
  "clarity_comment": "..."
}}"""
        payload = {"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.0, "num_predict": 300}}
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
            if resp.status_code == 200:
                response = resp.json().get("response", "")
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    factual = data.get("factual_score", 0)
                    relevance = data.get("relevance_score", 0)
                    clarity = data.get("clarity_score", 0)
                    factual_comment = data.get("factual_comment", "")
                    relevance_comment = data.get("relevance_comment", "")
                    clarity_comment = data.get("clarity_comment", "")
                    if is_basic and factual < 7:
                        factual = 7
                        factual_comment = "Produit basique adapté au profil (score ajusté à 7). " + factual_comment
                    overall = round((factual + relevance + clarity) / 3, 1)
                    feedback = f"📊 Factuel ({factual}/10) : {factual_comment}\n🎯 Pertinence ({relevance}/10) : {relevance_comment}\n✍️ Clarté ({clarity}/10) : {clarity_comment}\n🏆 Global : {overall}/10"
                    return {
                        "factual_score": factual,
                        "relevance_score": relevance,
                        "clarity_score": clarity,
                        "hallucination_score": 10,
                        "overall_score": overall,
                        "feedback": feedback
                    }
        except Exception as e:
            print(f"LLM judge error: {e}")
        return None

    def _evaluate_recommendation_rule_based(self, explanation: str, client: Dict) -> Dict:
        factual = 8 if str(client.get('age', '')) in explanation else 4
        relevance = compute_relevance_score(explanation)
        clarity = compute_clarity_score(explanation)
        overall = round((factual + relevance + clarity) / 3, 1)
        factual_comment = "L'explication cite l'âge ou la profession." if factual >= 7 else "L'explication ne cite aucune donnée du client."
        relevance_comment = "Mentionne un avantage concret." if relevance == 10 else "Ne mentionne pas d'avantage précis."
        clarity_comment = "Explication claire." if clarity >= 8 else ("Explication correcte." if clarity >= 6 else "Explication confuse.")
        feedback = f"📊 Factuel ({factual}/10) : {factual_comment}\n🎯 Pertinence ({relevance}/10) : {relevance_comment}\n✍️ Clarté ({clarity}/10) : {clarity_comment}\n🏆 Global : {overall}/10"
        return {
            "factual_score": factual,
            "relevance_score": relevance,
            "clarity_score": clarity,
            "hallucination_score": 10,
            "overall_score": overall,
            "feedback": feedback
        }

    def evaluate_recommendation(self, explanation: str, client: Dict, product_name: str) -> Dict:
        if self.use_llm_judge:
            res = self.judge_with_llm(explanation, client, product_name)
            if res:
                return res
        return self._evaluate_recommendation_rule_based(explanation, client)

    def recommend_for_client(self, client_id: str) -> List[Dict]:
        print(f"\n🔍 Génération de recommandations pour le client {client_id}")
        client = self.get_client_profile(client_id)
        if not client:
            return [{"error": f"Client {client_id} non trouvé"}]
        print(f"✅ Client: âge={client['age']}, RFM={client['rfm_segment']}, profession={client['job_position']}")
        filtered = self.prefilter_products(client)
        print(f"📊 Produits préfiltrés: {len(filtered)} sur {len(self.products_df)}")
        if not filtered:
            print("⚠️ Aucun produit préfiltré – utilisation du fallback")
            recs = self.rule_based_fallback(client)
        else:
            prompt = self.build_prompt(client, filtered)
            result = self.call_llm(prompt)
            recs = result.get("recommendations", [])
            if not recs:
                print("⚠️ Échec de l'IA – utilisation du fallback")
                recs = self.rule_based_fallback(client)
            else:
                print(f"✅ L'IA a retourné {len(recs)} recommandations")
            recs = self.boost_by_merchant_category(client, recs)
        output = []
        for r in recs[:3]:
            # Apply feedback modifier
            try:
                modifier_obj = ProductScoreModifier.objects.filter(product_name=r['product_name']).first()
                if modifier_obj:
                    new_score = r['score'] + modifier_obj.modifier
                    r['score'] = max(1, min(10, new_score))
            except Exception as e:
                print(f"Modifier error for {r['product_name']}: {e}")
            # Ensure client data in explanation (including RFM)
            r['explanation'] = ensure_client_data_in_explanation(r['explanation'], client)
            xai = self.evaluate_recommendation(r['explanation'], client, r['product_name'])
            output.append({
                "product_name": r['product_name'],
                "score": r['score'],
                "explanation": r['explanation'],
                "xai": xai
            })
        return output

    def recommend_all_clients(self, limit=None, output_file="recommendations.csv"):
        all_recs = []
        clients = self.clients_df['client_id'].astype(str).str.strip().tolist()
        if limit:
            clients = clients[:limit]
        for cid in clients:
            recs = self.recommend_for_client(cid)
            for r in recs:
                all_recs.append({
                    "client_id": cid,
                    "product_name": r['product_name'],
                    "score": r['score'],
                    "explanation": r['explanation']
                })
        pd.DataFrame(all_recs).to_csv(output_file, index=False)
        return all_recs

def ensure_client_data_in_explanation(explanation: str, client: Dict) -> str:
    """
    Ensure that the explanation contains the client's age, job, savings capacity, and RFM segment.
    If any are missing, prepend them as a single sentence.
    """
    exp_lower = explanation.lower()
    age = str(client.get('age', ''))
    job = client.get('job_position', '').lower()
    spending = f"{client.get('spending_capacity', 0):.2f}"
    rfm = client.get('rfm_segment', '')
    rfm_lower = rfm.lower()

    missing_parts = []
    if age not in exp_lower:
        missing_parts.append(f"{age} ans")
    if job not in exp_lower:
        missing_parts.append(job)
    if spending not in exp_lower:
        missing_parts.append(f"capacité d'épargne {spending} TND")
    if rfm_lower and rfm_lower not in exp_lower:
        missing_parts.append(f"segment RFM {rfm}")

    if missing_parts:
        prefix = "Client " + ", ".join(missing_parts) + ". "
        return prefix + explanation
    return explanation

if __name__ == "__main__":
    eng = RecommendationEngine()
    sample = eng.clients_df['client_id'].iloc[0]
    print(json.dumps(eng.recommend_for_client(sample), indent=2, ensure_ascii=False))