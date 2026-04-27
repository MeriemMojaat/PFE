import json
import re
import os
import math
from collections import defaultdict
from typing import List, Dict, Tuple

# ----------------------------------------------------------------------
# 1. Load and index product data
# ----------------------------------------------------------------------

class ProductIndex:
    def __init__(self, json_path: str = "product_contents.json"):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.products = data["products"]
        self._build_index()

    def _build_index(self):
        self.documents = []
        self.doc_ids = []
        for prod in self.products:
            meta = f"Product: {prod['name']}\nCategory: {prod['category']}\n"
            if prod['subcategory']:
                meta += f"Subcategory: {prod['subcategory']}\n"
            full_text = meta + prod['content']
            self.documents.append(full_text)
            self.doc_ids.append(prod)

        # TF‑IDF
        self.vocab = {}
        self.doc_tf = []
        doc_freq = defaultdict(int)
        for doc in self.documents:
            tokens = re.findall(r'\b\w+\b', doc.lower())
            tf = defaultdict(int)
            for t in tokens:
                tf[t] += 1
            self.doc_tf.append(tf)
            for t in set(tokens):
                doc_freq[t] += 1

        self.idf = {}
        N = len(self.documents)
        for term, freq in doc_freq.items():
            self.idf[term] = math.log((N + 1) / (freq + 1)) + 1

        self.doc_tfidf = []
        for tf in self.doc_tf:
            vec = {t: count * self.idf.get(t, 0) for t, count in tf.items()}
            self.doc_tfidf.append(vec)

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict]:
        q_tokens = re.findall(r'\b\w+\b', query.lower())
        q_tf = defaultdict(int)
        for t in q_tokens:
            q_tf[t] += 1
        q_vec = {t: count * self.idf.get(t, 0) for t, count in q_tf.items()}
        scores = []
        for idx, doc_vec in enumerate(self.doc_tfidf):
            dot = sum(q_vec.get(t, 0) * doc_vec.get(t, 0) for t in q_vec)
            norm_q = math.sqrt(sum(v*v for v in q_vec.values()))
            norm_d = math.sqrt(sum(v*v for v in doc_vec.values()))
            if norm_q == 0 or norm_d == 0:
                scores.append((idx, 0))
            else:
                scores.append((idx, dot / (norm_q * norm_d)))
        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scores[:top_k]:
            if score > 0:
                prod = self.doc_ids[idx].copy()
                prod["relevance_score"] = score
                prod["snippet"] = self._extract_snippet(query, self.documents[idx])
                results.append(prod)
        return results

    def _extract_snippet(self, query: str, text: str, window: int = 300) -> str:
        terms = set(re.findall(r'\b\w+\b', query.lower()))
        words = text.split()
        best_idx, best_cnt = 0, 0
        for i, w in enumerate(words):
            if w.lower() in terms:
                cnt = sum(1 for j in range(max(0,i-50), min(len(words), i+50)) if words[j].lower() in terms)
                if cnt > best_cnt:
                    best_cnt = cnt
                    best_idx = i
        start = max(0, best_idx - window//2)
        end = min(len(words), start + window)
        snippet = ' '.join(words[start:end])
        if start > 0: snippet = "..." + snippet
        if end < len(words): snippet = snippet + "..."
        return snippet


# ----------------------------------------------------------------------
# 2. LLM Interface – Ollama
# ----------------------------------------------------------------------

class OllamaClient:
    def __init__(self, model: str = "llama3:8b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def generate(self, prompt: str) -> str:
        import requests
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        try:
            resp = requests.post(self.url, json=payload, timeout=60)
            if resp.status_code == 200:
                return resp.json().get("response", "")
            else:
                return f"Error: {resp.status_code} - {resp.text}"
        except Exception as e:
            return f"Connection error: {e}"


# ----------------------------------------------------------------------
# 3. RAG System
# ----------------------------------------------------------------------

class RAGSystem:
    def __init__(self, index: ProductIndex, llm: OllamaClient):
        self.index = index
        self.llm = llm

    def answer(self, question: str, top_k: int = 3) -> str:
        results = self.index.retrieve(question, top_k)
        if not results:
            return "No relevant product information found."

        context_parts = []
        for i, prod in enumerate(results, 1):
            part = f"""
--- Product {i}: {prod['name']} (page {prod['page_start']})
Category: {prod['category']}
{subcategory_info if (subcategory_info := f"Subcategory: {prod['subcategory']}") else ""}
Relevant excerpt:
{prod['snippet']}
Full content (first 1500 chars):
{prod['content'][:1500]}
"""
            context_parts.append(part)
        context = "\n".join(context_parts)

        prompt = f"""You are a helpful assistant for a bank's product catalog. Answer the user's question **only** using the information below. If the answer is not present, say "I don't have that information."

Context:
{context}

User question: {question}

Answer concisely and accurately:"""

        return self.llm.generate(prompt)


# ----------------------------------------------------------------------
# 4. CLI
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
        print("\nAsk questions about the product catalog (type 'quit' to exit).")
        while True:
            q = input("\nYou: ").strip()
            if q.lower() in ("quit", "exit"):
                break
            if not q:
                continue
            print(f"\nAssistant: {rag.answer(q)}")
    else:
        # demo
        q = "What is the interest rate for credit Auto?"
        print(f"\nDemo: {q}")
        print(f"Answer: {rag.answer(q)}")