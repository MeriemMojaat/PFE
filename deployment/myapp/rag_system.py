import json
import re
import math
from collections import defaultdict
from typing import List, Dict, Optional
from rapidfuzz import fuzz
from langdetect import detect
import requests

# ----------------------------------------------------------------------
# Product Index (TF‑IDF + fuzzy product name matching)
# ----------------------------------------------------------------------

class ProductIndex:
    def __init__(self, json_path: str = "product_contents.json"):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.products = data["products"]
        self.product_by_name = {p["name"].lower(): p for p in self.products}
        self._build_index()

    def _build_index(self):
        self.documents = []
        self.doc_ids = []
        for prod in self.products:
            doc = f"Product: {prod['name']}\nCategory: {prod['category']}\n"
            if prod['subcategory']:
                doc += f"Subcategory: {prod['subcategory']}\n"
            doc += prod['content']
            self.documents.append(doc.lower())
            self.doc_ids.append(prod)

        self.doc_tokens = []
        doc_freq = defaultdict(int)
        for doc in self.documents:
            tokens = re.findall(r'\b[a-zéèêëàâôîïùûüçñ0-9]+\b', doc)
            self.doc_tokens.append(tokens)
            for t in set(tokens):
                doc_freq[t] += 1

        N = len(self.documents)
        self.idf = {}
        for term, freq in doc_freq.items():
            self.idf[term] = math.log((N + 1) / (freq + 1)) + 1

    def find_exact_product(self, query: str) -> Optional[Dict]:
        query_lower = query.lower()
        # 1. Direct match: product name appears in query
        for name, prod in self.product_by_name.items():
            if name in query_lower:
                return prod
        # 2. Partial match: query appears inside product name
        for name, prod in self.product_by_name.items():
            if query_lower in name:
                return prod
        # 3. Word‑based matching: split query into words, try to match each word inside product names
        words = [w for w in query_lower.split() if len(w) > 3]  # ignore very short words
        for word in words:
            for name, prod in self.product_by_name.items():
                if word in name:
                    return prod
        # 4. Fuzzy matching as fallback
        best_score = 0
        best_prod = None
        for name, prod in self.product_by_name.items():
            score = fuzz.partial_ratio(name, query_lower)
            if score > best_score and score > 70:
                best_score = score
                best_prod = prod
        return best_prod

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict]:
        exact = self.find_exact_product(query)
        if exact:
            return [exact]

        query_tokens = re.findall(r'\b[a-zéèêëàâôîïùûüçñ0-9]+\b', query.lower())
        q_tf = defaultdict(int)
        for t in query_tokens:
            q_tf[t] += 1
        q_vec = {t: count * self.idf.get(t, 0) for t, count in q_tf.items()}
        norm_q = math.sqrt(sum(v*v for v in q_vec.values()))
        if norm_q == 0:
            return []

        scores = []
        for idx, tokens in enumerate(self.doc_tokens):
            dot = 0
            doc_norm = 0
            for term, q_val in q_vec.items():
                cnt = tokens.count(term)
                if cnt:
                    doc_val = cnt * self.idf.get(term, 0)
                    dot += q_val * doc_val
                    doc_norm += doc_val * doc_val
            norm_d = math.sqrt(doc_norm)
            if norm_d > 0:
                scores.append((idx, dot / (norm_q * norm_d)))
            else:
                scores.append((idx, 0))
        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scores[:top_k]:
            if score > 0:
                prod = self.doc_ids[idx].copy()
                prod["relevance_score"] = score
                results.append(prod)
        return results


# ----------------------------------------------------------------------
# Improved language detection (handles short English commands)
# ----------------------------------------------------------------------
COMMON_ENGLISH_WORDS = {
    'what', 'how', 'why', 'when', 'where', 'which', 'explain', 'tell', 'show',
    'list', 'describe', 'define', 'give', 'name', 'is', 'are', 'was', 'were'
}
# English question starters to force language detection
ENGLISH_STARTERS = ['explain', 'what', 'how', 'why', 'when', 'where', 'which', 'tell', 'describe', 'define', 'list']

