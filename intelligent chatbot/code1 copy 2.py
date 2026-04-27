
"""
extraction produit name correctly
FIXED RAG SYSTEM - Handles Multi-line Product Headers
=====================================================
- Searches for product names that are split across multiple lines
- Combines consecutive lines to match multi-line headers
"""

import os
import re
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import pymupdf


@dataclass
class Product:
    name: str
    category: str
    subcategory: Optional[str]
    content: str
    page: int
    reference: Optional[str] = None
    audience: Optional[str] = None
    features: Optional[str] = None
    pricing: Optional[str] = None


class FixedRAGSystem:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.products: List[Product] = []
        self.page_texts: Dict[int, str] = {}
    
    def extract_pdf(self) -> bool:
        """Extract PDF using pymupdf."""
        try:
            print("\n📄 Extracting PDF with PyMuPDF...")
            doc = pymupdf.open(self.pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text:
                    self.page_texts[page_num + 1] = text
            doc.close()
            print(f"  ✅ Extracted {len(self.page_texts)} pages")
            return True
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False
    
    def parse_sommaire(self) -> List[Dict]:
        """Parse sommaire from page 3."""
        print("\n📖 Parsing sommaire (page 3)...")
        
        if 3 not in self.page_texts:
            print("  ❌ Page 3 not found!")
            return []
        
        lines = self.page_texts[3].split('\n')
        products = []
        current_category = None
        current_subcategory = None
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 2:
                continue
            
            garbage = ['SOMMAIRE', 'SERIACNAB', 'SETRAC', 'SELANOITAN', 'SEL', 'Expires end']
            if line in garbage or line.isdigit():
                continue
            
            cat_match = re.match(r'^(\d+)\.([A-Z][A-Z\s]+)$', line)
            if cat_match:
                current_category = cat_match.group(2).strip()
                current_subcategory = None
                print(f"  📁 {current_category}")
                continue
            
            sub_match = re.match(r'^(\d+\.\d+)([A-Z][A-Z\s]+)$', line)
            if sub_match:
                current_subcategory = sub_match.group(2).strip()
                print(f"    📂 {current_subcategory}")
                continue
            
            if current_category and line:
                skip_words = ['REFERENCE', 'POPULATION', 'CARACTERISTIQUES', 
                             'FONCTIONNALITES', 'TARIFICATION', 'NOTE DE SERVICE']
                if any(word in line.upper() for word in skip_words):
                    continue
                if len(line) > 60:
                    continue
                if line[0].isdigit():
                    continue
                
                products.append({
                    'name': line,
                    'category': current_category,
                    'subcategory': current_subcategory
                })
        
        print(f"  ✅ Found {len(products)} products in sommaire")
        return products
    
    def find_product_content(self, product_name: str) -> Tuple[int, str]:
        """Find product content - handles multi-line headers."""
        
        # Split product name into words for multi-line matching
        product_words = product_name.split()
        
        # Create variations
        variations = [
            product_name,
            product_name.upper(),
            product_name.title(),
        ]
        
        # Remove accents
        no_accents = product_name
        for a, b in [('é','e'), ('è','e'), ('ê','e'), ('à','a'), ('â','a'), ('ç','c')]:
            no_accents = no_accents.replace(a, b).replace(a.upper(), b.upper())
        variations.append(no_accents.upper())
        
        # Remove prefix
        for prefix in ['LE ', 'LA ', 'LES ']:
            if product_name.upper().startswith(prefix):
                without_prefix = product_name[len(prefix):]
                variations.append(without_prefix)
                variations.append(without_prefix.upper())
        
        variations = list(dict.fromkeys(variations))
        
        # Search ALL content pages (from page 5 onward)
        for page_num in range(5, len(self.page_texts) + 1):
            if page_num not in self.page_texts:
                continue
            
            lines = self.page_texts[page_num].split('\n')
            
            # First try: exact match on a single line
            for line_idx, line in enumerate(lines):
                line_clean = line.strip()
                if not line_clean:
                    continue
                
                line_for_compare = re.sub(r'^\d+\.\s*', '', line_clean)
                line_upper = line_for_compare.upper()
                
                for variant in variations:
                    variant_upper = variant.upper()
                    
                    if line_upper == variant_upper:
                        return page_num, self._extract_content(lines, line_idx)
                    
                    if line_upper.startswith(variant_upper):
                        remainder = line_upper[len(variant_upper):]
                        if not remainder or remainder[0] in ' ,.:;!?':
                            return page_num, self._extract_content(lines, line_idx)
            
            # Second try: multi-line match (product split across consecutive lines)
            for line_idx in range(len(lines) - 2):
                line1 = lines[line_idx].strip()
                line2 = lines[line_idx + 1].strip() if line_idx + 1 < len(lines) else ""
                line3 = lines[line_idx + 2].strip() if line_idx + 2 < len(lines) else ""
                
                # Remove number prefixes
                line1_clean = re.sub(r'^\d+\.\s*', '', line1)
                line2_clean = re.sub(r'^\d+\.\s*', '', line2)
                line3_clean = re.sub(r'^\d+\.\s*', '', line3)
                
                # Combine 2 lines
                combined_2 = f"{line1_clean} {line2_clean}".upper()
                # Combine 3 lines
                combined_3 = f"{line1_clean} {line2_clean} {line3_clean}".upper()
                
                # Remove extra spaces
                combined_2 = re.sub(r'\s+', ' ', combined_2).strip()
                combined_3 = re.sub(r'\s+', ' ', combined_3).strip()
                
                for variant in variations:
                    variant_upper = variant.upper()
                    
                    # Check 2-line combination
                    if combined_2 == variant_upper or combined_2.startswith(variant_upper):
                        # Found it across 2 lines - reconstruct the actual header
                        header = f"{line1} {line2}".strip()
                        # Replace the 2 lines with combined header in content
                        modified_lines = lines.copy()
                        modified_lines[line_idx] = header
                        modified_lines.pop(line_idx + 1)
                        return page_num, self._extract_content(modified_lines, line_idx)
                    
                    # Check 3-line combination
                    if combined_3 == variant_upper or combined_3.startswith(variant_upper):
                        header = f"{line1} {line2} {line3}".strip()
                        modified_lines = lines.copy()
                        modified_lines[line_idx] = header
                        modified_lines.pop(line_idx + 1)
                        modified_lines.pop(line_idx + 1)
                        return page_num, self._extract_content(modified_lines, line_idx)
        
        return 0, ""
    
    def _extract_content(self, lines: List[str], start_idx: int) -> str:
        """Extract content from start position."""
        content_lines = [lines[start_idx].strip()]
        
        for next_idx in range(start_idx + 1, min(start_idx + 150, len(lines))):
            next_line = lines[next_idx].strip()
            if not next_line:
                content_lines.append('')
                continue
            
            # Stop if we hit another product header
            next_clean = re.sub(r'^\d+\.\s*', '', next_line)
            if next_clean.isupper() and 3 < len(next_clean) < 60:
                if not any(next_line.startswith(m) for m in ['REFERENCE', 'POPULATION']):
                    break
            
            content_lines.append(next_line)
        
        return '\n'.join(content_lines)
    
    def extract_fields(self, content: str) -> Dict:
        """Extract structured fields from content."""
        fields = {'reference': None, 'audience': None, 'features': None, 'pricing': None}
        
        ref_match = re.search(r'REFERENCE\s*:?\s*(.+?)(?=\n[A-Z]|\n\n|\Z)', content, re.IGNORECASE | re.DOTALL)
        if ref_match:
            fields['reference'] = ref_match.group(1).strip()[:200]
        
        aud_match = re.search(r'POPULATION CIBLE\s*:?\s*(.+?)(?=\n[A-Z]|\n\n|\Z)', content, re.IGNORECASE | re.DOTALL)
        if aud_match:
            fields['audience'] = aud_match.group(1).strip()[:350]
        
        feat_match = re.search(r'CARACTERISTIQUES\s*:?\s*(.+?)(?=\n[A-Z]|\n\n|\Z)', content, re.IGNORECASE | re.DOTALL)
        if not feat_match:
            feat_match = re.search(r'FONCTIONNALITES\s*:?\s*(.+?)(?=\n[A-Z]|\n\n|\Z)', content, re.IGNORECASE | re.DOTALL)
        if feat_match:
            fields['features'] = feat_match.group(1).strip()[:400]
        
        price_match = re.search(r'TARIFICATION\s*:?\s*(.+?)(?=\n[A-Z]|\n\n|\Z)', content, re.IGNORECASE | re.DOTALL)
        if price_match:
            fields['pricing'] = price_match.group(1).strip()[:250]
        
        return fields
    
    def build(self) -> List[Product]:
        """Build the RAG system."""
        print("=" * 65)
        print("  FIXED RAG SYSTEM - Multi-line Header Support")
        print("=" * 65)
        
        if not self.extract_pdf():
            return []
        
        sommaire_products = self.parse_sommaire()
        if not sommaire_products:
            return []
        
        print("\n📝 Extracting product content...")
        self.products = []
        
        found_count = 0
        for i, prod_info in enumerate(sommaire_products):
            product_name = prod_info['name']
            page_num, content = self.find_product_content(product_name)
            
            if not content:
                print(f"  ❌ Not found: {product_name[:45]}")
                continue
            
            fields = self.extract_fields(content)
            
            product = Product(
                name=product_name,
                category=prod_info['category'],
                subcategory=prod_info['subcategory'],
                content=content[:2000],
                page=page_num,
                reference=fields['reference'],
                audience=fields['audience'],
                features=fields['features'],
                pricing=fields['pricing']
            )
            self.products.append(product)
            found_count += 1
            
            if found_count % 10 == 0:
                print(f"  ✅ Found {found_count}/{len(sommaire_products)} products")
        
        print(f"\n✅ Extracted {len(self.products)} products")
        
        # Export
        self.export_json()
        return self.products
    
    def export_json(self, filename: str = "products_fixed.json"):
        """Export to JSON."""
        data = {
            "total": len(self.products),
            "products": [
                {
                    "name": p.name,
                    "category": p.category,
                    "subcategory": p.subcategory,
                    "page": p.page,
                    "reference": p.reference,
                    "audience": p.audience[:300] if p.audience else None,
                    "features": p.features[:400] if p.features else None,
                    "pricing": p.pricing[:200] if p.pricing else None,
                }
                for p in self.products
            ]
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✅ Exported to {filename}")
    
    def ask(self, question: str) -> str:
        """Simple question answering."""
        if not self.products:
            return "Système non initialisé."
        
        q = question.lower()
        best = None
        best_score = 0
        
        for p in self.products:
            score = 0
            if p.name.lower() in q:
                score = 100
            elif any(word in p.name.lower() for word in q.split() if len(word) > 3):
                score = 50
            
            if score > best_score:
                best_score = score
                best = p
        
        if not best or best_score < 30:
            return "Désolé, je n'ai pas trouvé de produit correspondant."
        
        # Simple response
        if any(w in q for w in ['frais', 'prix', 'tarif']):
            if best.pricing:
                return f"**{best.name}**\n\n{best.pricing}"
            return f"Je n'ai pas d'information sur les frais de {best.name}."
        
        if any(w in q for w in ['qui', 'client', 'cible']):
            if best.audience:
                return f"**{best.name}**\n\n{best.audience}"
        
        if best.features:
            return f"**{best.name}**\n\n{best.features[:350]}"
        
        return f"**{best.name}**\n\n{best.content[:350]}"
    
    def chat(self):
        """Interactive chat."""
        print("\n" + "=" * 55)
        print("  💬 ASSISTANT BANCAIRE BH")
        print("=" * 55)
        print("\n✨ Tapez 'quit' pour quitter\n")
        
        while True:
            q = input("🔍 Vous: ").strip()
            if q.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Au revoir!")
                break
            if q:
                response = self.ask(q)
                print(f"\n💬 {response}\n")


if __name__ == "__main__":
    PDF_PATH = "product_catalog.pdf"
    
    if not os.path.exists(PDF_PATH):
        print(f"❌ File not found: {PDF_PATH}")
    else:
        rag = FixedRAGSystem(PDF_PATH)
        products = rag.build()
        
        if products:
            print("\n" + "=" * 65)
            print(f"✅ Ready! {len(products)} products loaded")
            rag.chat()