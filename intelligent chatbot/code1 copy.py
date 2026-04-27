import pdfplumber
import re
from typing import List, Dict, Tuple, Optional
import numpy as np
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import faiss
import os
from collections import defaultdict

@dataclass
class Product:
    name: str
    category: str
    subcategory: Optional[str]
    fields: Dict[str, str]
    page_number: int
    raw_text: str

class DynamicRAGSystem:
    def __init__(self, pdf_path: str, embedding_model: str = 'all-MiniLM-L6-v2'):
        self.pdf_path = pdf_path
        self.embedding_model = SentenceTransformer(embedding_model)
        self.products = []
        self.index = None
        
    def extract_sommaire_hierarchical(self, sommaire_text: str) -> List[Dict]:
        """Extract categories, subcategories, and products from hierarchical sommaire"""
        
        categories = []
        lines = sommaire_text.split('\n')
        
        current_category = None
        current_category_num = None
        current_subcategory = None
        current_subcategory_num = None
        current_products = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            main_category_match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if main_category_match:
                if current_category and current_products:
                    categories.append({
                        'category': current_category,
                        'category_num': current_category_num,
                        'subcategory': current_subcategory,
                        'subcategory_num': current_subcategory_num,
                        'products': current_products.copy()
                    })
                    current_products = []
                
                current_category_num = main_category_match.group(1)
                current_category = main_category_match.group(2).strip()
                current_subcategory = None
                current_subcategory_num = None
                continue
            
            subcategory_match = re.match(r'^(\d+\.\d+)\.?\s*(.+)$', line)
            if subcategory_match and current_category:
                if current_subcategory and current_products:
                    categories.append({
                        'category': current_category,
                        'category_num': current_category_num,
                        'subcategory': current_subcategory,
                        'subcategory_num': current_subcategory_num,
                        'products': current_products.copy()
                    })
                    current_products = []
                
                current_subcategory_num = subcategory_match.group(1)
                current_subcategory = subcategory_match.group(2).strip()
                continue
            
            if current_category and line:
                product_name = line.strip()
                product_name = re.sub(r'^\d+\.\d+\s*', '', product_name)
                product_name = re.sub(r'^\d+\.\s*', '', product_name)
                
                if product_name:
                    current_products.append(product_name)
        
        if current_category and current_products:
            categories.append({
                'category': current_category,
                'category_num': current_category_num,
                'subcategory': current_subcategory,
                'subcategory_num': current_subcategory_num,
                'products': current_products.copy()
            })
        
        return categories
    
    def extract_products_from_pdf(self, start_page: int, sommaire_products: List[str]) -> List[Product]:
        """Extract ONLY products that match sommaire products"""
        products = []
        
        # Normalize sommaire products for matching
        normalized_sommaire = {}
        for prod in sommaire_products:
            norm = self.normalize_product_name(prod)
            normalized_sommaire[norm] = prod
        
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num in range(start_page, len(pdf.pages)):
                page = pdf.pages[page_num]
                text = page.extract_text()
                
                if not text:
                    continue
                
                lines = text.split('\n')
                i = 0
                
                while i < len(lines):
                    line = lines[i].strip()
                    
                    if not line:
                        i += 1
                        continue
                    
                    # Skip page numbers and headers
                    if re.match(r'^\d+$', line) or line in ['SERIACNAB', 'SETRAC', 'SEL', 'SELANOITAN']:
                        i += 1
                        continue
                    
                    # Skip reversed text
                    if any(pattern in line for pattern in ['SELANOITANRETNI', 'SERIACNAB', 'SETRAC', 'ECNATSID', 'SECIVRES']):
                        i += 1
                        continue
                    
                    # Skip sommaire remnants
                    if (re.match(r'^\d+\.\d+', line) or re.match(r'^\d+\.', line) or
                        'SOMMAIRE' in line or 'CATALOGUE' in line):
                        i += 1
                        continue
                    
                    # Skip spaced-out words
                    if re.search(r'[A-Z]\s+[A-Z]\s+[A-Z]', line):
                        i += 1
                        continue
                    
                    # Check if line could be a product name
                    is_field = bool(re.match(r'^[A-Z][A-Z\s]{2,}:', line))
                    
                    # Clean potential product name
                    product_name_clean = re.sub(r'\s+Note de service.*$', '', line)
                    product_name_clean = re.sub(r'\s+Note.*$', '', product_name_clean)
                    product_name_clean = re.sub(r'\s+\(.*?\)', '', product_name_clean)
                    product_name_clean = re.sub(r'\s+•', '', product_name_clean)
                    
                    # Check if this matches any sommaire product
                    norm_candidate = self.normalize_product_name(product_name_clean)
                    matched_sommaire = None
                    
                    for sommaire_norm, sommaire_orig in normalized_sommaire.items():
                        if (norm_candidate == sommaire_norm or 
                            sommaire_norm in norm_candidate or 
                            norm_candidate in sommaire_norm):
                            matched_sommaire = sommaire_orig
                            break
                    
                    if matched_sommaire:
                        # This is a product we want
                        complete_product_name = matched_sommaire  # Use sommaire name as canonical
                        product_content = []
                        j = i + 1
                        
                        # Collect product content until next product or end
                        while j < len(lines):
                            next_line = lines[j].strip()
                            if not next_line:
                                j += 1
                                continue
                            
                            # Check if next line starts a new product
                            next_clean = re.sub(r'\s+Note de service.*$', '', next_line)
                            next_norm = self.normalize_product_name(next_clean)
                            
                            is_next_product = False
                            for sommaire_norm in normalized_sommaire.keys():
                                if (next_norm == sommaire_norm or 
                                    sommaire_norm in next_norm or 
                                    next_norm in sommaire_norm):
                                    is_next_product = True
                                    break
                            
                            if is_next_product:
                                break
                            
                            # Skip field names and other noise
                            if not re.match(r'^[A-Z][A-Z\s]{2,}:', next_line):
                                product_content.append(next_line)
                            j += 1
                        
                        # Extract fields from content
                        fields = self.extract_fields(product_content)
                        
                        # Check if we already have this product
                        existing = None
                        for p in products:
                            if self.normalize_product_name(p.name) == self.normalize_product_name(complete_product_name):
                                existing = p
                                break
                        
                        if existing:
                            # Merge content
                            if product_content:
                                existing.raw_text += "\n" + '\n'.join(product_content)
                            existing.fields.update(fields)
                        else:
                            products.append(Product(
                                name=complete_product_name,
                                category="",
                                subcategory=None,
                                fields=fields,
                                page_number=page_num + 1,
                                raw_text='\n'.join(product_content)
                            ))
                        
                        i = j
                    else:
                        i += 1
        
        return products
    
    def extract_fields(self, content_lines: List[str]) -> Dict[str, str]:
        """Extract UPPERCASE fields from product content"""
        fields = {}
        full_text = '\n'.join(content_lines)
        lines = full_text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            match = re.match(r'^([A-Z][A-Z\s]{2,}):?\s*(.*)$', line)
            
            if match:
                field_name = match.group(1).strip()
                field_value = match.group(2).strip()
                
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if re.match(r'^[A-Z][A-Z\s]{2,}:?', next_line):
                        break
                    if next_line and not next_line[0].isdigit():
                        field_value += " " + next_line
                    j += 1
                
                if field_name and field_value:
                    field_value = re.sub(r'\s+', ' ', field_value).strip()
                    fields[field_name] = field_value[:500]
        
        return fields
    
    def normalize_product_name(self, name: str) -> str:
        """Normalize product name for matching"""
        normalized = name.lower().strip()
        normalized = re.sub(r'[éèêë]', 'e', normalized)
        normalized = re.sub(r'[àâä]', 'a', normalized)
        normalized = re.sub(r'[ôö]', 'o', normalized)
        normalized = re.sub(r'[ç]', 'c', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()
    
    def match_products_to_categories(self, products: List[Product], sommaire_categories: List[Dict]) -> List[Product]:
        """Match products to their categories from sommaire"""
        
        # Build mapping from product name to category
        product_to_category = {}
        for cat in sommaire_categories:
            category = cat['category']
            subcategory = cat.get('subcategory')
            for product_name in cat['products']:
                normalized = self.normalize_product_name(product_name)
                product_to_category[normalized] = (category, subcategory, product_name)
        
        matched = []
        for product in products:
            product_norm = self.normalize_product_name(product.name)
            
            if product_norm in product_to_category:
                category, subcategory, original = product_to_category[product_norm]
                product.category = category
                product.subcategory = subcategory
                matched.append(product)
            else:
                # Try fuzzy match
                for sommaire_norm, (category, subcategory, original) in product_to_category.items():
                    if product_norm in sommaire_norm or sommaire_norm in product_norm:
                        product.category = category
                        product.subcategory = subcategory
                        matched.append(product)
                        break
        
        return matched
    
    def create_embeddings(self):
        """Create FAISS index"""
        texts = []
        for product in self.products:
            text = f"Category: {product.category}\n"
            if product.subcategory:
                text += f"Subcategory: {product.subcategory}\n"
            text += f"Product: {product.name}\n"
            for field_name, field_value in product.fields.items():
                text += f"{field_name}: {field_value[:200]}\n"
            texts.append(text)
        
        embeddings = self.embedding_model.encode(texts)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings).astype('float32'))
    
    def build_rag_system(self):
        """Build complete RAG system"""
        
        # Extract sommaire
        print("📖 Extracting sommaire from PDF...")
        sommaire_text = ""
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num in range(min(3, len(pdf.pages))):
                text = pdf.pages[page_num].extract_text()
                if text and ('SOMMAIRE' in text or '1.' in text[:100]):
                    sommaire_text = text
                    break
        
        if not sommaire_text:
            print("❌ Could not find sommaire")
            return []
        
        print("\n📑 Parsing hierarchical sommaire...")
        categories = self.extract_sommaire_hierarchical(sommaire_text)
        
        # Collect all product names from sommaire
        all_sommaire_products = []
        for cat in categories:
            all_sommaire_products.extend(cat['products'])
        
        print(f"\n✅ Found {len(categories)} categories with {len(all_sommaire_products)} total products:\n")
        for cat in categories:
            print(f"  {cat['category_num']}. {cat['category']}")
            if cat['subcategory']:
                print(f"    {cat['subcategory_num']}. {cat['subcategory']}")
            for product in cat['products'][:5]:
                print(f"      - {product}")
            if len(cat['products']) > 5:
                print(f"      ... and {len(cat['products'])-5} more")
        
        print("\n📄 Extracting products from PDF (only matching sommaire)...")
        start_page = 5
        all_products = self.extract_products_from_pdf(start_page, all_sommaire_products)
        print(f"  Found {len(all_products)} matching product sections")
        
        print("\n🔗 Matching products to categories...")
        self.products = self.match_products_to_categories(all_products, categories)
        print(f"  ✅ Matched {len(self.products)} products")
        
        if self.products:
            print("\n📊 Products by category:")
            category_stats = defaultdict(list)
            for p in self.products:
                category_stats[p.category].append(p.name)
            
            for cat, prods in category_stats.items():
                print(f"\n  {cat}: {len(prods)} products")
                for prod in prods:
                    print(f"    - {prod}")
            
            print("\n📊 Creating FAISS index...")
            self.create_embeddings()
            print(f"  Index ready with {self.index.ntotal} vectors")
        
        return self.products
    
    def query(self, question: str, top_k: int = 3) -> List[Tuple[Product, float]]:
        """Query the system"""
        if not self.index:
            raise ValueError("System not built")
        
        query_embedding = self.embedding_model.encode([question])
        distances, indices = self.index.search(
            np.array(query_embedding).astype('float32'),
            min(top_k, self.index.ntotal)
        )
        
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx != -1:
                similarity = 1 / (1 + dist)
                results.append((self.products[idx], similarity))
        
        return results
    
    def format_response(self, product: Product, similarity: float) -> str:
        """Format response"""
        response = f"""
{'='*60}
📦 **{product.name}**
📂 Category: {product.category}
{f'📁 Subcategory: {product.subcategory}' if product.subcategory else ''}
📍 Page: {product.page_number} | Relevance: {similarity:.2%}
{'─'*60}
"""
        if product.fields:
            for field_name, field_value in list(product.fields.items())[:8]:
                display = field_value[:100] + "..." if len(field_value) > 100 else field_value
                response += f"• **{field_name}**: {display}\n"
        else:
            response += "• No structured fields found\n"
        
        return response

# Main execution
if __name__ == "__main__":
    PDF_PATH = "product_catalog.pdf"
    
    if not os.path.exists(PDF_PATH):
        print(f"❌ Error: {PDF_PATH} not found!")
    else:
        print("="*60)
        print("DYNAMIC RAG SYSTEM - Banking Products Catalog")
        print("="*60)
        
        rag = DynamicRAGSystem(PDF_PATH)
        products = rag.build_rag_system()
        
        if products:
            print("\n" + "="*60)
            print("✅ RAG SYSTEM READY")
            print("="*60)
            
            while True:
                print("\n" + "─"*60)
                query = input("🔍 Question (or 'quit'): ").strip()
                
                if query.lower() in ['quit', 'exit', 'q']:
                    break
                
                if not query:
                    continue
                
                results = rag.query(query, top_k=3)
                if not results:
                    print("❌ No relevant products found")
                    continue
                
                for product, score in results:
                    print(rag.format_response(product, score))
        else:
            print("\n❌ No products were matched.")