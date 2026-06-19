import requests
import re
import json
import os
import random
import math
from django.conf import settings

# ---------- FINANCIAL FORMULA HELPERS ----------
def calculate_pmt(principal, annual_rate, months):
    if annual_rate == 0 or months == 0:
        return principal / months if months > 0 else 0
    monthly_rate = annual_rate / 12 / 100
    if monthly_rate == 0:
        return principal / months
    pmt = principal * monthly_rate * (1 + monthly_rate)**months / ((1 + monthly_rate)**months - 1)
    return round(pmt, 2)

def calculate_roi(gain, cost):
    if cost == 0:
        return 0
    return round((gain - cost) / cost * 100, 1)

def calculate_clv(avg_monthly_margin, tenure_years, discount_rate_percent=10):
    if discount_rate_percent == 0:
        return avg_monthly_margin * tenure_years * 12
    discount_rate = discount_rate_percent / 100
    clv = avg_monthly_margin * tenure_years * 12 / (1 + discount_rate)
    return round(clv, 2)

# ---------- END FORMULA HELPERS ----------

def call_ollama(prompt, model=None):
    model = model or settings.OLLAMA_MODEL
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2500}
    }
    try:
        print(f"🔄 Calling Ollama with model: {model}")
        response = requests.post(url, json=payload, timeout=3000)
        response.raise_for_status()
        print("✅ Ollama responded")
        return response.json()['response'].strip()
    except Exception as e:
        print(f"❌ Erreur Ollama: {e}")
        return None

def get_catalogue_products():
    try:
        path = os.path.join(settings.BASE_DIR, 'product_catalog.json')
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        products = data.get('products', [])
        return [p.get('name', '').strip() for p in products if p.get('name')]
    except:
        return ["La carte CIB", "LA CARTE GO", "Assur Senior", "Dhamen Compte", "BH Net Mobile", "Le Pack : BH Access", "Crédit Auto BH", "Prêt Étudiant BH"]

