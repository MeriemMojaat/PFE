import json
import re
import math
from collections import defaultdict
from typing import List, Dict, Optional
from rapidfuzz import fuzz

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
        for name, prod in self.product_by_name.items():
            if name in query_lower:
                return prod
        best_score = 0
        best_prod = None
        for name, prod in self.product_by_name.items():
            score = fuzz.partial_ratio(name, query_lower)
            if score > best_score and score > 70:
                best_score = score
                best_prod = prod
        return best_prod

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict]:
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
# Language detection
# ----------------------------------------------------------------------

def detect_language(text: str) -> str:
    text_lower = text.lower()
    french_markers = ['pour', 'avec', 'dans', 'sur', 'par', 'qui', 'que', 'est', 'les', 'des', 'une', 'carte', 'frais', 'quels', 'quelle', 'prix', 'tarif', 'ses', 'son', 'sa']
    english_markers = ['the', 'for', 'with', 'what', 'which', 'is', 'are', 'credit', 'card', 'fees', 'price', 'its', 'it']
    french_score = sum(1 for m in french_markers if m in text_lower)
    english_score = sum(1 for m in english_markers if m in text_lower)
    return "fr" if french_score >= english_score else "en"


# ----------------------------------------------------------------------
# Ollama client
# ----------------------------------------------------------------------

class OllamaClient:
    def __init__(self, model: str = "llama3:8b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def generate(self, prompt: str) -> str:
        import requests
        payload = {"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
        try:
            resp = requests.post(self.url, json=payload, timeout=60)
            if resp.status_code == 200:
                return resp.json().get("response", "")
            return f"Error: {resp.status_code}"
        except Exception as e:
            return f"Connection error: {e}"


# ----------------------------------------------------------------------
# RAG System with conversation memory
# ----------------------------------------------------------------------

class RAGSystem:
    def __init__(self, index: ProductIndex, llm: OllamaClient):
        self.index = index
        self.llm = llm
        self.last_product = None          # last mentioned product name
        self.last_product_obj = None      # full product dict

    def _resolve_product_reference(self, question: str) -> str:
        """If question uses possessive pronouns and we have a last product, prepend it."""
        q_lower = question.lower()
        french_refs = ['ses', 'son', 'sa', 'cette', 'ce', 'cet', 'carte', 'produit', 'lui', 'il']
        english_refs = ['its', 'it', 'this', 'that', 'product', 'card']
        is_reference = any(ref in q_lower for ref in french_refs + english_refs)
        if is_reference and self.last_product:
            return f"{self.last_product} {question}"
        return question

    def answer(self, question: str) -> str:
        lang = detect_language(question)

        # Resolve reference to last product
        resolved_question = self._resolve_product_reference(question)

        # Try exact product match
        exact_product = self.index.find_exact_product(resolved_question)
        if exact_product:
            retrieved = [exact_product]
        else:
            retrieved = self.index.retrieve(resolved_question, top_k=2)
            if not retrieved:
                return "Je n'ai pas trouvé de produit correspondant." if lang == "fr" else "No matching product found."

        # Update last product (use the first retrieved product)
        self.last_product = retrieved[0]['name']
        self.last_product_obj = retrieved[0]

        # Build context with fee extraction if needed
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

        # Prompt – no polite phrases, with reformulation notice
        if lang == "fr":
            prompt = f"""Vous êtes un assistant bancaire. Répondez à la question en utilisant UNIQUEMENT les informations ci-dessous. Reformulez la réponse de manière claire et concise, sans formules de politesse (pas de "Bonjour", "Merci", etc.). Ajoutez en fin de réponse : "(Réponse reformulée d'après le catalogue)".

Informations:
{context}

Question: {question}

Réponse:"""
        else:
            prompt = f"""You are a banking assistant. Answer the question using ONLY the information below. Reformulate the answer clearly and concisely, without any polite phrases (no "Hello", "Thank you", etc.). At the end of your answer, add: "(Answer reformulated from the catalog)".

Context:
{context}

Question: {question}

Answer:"""

        raw_answer = self.llm.generate(prompt)
        return raw_answer


# ----------------------------------------------------------------------
# CLI
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
        print("\nAsk questions (type 'quit' to exit). The system remembers the last mentioned product.")
        while True:
            q = input("\nYou: ").strip()
            if q.lower() in ("quit", "exit"):
                break
            if not q:
                continue
            print(f"\nAssistant: {rag.answer(q)}")
    else:
        # Demo
        q1 = "Quels sont les frais de la carte COOL ?"
        print(f"\nYou: {q1}")
        print(f"Assistant: {rag.answer(q1)}")
        q2 = "Quelles sont ses fonctionnalités ?"
        print(f"\nYou: {q2}")
        print(f"Assistant: {rag.answer(q2)}")