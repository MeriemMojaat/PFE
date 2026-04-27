import json
import re
import math
from collections import defaultdict
from typing import List, Dict, Optional
from rapidfuzz import fuzz
from langdetect import detect  # new: language detection library

# ----------------------------------------------------------------------
# Product Index (TF‑IDF + fuzzy product name matching)
# ----------------------------------------------------------------------

class ProductIndex:
    def __init__(self, json_path: str = "product_contents.json"):
        # Load products from JSON and build TF-IDF index
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.products = data["products"] #List of product dicts
        self.product_by_name = {p["name"].lower(): p for p in self.products} # for fast lookup we lowercase the product name
        self._build_index() #Create TF-IDF index for retrieval

    def _build_index(self):
        #Create a TF-IDF index for all proucts
        self.documents = [] #create an empty list to hold the document text for each product ( name , category, subcategory, content)
        self.doc_ids = [] #create an empty list to store te original product dict for each document 
        for prod in self.products:
            doc = f"Product: {prod['name']}\nCategory: {prod['category']}\n"
            if prod['subcategory']:
                doc += f"Subcategory: {prod['subcategory']}\n"
            doc += prod['content']
            self.documents.append(doc.lower()) #Append & and converts to lower case so that Carte & carte will be treated the same way
            self.doc_ids.append(prod)

        self.doc_tokens = [] #Create an empty list that will store tokenized versions of each document for TF-IDF calculations
        doc_freq = defaultdict(int) #Create a default dictionary to count document frequencies for each term (number of documents that contain the term)
        for doc in self.documents:
            tokens = re.findall(r'\b[a-zéèêëàâôîïùûüçñ0-9]+\b', doc) #find all words tht match the pattern (including accented characters and numbers)
            self.doc_tokens.append(tokens)
            for t in set(tokens):
                doc_freq[t] += 1 #Increment the document frequency count for each unique term in the document

        N = len(self.documents)
        self.idf = {} # to store the idf values for each term
        for term, freq in doc_freq.items():
            self.idf[term] = math.log((N + 1) / (freq + 1)) + 1

    def find_exact_product(self, query: str) -> Optional[Dict]:
        query_lower = query.lower()
        for name, prod in self.product_by_name.items():
            if name in query_lower:
                return prod
        best_score = 0 # Initialize best score for fuzzy matching
        best_prod = None
        for name, prod in self.product_by_name.items():
            score = fuzz.partial_ratio(name, query_lower) #compute fuzzy matching score between product name and query( partial_ratio looks for the best matching substring in the query)
            if score > best_score and score > 70:
                best_score = score
                best_prod = prod
        return best_prod

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict]:
        #this method retrieves the most relevant products based on the query using TF-IDF cosine similarity. It first tries to find an exact product match by name, if not found it computes the TF-IDF vector for the query and compares it to the document vectors to find the most relevant products.
        # First try exact product match (by name)
        exact = self.find_exact_product(query)
        if exact:
            return [exact]

        query_tokens = re.findall(r'\b[a-zéèêëàâôîïùûüçñ0-9]+\b', query.lower()) #convert to lower case & tokenize the query using the same pattern as for the documents
        q_tf = defaultdict(int) #create a dictionary to store term frequencies for the query
        for t in query_tokens:
            q_tf[t] += 1
        q_vec = {t: count * self.idf.get(t, 0) for t, count in q_tf.items()} #compute the TF-IDF vector for the query by multiplying term frequency with the IDF value for each term. If a term is not in the index, its IDF is treated as 0.
        norm_q = math.sqrt(sum(v*v for v in q_vec.values())) #computes the euclidean norm (length ) length of the query vector. 
        if norm_q == 0:
            return [] # return empty list

        scores = [] # empty list to store document_index & cosine similarity score for each document
        for idx, tokens in enumerate(self.doc_tokens):
            #initialize variables to compute the dot product and norm of the document vector
            dot = 0
            doc_norm = 0
            for term, q_val in q_vec.items():
                cnt = tokens.count(term) #how many times the term appears in the document's token list (TF in the document )
                if cnt:
                    doc_val = cnt * self.idf.get(term, 0)
                    dot += q_val * doc_val
                    doc_norm += doc_val * doc_val
            norm_d = math.sqrt(doc_norm)
            if norm_d > 0:
                scores.append((idx, dot / (norm_q * norm_d))) #compute cosine similarity
            else:
                scores.append((idx, 0)) # has no terms that overlap with query == similarity is 0 
        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scores[:top_k]: # takes the top_k entries
            if score > 0:
                prod = self.doc_ids[idx].copy() #make a copy to avoid modifying the original 
                prod["relevance_score"] = score # add the relevance score
                results.append(prod)
        return results