def get_segment_defaults(segment):
    catalogue = get_catalogue_products()
    random_product = random.choice(catalogue) if catalogue else "La carte CIB"
    
    defaults = {
        'Jeunes Actifs': {
            'interpretation': 'Les Jeunes Actifs sont dynamiques, connectés et ouverts aux innovations. Ils recherchent des produits digitaux, des récompenses et de la flexibilité.',
            'product': 'Pack BH Active – compte premium avec cashback (2%) sur les achats, carte virtuelle, arrondis automatiques, et conseiller digital 24/7. Prix : 50 TND par an.',
            'modification': f'{random_product} : augmentation du plafond de paiement, ajout d\'une assurance voyage et d\'un programme de cashback.',
            'partnership': 'Carrefour Tunisie : 10% de réduction sur les courses pour les détenteurs du Pack BH Active.',
            'roadmap_new': 'Phase 1 (0-4 mois) : Étude de marché et conception. Phase 2 (4-8 mois) : Développement et tests. Phase 3 (8-12 mois) : Lancement national.',
            'roadmap_modif': 'Phase 1 (0-2 mois) : Analyse des impacts techniques. Phase 2 (2-4 mois) : Mise en œuvre. Phase 3 (4-6 mois) : Communication et formation.',
            'justification_extra': 'ROI positif dès la 2ème année grâce à une forte fidélisation.'
        },
        'Familles avec enfants': {
            'interpretation': 'Les familles recherchent des solutions globales, sécurisantes et économiques. Elles sont sensibles aux offres groupées et aux assurances.',
            'product': 'Pack BH Famille – compte joint avec 2 cartes gratuites, assurance scolaire, livret d\'épargne pour enfants, et réduction sur les crédits logement. Prix : 60 TND par an.',
            'modification': f'{random_product} : réduction des frais de gestion de 50% et ajout d\'une fonction "Budget Enfant" pour suivre les dépenses liées aux enfants.',
            'partnership': 'Carrefour Tunisie : 15% de réduction sur les produits de puériculture et d\'alimentation pour les familles.',
            'roadmap_new': 'Phase 1 (0-4 mois) : Analyse des besoins des familles. Phase 2 (4-8 mois) : Conception du pack. Phase 3 (8-12 mois) : Lancement en agence et en ligne.',
            'roadmap_modif': 'Phase 1 (0-2 mois) : Étude d\'impact. Phase 2 (2-4 mois) : Mise à jour des conditions. Phase 3 (4-6 mois) : Communication aux clients éligibles.',
            'justification_extra': 'Investissement initial compensé par une CLV élevée et un fort taux de rétention familial.'
        },
        'Retraités': {
            'interpretation': 'Les retraités privilégient la sécurité, la simplicité, et la réduction des frais. Ils apprécient les services d\'assistance et les contacts physiques.',
            'product': 'Pack Senior BH – compte sans frais de tenue, carte CIB avec assurance, service d\'assistance téléphonique 24/7, et réductions sur les transferts. Prix : 40 TND par an.',
            'modification': f'{random_product} : extension de la couverture à 80 ans, avec une réduction de 10% sur la cotisation annuelle pour les adhérents fidèles.',
            'partnership': 'Pharmacies de proximité : 15% de réduction sur les médicaments pour les détenteurs du Pack Senior BH.',
            'roadmap_new': 'Phase 1 (0-4 mois) : Communication personnalisée. Phase 2 (4-8 mois) : Déploiement du pack. Phase 3 (8-12 mois) : Suivi et ajustement.',
            'roadmap_modif': 'Phase 1 (0-2 mois) : Analyse des besoins. Phase 2 (2-4 mois) : Mise à jour du produit. Phase 3 (4-6 mois) : Communication et formation.',
            'justification_extra': 'ROI positif à long terme grâce à une forte fidélisation et une CLV élevée.'
        },
        'Nids Vides': {
            'interpretation': 'Les Nids Vides ont un pouvoir d\'achat élevé, recherchent la sécurité et l\'optimisation fiscale. Ils s\'intéressent aux placements et à la préparation de la retraite.',
            'product': 'Pack Sécurité BH – épargne garantie à 7%, avec conseiller dédié, placement diversifié, et simulation de retraite. Prix : 100 TND par an.',
            'modification': f'{random_product} : ajout d\'un système de paiement sécurisé et d\'une assurance annulation pour les voyages.',
            'partnership': 'Tunisie Telecom : forfaits internet et mobile avec réduction de 20% pour les souscripteurs.',
            'roadmap_new': 'Phase 1 (0-4 mois) : Étude des besoins. Phase 2 (4-8 mois) : Développement. Phase 3 (8-12 mois) : Lancement et suivi.',
            'roadmap_modif': 'Phase 1 (0-2 mois) : Analyse technique. Phase 2 (2-4 mois) : Mise en œuvre. Phase 3 (4-6 mois) : Formation des conseillers.',
            'justification_extra': 'Retour sur investissement rapide grâce à une clientèle à fort pouvoir d\'achat.'
        },
        'Étudiants': {
            'interpretation': 'Les étudiants sont un segment clé pour BH Bank, car ils représentent une opportunité de création d\'une clientèle loyale et durable. Ils sont sensibles aux prix et ouverts aux innovations digitales.',
            'product': 'Pack BH Étudiant – compte sans frais, carte GO avec cashback, prêt étudiant à taux zéro, et accès à des offres partenaires. Prix : 0 TND (gratuit).',
            'modification': 'LA CARTE GO : augmentation du plafond de paiement à 500 TND et ajout de réductions chez les commerçants partenaires.',
            'partnership': 'Universités : offres de bienvenue pour les nouveaux étudiants, avec des réductions sur les frais de tenue de compte.',
            'roadmap_new': 'Phase 1 (0-4 mois) : Conception du pack étudiant. Phase 2 (4-8 mois) : Développement. Phase 3 (8-12 mois) : Lancement national.',
            'roadmap_modif': 'Phase 1 (0-2 mois) : Analyse des besoins des étudiants. Phase 2 (2-4 mois) : Mise à jour de LA CARTE GO. Phase 3 (4-6 mois) : Communication dans les universités.',
            'justification_extra': 'ROI positif à long terme grâce à la fidélisation des étudiants dès leur entrée dans la vie active.'
        },
        'Professionnels': {
            'interpretation': 'Les professionnels recherchent des solutions flexibles, des crédits adaptés, et une gestion de trésorerie simplifiée.',
            'product': 'Pack BH Pro – compte professionnel avec découvert autorisé, carte Yasmine avec plafond élevé, gestion de trésorerie, et conseiller dédié. Prix : 120 TND par an.',
            'modification': f'{random_product} : augmentation du plafond de paiement et ajout d\'une assurance perte d\'exploitation.',
            'partnership': 'Centre d\'affaires : réductions sur les services de conseil et de formation pour les entrepreneurs.',
            'roadmap_new': 'Phase 1 (0-4 mois) : Analyse des besoins. Phase 2 (4-8 mois) : Conception. Phase 3 (8-12 mois) : Lancement et suivi.',
            'roadmap_modif': 'Phase 1 (0-2 mois) : Étude des impacts. Phase 2 (2-4 mois) : Mise à jour. Phase 3 (4-6 mois) : Formation et communication.',
            'justification_extra': 'ROI rapide grâce à une clientèle à forte capacité de génération de revenus.'
        },
        '': {
            'interpretation': 'Opportunité de développement produit ciblé pour ce segment.',
            'product': 'Pack BH Access – compte de base avec carte CIB, BH Net Mobile, et alertes SMS. Prix : 30 TND par an.',
            'modification': 'La carte CIB : réduction des frais de gestion et ajout d\'un service d\'assistance.',
            'partnership': 'Carrefour : offres exclusives pour les clients.',
            'roadmap_new': 'Phase 1 (0-4 mois) : Étude de marché. Phase 2 (4-8 mois) : Développement. Phase 3 (8-12 mois) : Lancement national.',
            'roadmap_modif': 'Phase 1 (0-2 mois) : Analyse. Phase 2 (2-4 mois) : Mise en œuvre. Phase 3 (4-6 mois) : Communication.',
            'justification_extra': 'Projet à forte rentabilité sur le long terme.'
        }
    }
    return defaults.get(segment, defaults[''])

