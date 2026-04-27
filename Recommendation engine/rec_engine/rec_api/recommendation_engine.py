import pandas as pd
import json
import requests
from .models import ClientProfile

class RecommendationEngine:
    def __init__(self, ollama_model="llama3:8b"):
        self.model = ollama_model
        self.url = "http://localhost:11434/api/generate"
        self.products_df = pd.read_csv('data/product_features.csv')
    
    def get_client_profile(self, client_id):
        try:
            client = ClientProfile.objects.get(client_id=client_id)
            return client
        except ClientProfile.DoesNotExist:
            return None
    
    def build_prompt(self, client, top_k=10):
        # Build product list (limit to top_k to keep prompt size manageable)
        products = self.products_df.head(top_k).to_dict('records')
        product_text = ""
        for p in products:
            product_text += f"- {p['name']} (Catégorie: {p['category']}, Sous-catégorie: {p['subcategory']})\n"
        
        prompt = f"""
Tu es un conseiller bancaire. Recommande des produits bancaires à un client en fonction de son profil.

Profil client:
- Nom: {client.full_name}
- Âge: {client.age}
- Situation familiale: {client.marital_status}
- Genre: {client.gender}
- Profession: {client.job_position}
- Lieu de résidence: {client.residence_location}
- Segment RFM: {client.rfm_segment}
- Score d'engagement: {client.engagement_score}/6
- Capacité de dépense moyenne mensuelle: {client.spending_capacity:.2f} TND
- Niveau d'activité (transactions/mois): {client.activity_level:.1f}

Produits disponibles:
{product_text}

Pour chaque produit recommandé, donne:
- nom du produit
- un score de pertinence (0-10)
- une explication en français liée au profil du client

Réponds uniquement en JSON valide, sans texte avant ou après, au format suivant:
{{
  "recommendations": [
    {{
      "product_name": "Nom du produit",
      "score": 8.5,
      "explanation": "Explication en français..."
    }}
  ]
}}
"""
        return prompt
    
    def get_recommendations(self, client_id, top_n=3):
        client = self.get_client_profile(client_id)
        if not client:
            return {"error": f"Client {client_id} not found"}
        
        prompt = self.build_prompt(client)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2}
        }
        try:
            response = requests.post(self.url, json=payload, timeout=90)
            if response.status_code == 200:
                result = response.json()
                answer = result.get('response', '')
                # Extract JSON from the answer (in case LLM adds extra text)
                import re
                json_match = re.search(r'\{.*\}', answer, re.DOTALL)
                if json_match:
                    recommendations = json.loads(json_match.group())
                    # Limit to top_n
                    recommendations['recommendations'] = recommendations.get('recommendations', [])[:top_n]
                    return recommendations
                else:
                    return {"error": "Invalid response format", "raw": answer}
            else:
                return {"error": f"Ollama error: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}