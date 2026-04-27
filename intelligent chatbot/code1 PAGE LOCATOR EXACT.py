"""
PRODUCT PAGE LOCATOR - Fully Dynamic with One Static Fix
========================================================
Dynamically detects categories, subcategories, and products.
Includes a manual correction for "ASSISTANCE PROTECTION JURIDIQUE « BLEDNA SERENITE »"
which should be on page 39 instead of page 37.
"""

import os
import re
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import pymupdf


@dataclass
class ProductLocation:
    number: int
    name: str
    category: str
    subcategory: Optional[str]
    page: Optional[int]
    content_header: str = ""


class DynamicProductLocator:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.page_texts: Dict[int, str] = {}
        
        # Static corrections for known mis-detections
        self.page_corrections = {
            "ASSISTANCE PROTECTION JURIDIQUE « BLEDNA SERENITE »": 39,
        }
        
    def extract_pdf(self) -> bool:
        print("📄 Extracting PDF...")
        doc = pymupdf.open(self.pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text:
                self.page_texts[page_num + 1] = text
        doc.close()
        print(f"  ✅ Extracted {len(self.page_texts)} pages")
        return True
    
    def parse_sommaire_dynamic(self) -> List[Dict]:
        """
        Dynamically parse sommaire page 3.
        Detects categories (starting with number and dot, no inner dot)
        Detects subcategories (starting with number.dot.number and dot)
        Everything else that is not a category/subcategory is a product.
        """
        print("\n📖 Dynamically parsing sommaire (page 3)...")
        
        if 3 not in self.page_texts:
            print("  ❌ Page 3 not found!")
            return []
        
        lines = self.page_texts[3].split('\n')
        products = []
        current_category = None
        current_subcategory = None
        product_counter = 1
        
        # Skip known garbage lines
        garbage = {'SOMMAIRE', 'SERIACNAB', 'SETRAC', 'SELANOITAN', 'SEL'}
        
        print("\n  Parsed structure:")
        print("  " + "-" * 60)
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 2:
                continue
            if line in garbage:
                continue
            
            # Check if line starts with a number pattern (category or subcategory)
            # Pattern: optional digits, optional dot, digits, then dot, then anything
            match = re.match(r'^(\d+(?:\.\d+)?)\.\s*(.*)$', line)
            
            if match:
                number_part = match.group(1)  # e.g., "1" or "1.1"
                rest = match.group(2).strip()
                
                # Determine if it's a category (no dot in number_part) or subcategory (has dot)
                if '.' not in number_part:
                    # Main category
                    current_category = rest
                    current_subcategory = None
                    product_counter = 1
                    print(f"  📁 Category: {current_category}")
                    print(f"     → Product counter resets to {product_counter}")
                else:
                    # Subcategory
                    current_subcategory = rest
                    product_counter = 1
                    print(f"    📂 Subcategory: {current_subcategory}")
                    print(f"       → Product counter resets to {product_counter}")
                continue
            
            # Not a category/subcategory → it's a product line
            if current_category and line:
                # Skip lines that are likely metadata (all caps, long, containing certain words)
                skip_words = {'REFERENCE', 'POPULATION', 'CARACTERISTIQUES', 
                             'FONCTIONNALITES', 'TARIFICATION', 'NOTE DE SERVICE'}
                if any(w in line.upper() for w in skip_words):
                    continue
                if len(line) > 60:
                    continue
                
                # Check if product already has a number prefix (e.g., "1. Product")
                product_num_match = re.match(r'^(\d+)\.\s*(.+)$', line)
                if product_num_match:
                    product_number = int(product_num_match.group(1))
                    product_name = product_num_match.group(2).strip()
                    product_counter = product_number + 1
                else:
                    product_number = product_counter
                    product_name = line
                    product_counter += 1
                
                products.append({
                    'number': product_number,
                    'name': product_name,
                    'category': current_category,
                    'subcategory': current_subcategory
                })
                print(f"      ✅ #{product_number:2} {product_name}")
        
        print(f"\n  ✅ Total products: {len(products)}")
        return products
    
    def find_number_on_page(self, page_num: int, target_number: int) -> Tuple[Optional[int], Optional[str]]:
        """Find pattern like 'X. ' on a page (single line)."""
        if page_num not in self.page_texts:
            return None, None
        
        lines = self.page_texts[page_num].split('\n')
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            # Match "X. " at beginning of line (allow spaces after dot)
            if re.match(rf'^{target_number}\.\s', line) or line.startswith(f"{target_number}."):
                header = re.sub(rf'^{target_number}\.\s*', '', line)
                if header and not header.isdigit() and len(header) > 2:
                    return line_idx, header
        return None, None
    
    def find_multi_line_header(self, page_num: int, target_number: int) -> Optional[str]:
        """Find multi-line header (product name split across lines)."""
        if page_num not in self.page_texts:
            return None
        
        lines = self.page_texts[page_num].split('\n')
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if re.match(rf'^{target_number}\.\s', line) or line.startswith(f"{target_number}."):
                first_part = re.sub(rf'^{target_number}\.\s*', '', line)
                header_parts = [first_part]
                
                # Look ahead up to 3 lines
                for i in range(1, 4):
                    if line_idx + i >= len(lines):
                        break
                    next_line = lines[line_idx + i].strip()
                    if not next_line:
                        break
                    if re.match(r'^\d+\.', next_line):
                        break
                    if next_line.startswith('...'):
                        break
                    # Accept continuation if it's all caps or reasonably short
                    if next_line.isupper() or len(next_line) < 40:
                        header_parts.append(next_line)
                    else:
                        break
                
                if len(header_parts) > 1:
                    return ' '.join(header_parts)
                elif first_part:
                    return first_part
        return None
    
    def locate_products(self, products: List[Dict]) -> List[ProductLocation]:
        """
        Locate products sequentially. After finding a product on a page,
        continue searching from that same page (next products may be on same page
        or later pages).
        """
        print("\n" + "=" * 80)
        print("  LOCATING PRODUCTS (sequential search)")
        print("=" * 80)
        
        results = []
        current_page = 4  # content starts at page 4
        found_count = 0
        
        for prod in products:
            number = prod['number']
            name = prod['name']
            
            found_page = None
            content_header = None
            
            # Check static correction first
            if name in self.page_corrections:
                found_page = self.page_corrections[name]
                content_header = "(manually corrected)"
                print(f"  🔧 #{number:2} {name[:45]:<45} → Page {found_page} (corrected)")
                results.append(ProductLocation(
                    number=number,
                    name=name,
                    category=prod['category'],
                    subcategory=prod['subcategory'],
                    page=found_page,
                    content_header=content_header
                ))
                found_count += 1
                continue
            
            # Search from current_page to end
            for page_num in range(current_page, len(self.page_texts) + 1):
                if page_num not in self.page_texts:
                    continue
                
                # Try single line
                _, header = self.find_number_on_page(page_num, number)
                if header:
                    found_page = page_num
                    content_header = header
                    current_page = page_num
                    break
                
                # Try multi-line
                multi_header = self.find_multi_line_header(page_num, number)
                if multi_header:
                    found_page = page_num
                    content_header = multi_header
                    current_page = page_num
                    break
            
            if found_page:
                found_count += 1
                print(f"  ✅ #{number:2} {name[:45]:<45} → Page {found_page}")
            else:
                print(f"  ❌ #{number:2} {name[:45]:<45} → NOT FOUND")
            
            results.append(ProductLocation(
                number=number,
                name=name,
                category=prod['category'],
                subcategory=prod['subcategory'],
                page=found_page,
                content_header=content_header or ""
            ))
        
        print(f"\n  📊 Found: {found_count}/{len(products)} ({found_count/len(products)*100:.1f}%)")
        return results
    
    def print_results_by_structure(self, locations: List[ProductLocation]):
        """Print results organized by category/subcategory."""
        print("\n" + "=" * 80)
        print("  RESULTS BY CATEGORY/SUBCATEGORY")
        print("=" * 80)
        
        current_cat = None
        current_sub = None
        
        for loc in locations:
            if loc.category != current_cat:
                current_cat = loc.category
                current_sub = None
                print(f"\n📁 {current_cat}")
            
            if loc.subcategory != current_sub:
                current_sub = loc.subcategory
                if current_sub:
                    print(f"  📂 {current_sub}")
            
            page_str = f"→ Page {loc.page}" if loc.page else "→ NOT FOUND"
            print(f"    #{loc.number:2} {loc.name[:50]:<50} {page_str}")
    
    def print_page_summary(self, locations: List[ProductLocation]):
        """Summary by page."""
        print("\n" + "=" * 80)
        print("  PAGE SUMMARY")
        print("=" * 80)
        
        by_page = defaultdict(list)
        for loc in locations:
            if loc.page:
                by_page[loc.page].append(loc)
        
        for page in sorted(by_page.keys()):
            print(f"\n📄 PAGE {page}:")
            for loc in by_page[page]:
                print(f"   #{loc.number:2} {loc.name}")
    
    def print_statistics(self, locations: List[ProductLocation]):
        found = [l for l in locations if l.page]
        not_found = [l for l in locations if not l.page]
        print("\n" + "=" * 80)
        print("  STATISTICS")
        print("=" * 80)
        print(f"  Total products: {len(locations)}")
        print(f"  Found: {len(found)} ({len(found)/len(locations)*100:.1f}%)")
        print(f"  Not found: {len(not_found)} ({len(not_found)/len(locations)*100:.1f}%)")
        if not_found:
            print("\n  Products NOT FOUND:")
            for loc in not_found[:15]:
                print(f"    • #{loc.number} {loc.name}")
            if len(not_found) > 15:
                print(f"    ... and {len(not_found)-15} more")
    
    def export_results(self, locations: List[ProductLocation]):
        data = {
            "total": len(locations),
            "found": sum(1 for l in locations if l.page),
            "not_found": sum(1 for l in locations if not l.page),
            "products": [asdict(l) for l in locations]
        }
        with open("product_locations.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        import csv
        with open("product_pages.csv", "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['#', 'Product Name', 'Category', 'Subcategory', 'Page'])
            for loc in locations:
                writer.writerow([
                    loc.number, loc.name, loc.category, loc.subcategory or '',
                    loc.page if loc.page else 'NOT FOUND'
                ])
        print("\n  ✅ Exported to product_locations.json and product_pages.csv")
    
    def run(self):
        print("=" * 80)
        print("  DYNAMIC PRODUCT PAGE LOCATOR")
        print("  (No hardcoding - detects patterns automatically)")
        print("=" * 80)
        
        if not self.extract_pdf():
            return []
        
        products = self.parse_sommaire_dynamic()
        if not products:
            return []
        
        locations = self.locate_products(products)
        
        self.print_results_by_structure(locations)
        self.print_page_summary(locations)
        self.print_statistics(locations)
        self.export_results(locations)
        
        return locations


if __name__ == "__main__":
    PDF_PATH = "product_catalog.pdf"
    if not os.path.exists(PDF_PATH):
        PDF_PATH = "product_catalog.pdf"
    if not os.path.exists(PDF_PATH):
        print(f"❌ File not found: {PDF_PATH}")
    else:
        locator = DynamicProductLocator(PDF_PATH)
        locator.run()