def is_generic_partnership(text: str) -> bool:
    """Detect if the partnership text is too generic."""
    generic_phrases = [
        'offres exclusives',
        'réductions pour les clients',
        'offres et réductions',
        'exclusivités',
        'avantages pour les clients'
    ]
    text_lower = text.lower()
    if re.search(r'\d+%', text):
        return False
    for phrase in generic_phrases:
        if phrase in text_lower:
            return True
    return False

def enrich_interpretation_with_trends(interpretation: str, stats: dict, trends: dict, segment: str) -> str:
    """
    Ensure the interpretation mentions key negative trends if they are present in the data.
    """
    # Extract key metrics
    income_trend = trends.get('income', 0)
    savings_trend = trends.get('savings', 0)
    spending_trend = trends.get('spending', 0)
    online_trend = trends.get('online', 0)
    mobile_trend = trends.get('mobile', 0)
    growth_sim = stats.get('growth_simulator', 0)
    
    # Build a list of notable negative trends
    negative_notes = []
    if income_trend < 0:
        negative_notes.append(f"une baisse du revenu de {abs(income_trend):.1f}%")
    if savings_trend < 0:
        negative_notes.append(f"une baisse de l'épargne de {abs(savings_trend):.1f}%")
    if spending_trend < 0:
        negative_notes.append(f"une baisse des dépenses de {abs(spending_trend):.1f}%")
    if online_trend < 0:
        negative_notes.append(f"une baisse de l'activité en ligne de {abs(online_trend):.1f}%")
    
    # Also check if the interpretation already mentions these trends
    interpretation_lower = interpretation.lower()
    already_mentions = False
    for note in negative_notes:
        # Check if the key words appear (e.g., "baisse du revenu")
        key_words = note.split(' ')[:3]  # e.g., ["une", "baisse", "du"]
        if any(word in interpretation_lower for word in key_words):
            already_mentions = True
            break
    
    # If there are negative trends and the interpretation doesn't mention them, add them
    if negative_notes and not already_mentions:
        # Find a good insertion point (after the first sentence)
        sentences = interpretation.split('.')
        if len(sentences) > 1:
            # Insert after the first sentence
            first_sent = sentences[0]
            rest = '.'.join(sentences[1:])
            if rest:
                insertion = f". Cependant, les données montrent également {', '.join(negative_notes)}."
                return first_sent + insertion + '.' + rest
            else:
                insertion = f" Cependant, les données montrent également {', '.join(negative_notes)}."
                return first_sent + insertion
        else:
            # Only one sentence, append
            insertion = f" Cependant, les données montrent également {', '.join(negative_notes)}."
            return interpretation + insertion
    
    return interpretation

