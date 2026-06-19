import requests
import re
import json
import os
import random
import math
from django.conf import settings

# ═══════════════════════════════════════════════════════════════
# SEGMENT MAPPING
# ═══════════════════════════════════════════════════════════════
SEGMENT_MAP = {
    'YoungProfessional': 'Jeunes Actifs',
    'FamilyWithChildren': 'Familles avec enfants',
    'EmptyNester': 'Nids Vides',
    'HighNetWorth': 'Hauts revenus',
    'Entrepreneur': 'Professionnels',
    'Student': 'Étudiants',
    'Retiree': 'Retraités',
}

# Cards that legitimately belong to each segment
SEGMENT_CARDS = {
    'Jeunes Actifs':         ['carte cool', 'bh active', 'carte go', 'carte cib'],
    'Étudiants':             ['carte go', 'prêt étudiant', 'carte cib', 'carte bh scolarite'],
    'Familles avec enfants': ['carte cib', 'pack bh famille', 'dhamen'],
    'Nids Vides':            ['carte yasmine', 'carte sérénité', 'pack sécurité', 'carte cib'],
    'Hauts revenus':         ['bh prestige', 'carte yasmine', 'carte cib'],
    'Professionnels':        ['carte yasmine', 'pack bh pro', 'carte cib'],
    'Retraités':             ['carte cib', 'pack senior', 'assur senior'],
}

# Segment-specific partnership discount percentages
SEGMENT_PARTNERSHIP_PCT = {
    'Jeunes Actifs':         '10%',
    'Familles avec enfants': '15%',
    'Retraités':             '15%',
    'Nids Vides':            '20%',
    'Étudiants':             '10%',
    'Professionnels':        '12%',
    'Hauts revenus':         '10%',
}

# ═══════════════════════════════════════════════════════════════
# FINANCIAL FORMULA HELPERS
# ═══════════════════════════════════════════════════════════════
def calculate_pmt(principal: float, annual_rate: float, months: int) -> float:
    if months == 0:
        return 0.0
    if annual_rate == 0:
        return round(principal / months, 2)
    r = annual_rate / 12 / 100
    pmt = principal * r * (1 + r) ** months / ((1 + r) ** months - 1)
    return round(pmt, 2)


def calculate_roi(gain: float, cost: float) -> float:
    if cost == 0:
        return 0.0
    return round((gain - cost) / cost * 100, 1)


def calculate_clv(avg_monthly_margin: float, tenure_years: float,
                  discount_rate_percent: float = 10.0) -> float:
    if discount_rate_percent == 0:
        return round(avg_monthly_margin * tenure_years * 12, 2)
    r = discount_rate_percent / 100
    clv = avg_monthly_margin * tenure_years * 12 / (1 + r)
    return round(clv, 2)