# ----------------------------------------------------------------------
# Language detection (using langdetect library)
# ----------------------------------------------------------------------

def detect_language(text: str) -> str:
    """
    Detect language of the input text using langdetect.
    Returns "fr" for French, "en" for English.
    Defaults to French if detection fails or returns other language.
    """
    try:
        # langdetect returns a two-letter language code (e.g., 'fr', 'en')
        lang = detect(text)
        # Map to our expected codes
        if lang.startswith('fr'):
            return "fr"
        elif lang.startswith('en'):
            return "en"
        else:
            # For other languages, default to French (catalog is French)
            return "fr"
    except Exception:
        # If detection fails (e.g., very short text or error), fallback to French
        return "fr"


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
        #Stream false to get the full response at once and not a stream of chunks
        #not hallucinate & without adding creative phrases & using synonyms that are not in the catalog we set temperature to 0.1 to make the model more deterministic and less likely to generate random or creative responses that are not based on the provided context.
        try:
            resp = requests.post(self.url, json=payload, timeout=180)
            if resp.status_code == 200:
                return resp.json().get("response", "")
            return f"Error: {resp.status_code}"
        except Exception as e:
            return f"Connection error: {e}"


# ----------------------------------------------------------------------
# RAG System with conversation memory and product count
# ----------------------------------------------------------------------

class RAGSystem:
    def __init__(self, index: ProductIndex, llm: OllamaClient):
        self.index = index
        self.llm = llm
        self.last_product = None          # last mentioned product name
        self.last_product_obj = None      # full product dict

    def _resolve_product_reference(self, question: str) -> str:
        """
        If question uses a true possessive pronoun and does NOT already contain
        a product name, prepend the last product name.
        """
        q_lower = question.lower()
        # True possessive pronouns (not general words like 'carte')
        french_refs = ['ses', 'son', 'sa', 'leur', 'leurs', 'ce', 'cet', 'cette', 'ces', 'lui', 'elle', 'eux']
        english_refs = ['its', 'it', 'this', 'that', 'these', 'those', 'them', 'they']

        is_reference = any(ref in q_lower for ref in french_refs + english_refs)

        # Check if the question already contains a product name
        has_product = self.index.find_exact_product(question) is not None

        if is_reference and not has_product and self.last_product:
            return f"{self.last_product} {question}"
        return question

    def answer(self, question: str, history: List[Dict] = None) -> str:
        """
        Answer the question with optional conversation history.
        history: list of dicts with keys "role" and "content"
        """
        lang = detect_language(question)

        # Special case: count products
        if re.search(r'\b(how many|combien de|nombre de|total des?)\s+products?\b', question.lower()):
            count = len(self.index.products)
            if lang == "fr":
                return f"Le catalogue contient {count} produits. (Réponse reformulée d'après le catalogue)"
            else:
                return f"The catalog contains {count} products. (Answer reformulated from the catalog)"

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

        # Build conversation history string
        history_str = ""
        if history and len(history) > 0:
            history_str = "Historique de la conversation:\n"
            for i in range(0, len(history), 2):
                if i+1 < len(history):
                    history_str += f"Utilisateur: {history[i]['content']}\nAssistant: {history[i+1]['content']}\n"
                else:
                    history_str += f"Utilisateur: {history[i]['content']}\n"
            history_str += "\n"

        # Prompt – includes history, then context, then current question
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
            # Update history for next turn
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": answer})
            # Keep only last 10 exchanges (20 messages) to avoid token bloat
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