def generate_innovation_recommendation(segment, stats, trends, growth_simulator=None):
    # Calculate financial indicators
    avg_income = stats.get('avg_income', 2500)
    avg_tenure = stats.get('avg_tenure', 10)
    principal_example = 10000
    annual_rate_example = 8 + 2.5
    pmt_example = calculate_pmt(principal_example, annual_rate_example, 36)
    margin_estimate = avg_income * 0.02
    clv_estimate = calculate_clv(margin_estimate, avg_tenure, 10)
    roi_estimate = calculate_roi(avg_income * 12 * 0.1, avg_income * 3)
    
    trend_text = ", ".join([f"{k.replace('avg_','')} {v}%" for k,v in trends.items() if v != 0])
    defaults = get_segment_defaults(segment)
    catalogue = get_catalogue_products()
    catalogue_text = "\n".join([f"- {p}" for p in catalogue[:15]]) if catalogue else "Catalogue non disponible"
    
    # --- REINFORCED PROMPT FOR 5/5 (Gemma 2 9B compatible) ---
    prompt = f"""Tu es un expert en innovation bancaire pour BH Bank (Tunisie). Propose des recommandations stratégiques pour le segment : {segment}.

**DONNÉES RÉELLES DU SEGMENT :**
- Clients : {stats['count']}
- Âge moyen : {stats.get('avg_age', 'N/A')} ans
- Revenu moyen : {stats.get('avg_income', 'N/A')} TND
- Dépenses : {stats.get('avg_spending', 'N/A')} TND
- Épargne : {stats.get('avg_savings', 'N/A')} TND
- Tendances réelles (T/T) : {trend_text}
- Croissance simulée : {growth_simulator or 'Non spécifié'}%

**PRODUITS EXISTANTS (pour la MODIFICATION) :**
{catalogue_text}

**INDICATEURS FINANCIERS ESTIMÉS (à utiliser dans la JUSTIFICATION) :**
- PMT (10k TND, 36 mois, 10.5%) : {pmt_example} TND
- CLV estimée : {clv_estimate:.2f} TND
- ROI estimé : {roi_estimate}%

**RÈGLES OBLIGATOIRES POUR UN RAPPORT 5/5 :**
1. Réponds UNIQUEMENT en français.
2. INTERPRÉTATION STRATÉGIQUE : 2-3 phrases basées sur les données réelles. Mentionne TOUTES les tendances négatives si elles existent (baisse du revenu, de l'épargne, etc.).
3. NOUVEAU PRODUIT : Nom évocateur + 5 caractéristiques précises + PRIX clair (ex: 50 TND par an).
4. MODIFICATION : Cite OBLIGATOIREMENT un produit EXISTANT du catalogue (nom exact) + amélioration précise.
5. PARTENARIAT : Marque EXTERNE + valeur ajoutée CONCRÈTE avec un POURCENTAGE (ex: "15% de réduction sur...").
6. JUSTIFICATION : OBLIGATOIREMENT : ROI (%), CLV (TND), et 3 KPIs avec chiffres (ex: taux d'adoption 30%, nombre de souscriptions 500+, taux de rétention 85%).
   **Si le ROI est négatif, explique POURQUOI (coûts d'acquisition) et indique quand il devient positif (ex: "dès la 3ème année").**
7. PLAN DE DÉPLOIEMENT : SÉPARÉ en deux parties : "NOUVEAU PRODUIT" (3 phases, 12-18 mois au total) et "MODIFICATION" (3 phases, 3-6 mois au total). Donne des délais et des actions concrètes.
8. RISQUES : 2 risques + pour CHAQUE risque une stratégie de mitigation spécifique.

**STRUCTURE OBLIGATOIRE (sans numéros) :**
INTERPRÉTATION STRATÉGIQUE :
NOUVEAU PRODUIT :
MODIFICATION :
PARTENARIAT :
JUSTIFICATION :
PLAN DE DÉPLOIEMENT :
RISQUES :

Commence ta réponse directement par "INTERPRÉTATION STRATÉGIQUE :"."""
    
    llm_response = call_ollama(prompt)
    
    # Start with defaults
    result = {
        'trend_interpretation': defaults['interpretation'],
        'product': defaults['product'],
        'modification': defaults['modification'],
        'partnership': defaults['partnership'],
        'justification': f"ROI estimé : {roi_estimate}%. CLV projetée : {clv_estimate:.2f} TND. PMT (10k TND, 36 mois) : {pmt_example} TND. KPIs : taux d'adoption 30%, nombre de souscriptions 500+ dans les 12 mois, taux de rétention 85%.",
        'roadmap': f"**NOUVEAU PRODUIT :**\n{defaults['roadmap_new']}\n\n**MODIFICATION :**\n{defaults['roadmap_modif']}",
        'risks': "Risque 1 : Adoption lente par les clients. Mitigation : campagne de communication ciblée et offres de lancement attractives. Risque 2 : Concurrence agressive. Mitigation : positionnement différenciant et amélioration continue du produit."
    }
    
    if not llm_response:
        print("⚠️ LLM failed, using defaults.")
        # Even with default, enrich interpretation with trends
        result['trend_interpretation'] = enrich_interpretation_with_trends(result['trend_interpretation'], stats, trends, segment)
        return result
    
    # --- ROBUST PARSING ---
    patterns = {
        'trend_interpretation': r'(?:INTERPRÉTATION STRATÉGIQUE|1\.\s*INTERPRÉTATION STRATÉGIQUE)\s*:?\s*(.*?)(?=(?:NOUVEAU PRODUIT|2\.)|$)',
        'product': r'(?:NOUVEAU PRODUIT|2\.\s*NOUVEAU PRODUIT)\s*:?\s*(.*?)(?=(?:MODIFICATION|3\.)|$)',
        'modification': r'(?:MODIFICATION|3\.\s*MODIFICATION)\s*:?\s*(.*?)(?=(?:PARTENARIAT|4\.)|$)',
        'partnership': r'(?:PARTENARIAT|4\.\s*PARTENARIAT)\s*:?\s*(.*?)(?=(?:JUSTIFICATION|5\.)|$)',
        'justification': r'(?:JUSTIFICATION|5\.\s*JUSTIFICATION)\s*:?\s*(.*?)(?=(?:PLAN DE DÉPLOIEMENT|6\.)|$)',
        'roadmap': r'(?:PLAN DE DÉPLOIEMENT|6\.\s*PLAN DE DÉPLOIEMENT)\s*:?\s*(.*?)(?=(?:RISQUES|7\.)|$)',
        'risks': r'(?:RISQUES|7\.\s*RISQUES)\s*:?\s*(.*?)(?=##|$)'
    }
    
    parsed_count = 0
    for key, pattern in patterns.items():
        match = re.search(pattern, llm_response, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            if content and len(content) > 10:
                content = content.replace('\n', ' ').strip()
                result[key] = content
                parsed_count += 1
    
    if parsed_count == 0:
        result['trend_interpretation'] = llm_response[:500]
        print("⚠️ No sections parsed, using raw LLM response as interpretation.")
    
    print(f"✅ Parsed {parsed_count}/7 sections from LLM")
    
    # --- POST-PROCESSING ---
    
    # 0. ENRICH INTERPRETATION WITH MISSING TRENDS
    result['trend_interpretation'] = enrich_interpretation_with_trends(
        result['trend_interpretation'], stats, trends, segment
    )
    
    # 1. Ensure modification uses catalogue product
    if result['modification'] and catalogue:
        has_catalogue_product = False
        for prod in catalogue:
            if prod.lower() in result['modification'].lower():
                has_catalogue_product = True
                break
        if not has_catalogue_product:
            first_product = catalogue[0] if catalogue else "La carte CIB"
            improvement = result['modification']
            result['modification'] = f"{first_product} : {improvement}"
    
    # 2. Ensure partnership is external AND specific (with percentage)
    if result['partnership']:
        if 'BH' in result['partnership'] or 'bh' in result['partnership'].lower():
            result['partnership'] = defaults['partnership']
        elif is_generic_partnership(result['partnership']):
            result['partnership'] = defaults['partnership']
        elif not re.search(r'\d+%', result['partnership']):
            segment_percentages = {
                'Jeunes Actifs': '10%',
                'Familles avec enfants': '15%',
                'Retraités': '15%',
                'Nids Vides': '20%',
                'Étudiants': '10%',
                'Professionnels': '12%'
            }
            pct = segment_percentages.get(segment, '10%')
            result['partnership'] = result['partnership'] + f" : {pct} de réduction pour les clients du segment."
    
    # 3. Ensure justification explains negative ROI if present
    if 'ROI' in result['justification'] and '-' in result['justification']:
        if "explique" not in result['justification'].lower() and "acquisition" not in result['justification'].lower():
            result['justification'] += " (Le ROI négatif s'explique par les coûts d'acquisition initiaux. Le retour sur investissement devient positif dès la 3ème année grâce à une CLV élevée et une forte fidélisation.)"
    
    # 4. Ensure roadmap has clear separation
    if result['roadmap'] and ('NOUVEAU PRODUIT' not in result['roadmap'].upper() or 'MODIFICATION' not in result['roadmap'].upper()):
        result['roadmap'] = f"**NOUVEAU PRODUIT :**\n{defaults['roadmap_new']}\n\n**MODIFICATION :**\n{defaults['roadmap_modif']}"
    
    return result