def detect_language(text: str) -> str:
    text_lower = text.lower().strip()
    # If query starts with typical English question word, force English
    if any(text_lower.startswith(word) for word in ENGLISH_STARTERS):
        return "en"
    if len(text_lower) < 6 and text_lower in COMMON_ENGLISH_WORDS:
        return "en"
    try:
        lang = detect(text)
        if lang.startswith('fr'):
            return "fr"
        elif lang.startswith('en'):
            return "en"
        else:
            return "fr"
    except Exception:
        return "fr"


# ----------------------------------------------------------------------
# Ollama client
# ----------------------------------------------------------------------

class OllamaClient:
    def __init__(self, model: str = "llama3:8b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        }
        try:
            resp = requests.post(self.url, json=payload, timeout=180)
            if resp.status_code == 200:
                return resp.json().get("response", "")
            return f"Error: {resp.status_code}"
        except Exception as e:
            return f"Connection error: {e}"


# ----------------------------------------------------------------------
# RAG System with conversation memory, greeting handling, and out‑of‑scope refusal
# ----------------------------------------------------------------------

class RAGSystem:
    def __init__(self, index: ProductIndex, llm: OllamaClient):
        self.index = index
        self.llm = llm
        self.last_product = None
        self.last_product_obj = None

    def _is_greeting(self, question: str) -> tuple:
        q = question.lower().strip()
        greetings_fr = ['bonjour', 'salut', 'coucou', 'bonsoir', 'hello', 'hey']
        greetings_en = ['hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon']
        if q in greetings_fr or any(g in q for g in greetings_fr):
            return True, 'fr'
        if q in greetings_en or any(g in q for g in greetings_en):
            return True, 'en'
        return False, None

    def _resolve_product_reference(self, question: str) -> str:
        q_lower = question.lower()
        french_refs = ['ses', 'son', 'sa', 'leur', 'leurs', 'ce', 'cet', 'cette', 'ces', 'lui', 'elle', 'eux']
        english_refs = ['its', 'it', 'this', 'that', 'these', 'those', 'them', 'they']
        is_reference = any(ref in q_lower for ref in french_refs + english_refs)
        has_product = self.index.find_exact_product(question) is not None
        if is_reference and not has_product and self.last_product:
            return f"{self.last_product} {question}"
        return question

    def answer(self, question: str, history: List[Dict] = None) -> str:
        # 1. Language detection
        lang = detect_language(question)

        # 2. Greeting detection (overrides everything)
        is_greeting, greet_lang = self._is_greeting(question)
        if is_greeting:
            if greet_lang == 'fr':
                return "Je suis votre assistant bancaire. Je peux vous renseigner sur nos produits (cartes, comptes, crédits, assurances). Comment puis-je vous aider ?"
            else:
                return "I am your banking assistant. I can answer questions about our products (cards, accounts, loans, insurance). How can I help you?"

        # 3. Special case: count products
        if re.search(r'\b(how many|combien de|nombre de|total des?)\s+products?\b', question.lower()):
            count = len(self.index.products)
            if lang == "fr":
                return f"Le catalogue contient {count} produits. (Réponse reformulée d'après le catalogue)"
            else:
                return f"The catalog contains {count} products. (Answer reformulated from the catalog)"

        # 4. Resolve pronoun reference
        resolved_question = self._resolve_product_reference(question)

        # 5. Try exact product match, then retrieval
        exact_product = self.index.find_exact_product(resolved_question)
        if exact_product:
            retrieved = [exact_product]
        else:
            retrieved = self.index.retrieve(resolved_question, top_k=2)

        # 6. Relevance threshold (lowered to catch more matches)
        MIN_RELEVANCE = 0.15
        if retrieved and not exact_product:
            top_score = retrieved[0].get('relevance_score', 0)
            if top_score < MIN_RELEVANCE:
                retrieved = []

        if not retrieved:
            # Provide a helpful message indicating what we couldn't find
            if lang == 'fr':
                return f"Je n'ai pas trouvé de produit correspondant à « {question[:50]} ». Vérifiez le nom du produit ou posez une autre question."
            else:
                return f"I could not find a product matching '{question[:50]}'. Please check the product name or ask another question."

        # 7. Update last product
        self.last_product = retrieved[0]['name']
        self.last_product_obj = retrieved[0]

        # 8. Build context (fee extraction if needed)
        context_parts = []
        for prod in retrieved:
            if "frais" in question.lower() or "tarif" in question.lower() or "fee" in question.lower():
                content = prod['content']
                tarif_match = re.search(r'(TARIFICATION.*?)(?=\n[A-Z]{5,}:|\Z)', content, re.DOTALL | re.IGNORECASE)
                fee_text = tarif_match.group(1).strip() if tarif_match else content
            else:
                fee_text = prod['content']

            sub = f"Sous-catégorie: {prod['subcategory']}" if prod['subcategory'] else ""
            context_parts.append(
                f"--- Produit: {prod['name']} (page {prod['page_start']})\n"
                f"Catégorie: {prod['category']}\n{sub}\n"
                f"Contenu:\n{fee_text}\n"
            )
        context = "\n".join(context_parts)

        # 9. Build conversation history string
        history_str = ""
        if history and len(history) > 0:
            history_str = "Historique de la conversation:\n"
            for i in range(0, len(history), 2):
                if i+1 < len(history):
                    history_str += f"Utilisateur: {history[i]['content']}\nAssistant: {history[i+1]['content']}\n"
                else:
                    history_str += f"Utilisateur: {history[i]['content']}\n"
            history_str += "\n"

        # 10. Prompt construction (French or English)
        if lang == "fr":
            prompt = f"""Vous êtes un assistant bancaire. Répondez à la question en utilisant UNIQUEMENT les informations ci-dessous. Tenez compte de l'historique de la conversation si pertinent. Reformulez la réponse de manière claire et concise, sans formules de politesse (pas de "Bonjour", "Merci", etc.). Ajoutez en fin de réponse : "(Réponse reformulée d'après le catalogue)".

{history_str}
Informations sur les produits:
{context}

Question actuelle: {question}

Réponse:"""
        else:
            prompt = f"""You are a banking assistant. Answer the question using ONLY the information below. Consider the conversation history if relevant. Reformulate the answer clearly and concisely, without any polite phrases (no "Hello", "Thank you", etc.). At the end of your answer, add: "(Answer reformulated from the catalog)".

{history_str}
Product information:
{context}

Current question: {question}

Answer:"""

        raw_answer = self.llm.generate(prompt)

        # 11. Safety net
        if not raw_answer or len(raw_answer.strip()) < 5:
            if lang == 'fr':
                return "Je n'ai pas trouvé d'information pertinente dans le catalogue. Veuillez reformuler votre question."
            else:
                return "I did not find relevant information in the catalogue. Please rephrase your question."

        return raw_answer


# ----------------------------------------------------------------------
# CLI (interactive with history)
# ----------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", "-q", type=str)
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--model", type=str, default="llama3:8b")
    args = parser.parse_args()

    print("Loading product index...")
    index = ProductIndex("product_contents.json")
    print(f"Loaded {len(index.products)} products.")
    llm = OllamaClient(model=args.model)
    rag = RAGSystem(index, llm)

    if args.question:
        print(f"\nQ: {args.question}")
        print(f"A: {rag.answer(args.question)}")
    elif args.interactive:
        print("\nAsk questions (type 'quit' to exit). The system remembers the conversation and last mentioned product.")
        history = []
        while True:
            q = input("\nYou: ").strip()
            if q.lower() in ("quit", "exit"):
                break
            if not q:
                continue
            answer = rag.answer(q, history)
            print(f"\nAssistant: {answer}")
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": answer})
            if len(history) > 20:
                history = history[-20:]
    else:
        # Demo with history
        q1 = "Quels sont les frais de la carte COOL ?"
        print(f"\nYou: {q1}")
        history = []
        a1 = rag.answer(q1, history)
        print(f"Assistant: {a1}")
        history.append({"role": "user", "content": q1})
        history.append({"role": "assistant", "content": a1})

        q2 = "Quelles sont ses fonctionnalités ?"
        print(f"\nYou: {q2}")
        a2 = rag.answer(q2, history)
        print(f"Assistant: {a2}")