# ═══════════════════════════════════════════════════════════════
# OLLAMA CALL
# ═══════════════════════════════════════════════════════════════
def call_ollama(prompt: str, model: str = None) -> str | None:
    model = model or settings.OLLAMA_MODEL
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2800},
    }
    try:
        print(f"🔄 Calling Ollama [{model}]")
        r = requests.post(url, json=payload, timeout=3000)
        r.raise_for_status()
        print("✅ Ollama responded")
        return r.json()["response"].strip()
    except Exception as e:
        print(f"❌ Ollama error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# CATALOGUE
# ═══════════════════════════════════════════════════════════════
def get_catalogue_products() -> list[str]:
    try:
        path = os.path.join(settings.BASE_DIR, "product_catalog.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [p.get("name", "").strip() for p in data.get("products", []) if p.get("name")]
    except Exception:
        return [
            "La carte CIB", "LA CARTE GO", "LA CARTE COOL", "Assur Senior",
            "Dhamen Compte", "BH Net Mobile", "Le Pack : BH Access",
            "Crédit Auto BH", "Prêt Étudiant BH", "La Carte Yasmine",
            "La carte BH SCOLARITE",
        ]


# ═══════════════════════════════════════════════════════════════
# SEGMENT DEFAULTS
# ═══════════════════════════════════════════════════════════════
def get_segment_defaults(segment_key: str) -> dict:
    segment = SEGMENT_MAP.get(segment_key, "")
    catalogue = get_catalogue_products()
    random_product = random.choice(catalogue) if catalogue else "La carte CIB"

    defaults = {
        "Jeunes Actifs": {
            "interpretation": (
                "Les Jeunes Actifs sont dynamiques, connectés et ouverts aux innovations. "
                "Ils recherchent des produits digitaux, des récompenses et de la flexibilité financière."
            ),
            "product": (
                "Pack BH Active – compte premium avec cashback 2% sur les achats en ligne, "
                "carte virtuelle instantanée, arrondis automatiques vers l'épargne, "
                "conseiller digital 24/7 et assurance mobile incluse. Prix : 50 TND par an."
            ),
            "modification": (
                "LA CARTE COOL : augmentation du plafond de paiement à 2 000 TND, "
                "ajout d'un cashback 1,5% sur les achats en ligne et d'une assurance mobile."
            ),
            "partnership": (
                "Decathlon Tunisie : 10% de réduction sur tous les équipements sportifs "
                "pour les porteurs de la carte BH Active."
            ),
            "roadmap_new": (
                "Phase 1 (mois 1-4) : Étude de marché, UX design et validation produit. "
                "Phase 2 (mois 4-10) : Développement technique et tests pilotes. "
                "Phase 3 (mois 10-14) : Lancement national avec campagne digitale ciblée."
            ),
            "roadmap_modif": (
                "Phase 1 (mois 1-2) : Analyse d'impact technique et validation conformité. "
                "Phase 2 (mois 2-4) : Déploiement système et mise à jour des supports. "
                "Phase 3 (mois 4-6) : Communication clients et suivi des souscriptions."
            ),
        },
        "Familles avec enfants": {
            "interpretation": (
                "Les familles recherchent des solutions globales, sécurisantes et économiques, "
                "sensibles aux offres groupées et à la protection de leurs proches."
            ),
            "product": (
                "Pack BH Famille – compte joint avec 2 cartes gratuites, assurance scolaire, "
                "livret d'épargne enfant à 4%, alertes dépenses et réduction 10% sur les crédits logement. "
                "Prix : 60 TND par an."
            ),
            "modification": (
                f"{random_product} : réduction des frais de gestion de 50% et ajout d'une "
                "fonction 'Budget Enfant' pour catégoriser les dépenses liées aux enfants."
            ),
            "partnership": (
                "Carrefour Tunisie : 15% de réduction sur les produits de puériculture "
                "et d'alimentation pour les porteurs du Pack BH Famille."
            ),
            "roadmap_new": (
                "Phase 1 (mois 1-4) : Analyse des besoins familiaux et conception du pack. "
                "Phase 2 (mois 4-10) : Développement et tests avec panel de familles. "
                "Phase 3 (mois 10-14) : Lancement en agence et en ligne."
            ),
            "roadmap_modif": (
                "Phase 1 (mois 1-2) : Étude d'impact et validation juridique. "
                "Phase 2 (mois 2-4) : Mise à jour des conditions tarifaires. "
                "Phase 3 (mois 4-6) : Communication aux clients éligibles."
            ),
        },
        "Retraités": {
            "interpretation": (
                "Les retraités privilégient la sécurité, la simplicité et la réduction des frais. "
                "Ils apprécient les services d'assistance physique et les contacts humains."
            ),
            "product": (
                "Pack Senior BH – compte sans frais de tenue, carte CIB avec assurance hospitalisation, "
                "assistance téléphonique 24/7, réductions sur les transferts et alertes SMS gratuites. "
                "Prix : 40 TND par an."
            ),
            "modification": (
                f"{random_product} : extension de la couverture jusqu'à 80 ans avec "
                "réduction de 10% sur la cotisation pour les adhérents fidèles (+5 ans)."
            ),
            "partnership": (
                "Pharmacies de proximité partenaires BH : 15% de réduction sur les médicaments "
                "pour les porteurs du Pack Senior BH."
            ),
            "roadmap_new": (
                "Phase 1 (mois 1-4) : Conception du pack et formation des conseillers en agence. "
                "Phase 2 (mois 4-10) : Déploiement progressif dans les agences à forte densité senior. "
                "Phase 3 (mois 10-14) : Suivi de satisfaction et ajustements."
            ),
            "roadmap_modif": (
                "Phase 1 (mois 1-2) : Analyse des besoins et validation actuarielle. "
                "Phase 2 (mois 2-4) : Mise à jour du produit et des systèmes. "
                "Phase 3 (mois 4-6) : Communication personnalisée aux clients concernés."
            ),
        },
        "Nids Vides": {
            "interpretation": (
                "Les Nids Vides disposent d'un fort pouvoir d'achat et recherchent sécurité "
                "financière et optimisation de leur patrimoine en vue de la retraite."
            ),
            "product": (
                "Pack Sérénité BH – épargne garantie à 7%, conseiller patrimonial dédié, "
                "placement diversifié (actions, obligations, immobilier), "
                "simulation de retraite en ligne et assurance vie incluse. Prix : 100 TND par an."
            ),
            "modification": (
                "La Carte Yasmine : augmentation du plafond de crédit à 20 000 TND "
                "et intégration d'un paiement sans contact NFC avec assurance annulation voyage."
            ),
            "partnership": (
                "Tunisie Telecom : 20% de réduction sur les forfaits internet et mobile premium "
                "pour les porteurs du Pack Sérénité BH."
            ),
            "roadmap_new": (
                "Phase 1 (mois 1-4) : Conception du pack patrimonial et validation réglementaire. "
                "Phase 2 (mois 4-10) : Développement de l'outil de simulation retraite et tests. "
                "Phase 3 (mois 10-14) : Lancement avec événements VIP en agences."
            ),
            "roadmap_modif": (
                "Phase 1 (mois 1-2) : Analyse d'impact technique et conformité NFC. "
                "Phase 2 (mois 2-4) : Déploiement et mise à jour des terminaux. "
                "Phase 3 (mois 4-6) : Formation conseillers et communication clients."
            ),
        },
        "Étudiants": {
            "interpretation": (
                "Les étudiants représentent le vivier de la future clientèle fidèle de BH Bank. "
                "Sensibles aux prix et très connectés, ils sont ouverts aux solutions 100% digitales."
            ),
            "product": (
                "Pack BH Étudiant – compte sans frais, LA CARTE GO avec cashback 1% sur les achats, "
                "prêt étudiant à taux zéro jusqu'à 5 000 TND, accès BH Net Mobile gratuit. "
                "Prix : 0 TND (gratuit)."
            ),
            "modification": (
                "La carte BH SCOLARITE : augmentation du plafond de paiement à 6 000 TND "
                "et réduction du taux d'intérêt annuel à 6%."
            ),
            "partnership": (
                "Universités partenaires BH : 0 TND de frais de tenue de compte la 1ère année "
                "et 10% de réduction sur les fournitures scolaires chez les libraires partenaires."
            ),
            "roadmap_new": (
                "Phase 1 (mois 1-4) : Conception du pack et partenariats universitaires. "
                "Phase 2 (mois 4-10) : Développement digital et tests sur campus pilotes. "
                "Phase 3 (mois 10-14) : Lancement national en début d'année universitaire."
            ),
            "roadmap_modif": (
                "Phase 1 (mois 1-2) : Analyse des besoins étudiants et négociation partenaires. "
                "Phase 2 (mois 2-4) : Mise à jour de LA CARTE GO et intégration partenaires. "
                "Phase 3 (mois 4-6) : Communication dans les universités et réseaux sociaux."
            ),
        },
        "Professionnels": {
            "interpretation": (
                "Les professionnels et entrepreneurs recherchent flexibilité, crédits adaptés "
                "et outils de gestion de trésorerie performants pour leur activité."
            ),
            "product": (
                "Pack BH Pro – compte professionnel avec découvert autorisé jusqu'à 30 000 TND, "
                "La Carte Yasmine avec plafond 10 000 TND, tableau de bord trésorerie en ligne "
                "et conseiller dédié. Prix : 120 TND par an."
            ),
            "modification": (
                f"{random_product} : augmentation du plafond de paiement à 15 000 TND "
                "et ajout d'une assurance perte d'exploitation jusqu'à 50 000 TND."
            ),
            "partnership": (
                "Centre d'Affaires de Tunis : 12% de réduction sur les services de conseil "
                "juridique et de formation pour les porteurs du Pack BH Pro."
            ),
            "roadmap_new": (
                "Phase 1 (mois 1-4) : Analyse des besoins des TPE/PME et conception du pack. "
                "Phase 2 (mois 4-10) : Développement du dashboard trésorerie et tests. "
                "Phase 3 (mois 10-14) : Lancement avec roadshow dans les zones d'activités."
            ),
            "roadmap_modif": (
                "Phase 1 (mois 1-2) : Étude d'impact et validation assurance. "
                "Phase 2 (mois 2-4) : Mise à jour produit et formation équipes. "
                "Phase 3 (mois 4-6) : Communication et suivi des souscriptions."
            ),
        },
        "Hauts revenus": {
            "interpretation": (
                "Les clients à hauts revenus recherchent l'excellence, des services exclusifs "
                "et une gestion patrimoniale sur mesure avec une relation conseiller privilégiée."
            ),
            "product": (
                "BH Prestige – carte métal avec concierge 24/7, accès VIP lounges dans 1 200 aéroports, "
                "assurance tous risques voyages, programme de fidélité premium et gestionnaire de patrimoine dédié. "
                "Prix : 150 TND par an."
            ),
            "modification": (
                f"{random_product} : intégration du paiement sans contact NFC premium "
                "et assurance voyage étendue avec couverture rapatriement jusqu'à 500 000 TND."
            ),
            "partnership": (
                "Airbnb : 10% de réduction sur les locations premium pour les détenteurs de BH Prestige."
            ),
            "roadmap_new": (
                "Phase 1 (mois 1-4) : Conception du produit et sélection des partenaires VIP. "
                "Phase 2 (mois 4-10) : Développement et tests avec panel de clients premium. "
                "Phase 3 (mois 10-14) : Lancement VIP avec événement de prestige."
            ),
            "roadmap_modif": (
                "Phase 1 (mois 1-2) : Analyse technique et validation des assureurs. "
                "Phase 2 (mois 2-4) : Déploiement et mise à jour des cartes existantes. "
                "Phase 3 (mois 4-6) : Communication personnalisée et suivi conseiller."
            ),
        },
        "": {
            "interpretation": "Opportunité de développement produit ciblé pour ce segment.",
            "product": (
                "Pack BH Access – compte de base avec carte CIB, BH Net Mobile et alertes SMS. "
                "Prix : 30 TND par an."
            ),
            "modification": (
                "La carte CIB : réduction des frais de gestion de 30% "
                "et ajout d'un service d'assistance téléphonique."
            ),
            "partnership": (
                "Jumia Tunisie : 10% de réduction sur les achats en ligne "
                "pour les porteurs de la carte CIB BH Bank."
            ),
            "roadmap_new": (
                "Phase 1 (mois 1-4) : Étude de marché et conception. "
                "Phase 2 (mois 4-10) : Développement et tests. "
                "Phase 3 (mois 10-14) : Lancement national."
            ),
            "roadmap_modif": (
                "Phase 1 (mois 1-2) : Analyse. "
                "Phase 2 (mois 2-4) : Mise en œuvre. "
                "Phase 3 (mois 4-6) : Communication."
            ),
        },
    }
    return defaults.get(segment, defaults[""])


# ═══════════════════════════════════════════════════════════════
# TEXT CLEANING HELPERS
# ═══════════════════════════════════════════════════════════════
def clean_llm_artifacts(text: str) -> str:
    text = re.sub(r'#+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\*\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fix_roi_year_reference(text: str) -> str:
    text = re.sub(r"dès\s+(?:l[''']année\s+)?(202\d)", "dès la 2ème année", text, flags=re.IGNORECASE)
    text = re.sub(r"en\s+(202\d)", "en année 2", text, flags=re.IGNORECASE)
    return text


def clean_modification_text(modification: str, catalogue: list, segment: str) -> str:
    """
    Remove markdown leftovers and duplicate product names.
    NOW HANDLES VARIATIONS like "Carte BH SCOLARITE" vs "LA CARTE SCOLARITE".
    """
    # 1. Strip common markdown labels
    
    modification = re.sub(r'\*\*Produit concerné\*\*:\s*', '', modification, flags=re.IGNORECASE)
    modification = re.sub(r'\*\*Amélioration\*\*:\s*', '', modification, flags=re.IGNORECASE)
    modification = re.sub(r'\*\*Modification\*\*:\s*', '', modification, flags=re.IGNORECASE)
    modification = re.sub(r'\*\*Améliorations?\*\*:\s*', '', modification, flags=re.IGNORECASE)
    # Remove any remaining Markdown bold/italic
    modification = re.sub(r'\*\*([^*]+)\*\*', r'\1', modification)
    modification = re.sub(r'__([^_]+)__', r'\1', modification)

    # 2. Normalize the text for matching: convert to lowercase
    mod_lower = modification.lower()

    # 3. Find matching catalogue products (with flexible matching)
    # Build a list of (catalogue_name, normalized_lower_name)
    normalized_catalogue = []
    for prod in catalogue:
        # Remove "BH" and normalize for matching
        normalized = re.sub(r'bh\s*', '', prod, flags=re.IGNORECASE).strip().lower()
        normalized_catalogue.append((prod, normalized))

    # Find all matches
    mentioned = []
    for prod, norm_prod in normalized_catalogue:
        # Check if the normalized product name appears in the modification text
        if norm_prod in mod_lower:
            mentioned.append(prod)
        # Also check if the original product name appears (without normalization)
        elif prod.lower() in mod_lower:
            mentioned.append(prod)

    # Remove duplicates while preserving order
    seen = set()
    mentioned = [x for x in mentioned if not (x in seen or seen.add(x))]

    # If more than one product is mentioned, pick the best one
    if len(mentioned) > 1:
        segment_label = SEGMENT_MAP.get(segment, "")
        allowed = SEGMENT_CARDS.get(segment_label, [])
        kept = None
        for prod in mentioned:
            prod_lower = prod.lower()
            if any(a in prod_lower for a in allowed):
                kept = prod
                break
        if kept is None:
            # Fallback: take the one that appears last (usually the intended one)
            kept = mentioned[-1]
        # Remove all other product names from the text
        for prod in mentioned:
            if prod != kept:
                # Remove the product name and any preceding punctuation/space
                modification = re.sub(rf'\b{re.escape(prod)}\b\s*[:;,\s]*', '', modification, flags=re.IGNORECASE)
                modification = re.sub(rf'\b{re.escape(prod)}\b', '', modification, flags=re.IGNORECASE)
        # Ensure the kept product name appears at the beginning
        modification = re.sub(rf'^{re.escape(kept)}\s*[:;,\s]*', '', modification, flags=re.IGNORECASE)
        modification = f"{kept} : {modification.strip()}"
        return modification.strip()

    # If exactly one product is mentioned, ensure it's at the start
    if len(mentioned) == 1:
        prod = mentioned[0]
        if not modification.lower().startswith(prod.lower()):
            modification = re.sub(rf'{re.escape(prod)}\s*[:;,\s]*', '', modification, flags=re.IGNORECASE)
            modification = f"{prod} : {modification.strip()}"
        return modification

    # No product mentioned – we'll inject one later
    return modification


# ═══════════════════════════════════════════════════════════════
# PARTNERSHIP VALIDATION
# ═══════════════════════════════════════════════════════════════
_GENERIC_PHRASES = [
    'offres exclusives pour les clients',
    'offres et réductions',
    'exclusivités',
    'avantages pour les clients',
    'réductions pour les clients',
    'offres pour les clients',
    'avantages exclusifs',
    'offres spéciales pour les clients',
    'offres exclusives',
]

_INTERNAL_KEYWORDS = [
    'bh bank', 'bh net', 'bh mobile', 'bhbank',
    'banque de l\'habitat', 'banque de l habitat',
]


def is_internal_partnership(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _INTERNAL_KEYWORDS)


def is_generic_partnership(text: str) -> bool:
    t = text.lower()
    for phrase in _GENERIC_PHRASES:
        if phrase in t:
            return True
    has_pct = bool(re.search(r'\d+\s*%', text))
    has_amt = bool(re.search(r'\d+\s*tnd', t))
    return not (has_pct or has_amt)


def fix_partnership_card_mismatch(
    partnership: str, segment_key: str, default_partnership: str
) -> str:
    segment_label = SEGMENT_MAP.get(segment_key, "")
    allowed = SEGMENT_CARDS.get(segment_label, [])
    if not allowed:
        return partnership

    card_re = re.compile(r'carte\s+\w+', re.IGNORECASE)
    for card_match in card_re.findall(partnership):
        card_lower = card_match.lower()
        if not any(a in card_lower for a in allowed):
            return default_partnership
    return partnership


def validate_and_repair_partnership(
    partnership: str, segment_key: str, defaults: dict
) -> str:
    default = defaults["partnership"]

    if not partnership:
        return default

    if is_internal_partnership(partnership):
        if segment_key == "HighNetWorth" and "Carrefour" in default:
            return "Airbnb : 10% de réduction sur les locations premium pour les détenteurs de BH Prestige."
        return default

    if is_generic_partnership(partnership):
        if segment_key == "HighNetWorth" and "Carrefour" in default:
            return "Airbnb : 10% de réduction sur les locations premium pour les détenteurs de BH Prestige."
        return default

    partnership = fix_partnership_card_mismatch(partnership, segment_key, default)
    if segment_key == "HighNetWorth" and "Carrefour" in partnership:
        partnership = "Airbnb : 10% de réduction sur les locations premium pour les détenteurs de BH Prestige."

    if not re.search(r'\d+\s*%', partnership):
        segment_label = SEGMENT_MAP.get(segment_key, "")
        pct = SEGMENT_PARTNERSHIP_PCT.get(segment_label, "10%")
        partnership = partnership.rstrip(" .") + f" avec {pct} de réduction pour les clients BH Bank."

    if segment_key == "HighNetWorth" and "Carrefour" in partnership:
        return "Airbnb : 10% de réduction sur les locations premium pour les détenteurs de BH Prestige."

    return partnership


# ═══════════════════════════════════════════════════════════════
# TREND ENRICHMENT
# ═══════════════════════════════════════════════════════════════
_TREND_LABELS = {
    "avg_income":   "revenu moyen",
    "avg_savings":  "épargne moyenne",
    "avg_spending": "dépenses moyennes",
    "avg_online":   "activité bancaire en ligne",
    "avg_mobile":   "utilisation mobile",
}


def enrich_interpretation_with_trends(
    interpretation: str, stats: dict, trends: dict, segment: str
) -> str:
    negative_notes = []
    for key, label in _TREND_LABELS.items():
        val = trends.get(key)
        if isinstance(val, (int, float)) and val < 0:
            negative_notes.append(f"une baisse du/de la {label} de {abs(val):.1f}%")

    if not negative_notes:
        return interpretation

    interp_lower = interpretation.lower()
    new_notes = [
        n for n in negative_notes
        if not any(w in interp_lower for w in n.split()[:3])
    ]
    if not new_notes:
        return interpretation

    insertion = (
        " Cependant, les données révèlent également "
        + ", et ".join(new_notes)
        + ", ce qui nécessite une attention stratégique particulière."
    )

    sentences = interpretation.rstrip(" .").split(".")
    if len(sentences) > 1:
        return sentences[0] + insertion + ". " + ".".join(sentences[1:]).lstrip()
    return interpretation + insertion


# ═══════════════════════════════════════════════════════════════
# JUSTIFICATION FINANCIAL INJECTION
# ═══════════════════════════════════════════════════════════════
def inject_financials(
    justification: str,
    roi: float,
    clv: float,
    pmt: float,
) -> str:
    checks = [
        str(int(clv)) in justification or f"{clv:.2f}" in justification,
        str(pmt) in justification,
        str(int(abs(roi))) in justification,
    ]
    if not all(checks):
        header = (
            f"[Données financières vérifiées] ROI : {roi:.1f}%, "
            f"CLV : {clv:.0f} TND, PMT : {pmt} TND/mois. "
        )
        justification = header + justification

    if roi < 0 and "acquisition" not in justification.lower():
        justification += (
            " Le ROI négatif s'explique par les coûts d'acquisition initiaux "
            "(prospection, onboarding, communication) ; le retour à l'équilibre "
            "est attendu dès la 2ème année grâce à la CLV élevée et au taux de rétention cible."
        )

    return justification


# ═══════════════════════════════════════════════════════════════
# MAIN RECOMMENDATION FUNCTION
# ═══════════════════════════════════════════════════════════════
def generate_innovation_recommendation(
    segment: str,
    stats: dict,
    trends: dict,
    growth_simulator=None,
) -> dict:

    avg_income  = stats.get("avg_income", 2500)
    avg_tenure  = stats.get("avg_tenure", 10)

    pmt_example = calculate_pmt(10_000, 10.5, 36)
    margin      = avg_income * 0.02
    clv_est     = calculate_clv(margin, avg_tenure, 10)
    roi_est     = calculate_roi(avg_income * 12 * 0.10, avg_income * 3)

    trend_lines = []
    negative_trend_list = []
    for k, v in trends.items():
        if not isinstance(v, (int, float)):
            continue
        arrow = "↑" if v > 0 else ("↓" if v < 0 else "→")
        label = _TREND_LABELS.get(k, k.replace("avg_", ""))
        trend_lines.append(f"  • {label}: {arrow} {abs(v):.1f}%")
        if v < 0:
            negative_trend_list.append(f"{label} ({v:.1f}%)")

    trend_block = "\n".join(trend_lines) if trend_lines else "  • Aucune tendance significative"

    if negative_trend_list:
        negative_note = (
            "⚠️  TENDANCES NÉGATIVES RÉELLES (à mentionner obligatoirement dans l'interprétation) :\n"
            + "\n".join(f"  – {n}" for n in negative_trend_list)
        )
    else:
        negative_note = (
            "✅  Toutes les tendances sont positives ou neutres. "
            "Ne PAS inventer ni présenter une tendance positive comme négative."
        )

    roi_note = (
        f"⚠️  ROI NÉGATIF ({roi_est:.1f}%) : explique que cela est dû aux coûts "
        "d'acquisition initiaux et précise à partir de quelle ANNÉE RELATIVE (ex : 'dès la 2ème année') "
        "il devient positif. N'utilise jamais une année calendaire comme 2025 ou 2026."
        if roi_est < 0 else
        f"✅  ROI POSITIF ({roi_est:.1f}%) : mets en avant ce chiffre dans la justification."
    )

    defaults = get_segment_defaults(segment)
    catalogue = get_catalogue_products()
    catalogue_text = "\n".join(f"  – {p}" for p in catalogue[:15]) or "  – Catalogue non disponible"

    prompt = f"""Tu es un expert senior en stratégie et innovation bancaire pour BH Bank (Tunisie).
Génère des recommandations PRÉCISES, DIFFÉRENCIÉES et CHIFFRÉES pour le segment : {SEGMENT_MAP.get(segment, segment)}.

═══════════════════════════════════════════════════════
DONNÉES RÉELLES DU SEGMENT
═══════════════════════════════════════════════════════
  • Nombre de clients  : {stats['count']}
  • Âge moyen          : {stats.get('avg_age', 'N/A')} ans
  • Revenu mensuel moy.: {avg_income:.0f} TND
  • Dépenses mensuelles: {stats.get('avg_spending', 'N/A')} TND
  • Épargne mensuelle  : {stats.get('avg_savings', 'N/A')} TND
  • Croissance simulée : {growth_simulator or 'N/A'}%

TENDANCES TRIMESTRIELLES (T/T) :
{trend_block}

{negative_note}

═══════════════════════════════════════════════════════
CATALOGUE PRODUITS EXISTANTS (pour la MODIFICATION uniquement)
═══════════════════════════════════════════════════════
{catalogue_text}

═══════════════════════════════════════════════════════
INDICATEURS FINANCIERS — UTILISE CES CHIFFRES EXACTEMENT
═══════════════════════════════════════════════════════
  • PMT (10 000 TND / 36 mois / 10,5%)  : {pmt_example} TND/mois
  • CLV estimée du segment               : {clv_est:.0f} TND
  • ROI estimé                           : {roi_est:.1f}%
  {roi_note}

═══════════════════════════════════════════════════════
RÈGLES STRICTES — TOUTES OBLIGATOIRES
═══════════════════════════════════════════════════════
1. LANGUE : français uniquement.

2. INTERPRÉTATION STRATÉGIQUE (3 phrases) :
   – Base-toi UNIQUEMENT sur les données réelles du segment.
   – Cite les tendances négatives listées ci-dessus si elles existent.
   – Ne présente JAMAIS une tendance positive comme négative.

3. NOUVEAU PRODUIT :
   – Nom commercial évocateur + exactement 5 caractéristiques concrètes et mesurables.
   – Prix clair et explicite (ex : "75 TND par an").
   – Le produit doit être DIFFÉRENT des produits du catalogue.

4. MODIFICATION :
   – Cite OBLIGATOIREMENT un produit du catalogue ci-dessus par son NOM EXACT.
   – L'amélioration doit être précise et mesurable (plafond, taux, fonctionnalité).
   – La modification doit être COHÉRENTE avec le segment (ex : LA CARTE COOL pour Jeunes Actifs, La Carte Yasmine pour Nids Vides).

5. PARTENARIAT :
   – Marque EXTERNE connue en Tunisie (ni BH Bank, ni ses propres produits).
   – Service ou produit PRÉCIS lié aux habitudes du segment.
   – POURCENTAGE DE RÉDUCTION obligatoire (ex : "20% de réduction sur...").
   – INTERDIT : "offres exclusives", "avantages pour les clients", toute formule vague sans chiffre.
   – INTERDIT : mentionner une carte BH qui n'appartient pas à ce segment.

6. JUSTIFICATION :
   – Utilise EXACTEMENT : PMT={pmt_example} TND, CLV={clv_est:.0f} TND, ROI={roi_est:.1f}%.
   – 3 KPIs avec cibles chiffrées (ex : taux d'adoption 30%, souscriptions 500+, rétention 85%).
   – {roi_note}

7. PLAN DE DÉPLOIEMENT — deux blocs SÉPARÉS :
   "NOUVEAU PRODUIT :" (3 phases, 12-16 mois total) :
     Phase 1 = Conception & validation produit
     Phase 2 = Développement technique & formation équipes
     Phase 3 = Lancement & suivi des KPIs
   "MODIFICATION :" (3 phases, 3-6 mois total) :
     Phase 1 = Analyse d'impact & validation
     Phase 2 = Implémentation technique & mise à jour systèmes
     Phase 3 = Communication clients & suivi performance
   Utilise des délais RELATIFS uniquement : "mois 1-3", "mois 4-8", etc.
   N'utilise JAMAIS d'années calendaires (2025, 2026, etc.).

8. RISQUES : exactement 2 risques, chacun avec :
   – Description du risque spécifique au segment.
   – "Mitigation :" suivi d'une action CONCRÈTE et chiffrée si possible.

═══════════════════════════════════════════════════════
FORMAT DE RÉPONSE — RESPECTE CES TITRES EXACTEMENT
═══════════════════════════════════════════════════════
INTERPRÉTATION STRATÉGIQUE :
NOUVEAU PRODUIT :
MODIFICATION :
PARTENARIAT :
JUSTIFICATION :
PLAN DE DÉPLOIEMENT :
RISQUES :

Commence IMMÉDIATEMENT par "INTERPRÉTATION STRATÉGIQUE :" sans aucune introduction."""

    llm_response = call_ollama(prompt)

    justification_default = (
        f"ROI calculé : {roi_est:.1f}%"
        + (
            " (négatif en année 1 en raison des coûts d'acquisition ; "
            "retour à l'équilibre dès la 2ème année). "
            if roi_est < 0
            else " (positif dès la première année). "
        )
        + f"CLV projetée : {clv_est:.0f} TND. "
        f"PMT de référence (10 000 TND / 36 mois / 10,5%) : {pmt_example} TND/mois. "
        "KPIs cibles : taux d'adoption 30%, souscriptions 500+ dans les 12 premiers mois, "
        "taux de rétention 85%."
    )

    result = {
        "trend_interpretation": defaults["interpretation"],
        "product":              defaults["product"],
        "modification":         defaults["modification"],
        "partnership":          defaults["partnership"],
        "justification":        justification_default,
        "roadmap": (
            f"NOUVEAU PRODUIT :\n{defaults['roadmap_new']}\n\n"
            f"MODIFICATION :\n{defaults['roadmap_modif']}"
        ),
        "risks": (
            "Risque 1 : Adoption lente — les clients peuvent être réticents à changer de produit. "
            "Mitigation : offre de lancement à -50% pendant 3 mois, objectif 200 souscriptions dès le 1er mois. "
            "Risque 2 : Pression concurrentielle des fintechs locales. "
            "Mitigation : différenciation par l'accompagnement conseiller et les avantages partenaires exclusifs ; "
            "revue tarifaire trimestrielle pour rester compétitif."
        ),
    }

    if not llm_response:
        print("⚠️  LLM unavailable — using defaults.")
        result["trend_interpretation"] = enrich_interpretation_with_trends(
            result["trend_interpretation"], stats, trends, segment
        )
        return result

    patterns = {
        "trend_interpretation": r"INTERPRÉTATION STRATÉGIQUE\s*:?\s*(.*?)(?=NOUVEAU PRODUIT\s*:|$)",
        "product":              r"NOUVEAU PRODUIT\s*:?\s*(.*?)(?=MODIFICATION\s*:|$)",
        "modification":         r"MODIFICATION\s*:?\s*(.*?)(?=PARTENARIAT\s*:|$)",
        "partnership":          r"PARTENARIAT\s*:?\s*(.*?)(?=JUSTIFICATION\s*:|$)",
        "justification":        r"JUSTIFICATION\s*:?\s*(.*?)(?=PLAN DE DÉPLOIEMENT\s*:|$)",
        "roadmap":              r"PLAN DE DÉPLOIEMENT\s*:?\s*(.*?)(?=RISQUES\s*:|$)",
        "risks":                r"RISQUES\s*:?\s*(.*?)(?=##|$)",
    }

    parsed_count = 0
    for key, pattern in patterns.items():
        match = re.search(pattern, llm_response, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            if content and len(content) > 10:
                result[key] = content
                parsed_count += 1

    if parsed_count == 0:
        result["trend_interpretation"] = llm_response[:500]
        print("⚠️  No sections parsed — using raw LLM response as interpretation.")

    print(f"✅  Parsed {parsed_count}/7 sections from LLM")

    # ── Post‑processing pipeline ─────────────────────────────────────────────

    # 1. Strip Markdown artifacts
    for key in result:
        if isinstance(result[key], str):
            result[key] = clean_llm_artifacts(result[key])

    # 2. Fix absolute year references
    for key in ("trend_interpretation", "justification", "roadmap"):
        result[key] = fix_roi_year_reference(result[key])

    # 3. Enrich interpretation with real negative trends
    result["trend_interpretation"] = enrich_interpretation_with_trends(
        result["trend_interpretation"], stats, trends, segment
    )

    # 4. Clean and fix modification text
    if catalogue:
        modification_text = result["modification"]
        # First, inject a product name if missing
        has_catalogue = any(p.lower() in modification_text.lower() for p in catalogue)
        if not has_catalogue:
            segment_label = SEGMENT_MAP.get(segment, "")
            if segment_label == "Retraités":
                best_product = "La carte Yasmine"
            elif segment_label == "Hauts revenus":
                best_product = "La carte Yasmine"
            elif segment_label == "Jeunes Actifs":
                best_product = "LA CARTE COOL"
            elif segment_label == "Étudiants":
                best_product = "La carte BH SCOLARITE"  # ← CORRECTED
            else:
                best_product = catalogue[0]
            result["modification"] = f"{best_product} : {modification_text}"
        else:
            result["modification"] = clean_modification_text(modification_text, catalogue, segment)

    # 5. Partnership validation & repair
    result["partnership"] = validate_and_repair_partnership(
        result["partnership"], segment, defaults
    )

    # 6. Inject / verify financials in justification
    result["justification"] = inject_financials(
        result["justification"], roi_est, clv_est, pmt_example
    )

    # 7. Ensure roadmap has two clearly labelled blocks
    roadmap = result["roadmap"]
    if not (
        re.search(r"nouveau produit", roadmap, re.IGNORECASE)
        and re.search(r"modification", roadmap, re.IGNORECASE)
    ):
        result["roadmap"] = (
            f"NOUVEAU PRODUIT :\n{defaults['roadmap_new']}\n\n"
            f"MODIFICATION :\n{defaults['roadmap_modif']}"
        )

    # 8. Reject risks that are too short or missing "Mitigation"
    risks = result["risks"]
    if len(risks.split()) < 25 or "mitigation" not in risks.lower():
        segment_label = SEGMENT_MAP.get(segment, "ce segment")
        result["risks"] = (
            f"Risque 1 : Adoption insuffisante du nouveau produit par les clients {segment_label}. "
            "Mitigation : campagne de lancement digitale ciblée avec offre promotionnelle "
            "-50% pendant 3 mois ; objectif minimum 200 souscriptions dès le 1er mois. "
            f"Risque 2 : Pression concurrentielle des fintechs sur le segment {segment_label}. "
            "Mitigation : positionnement sur la relation conseiller et les avantages partenaires exclusifs ; "
            "revue tarifaire trimestrielle et veille concurrentielle mensuelle."
        )

    return result