"""
PRODUCT PAGE LOCATOR - Final Corrected Version
===============================================
- Extracts full content for all products, including multi-page
- Properly handles Assur Senior (pages 37-40)
- Includes manually corrected product in correct sequence
"""

import os
import re
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import pymupdf # High performance PDF text extraction


@dataclass
class ProductContent:
    # Stores the extracted content for a single product
    number: int
    name: str
    category: str
    subcategory: Optional[str]
    page_start: int
    page_end: int
    content: str
    confidence: str = "high" # "high" for auto-extracted, "manual" for manually added products


class FinalProductExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        # Store full text of that page page_texts[page_num] = text
        self.page_texts: Dict[int, str] = {}
        
        # Static page correction for one product
        self.page_corrections = {
            "ASSISTANCE PROTECTION JURIDIQUE « BLEDNA SERENITE »": 39,
        }
        
    def extract_pdf(self) -> bool:
        #Read all pages from PDF & store in page_texts
        print("📄 Extracting PDF...")
        doc = pymupdf.open(self.pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text:
                # Convert to 1‑based page numbers for readability
                self.page_texts[page_num + 1] = text
        doc.close()
        print(f"  ✅ Extracted {len(self.page_texts)} pages")
        return True
    
    def parse_sommaire_with_subcategories(self) -> List[Dict]:
        """Parse sommaire page 3, preserving category and subcategory."""
        print("\n📖 Parsing sommaire (page 3) with subcategories...")
        
        if 3 not in self.page_texts:
            print("  ❌ Page 3 not found!")
            return []
        
        #Split page 3 into lines 
        lines = self.page_texts[3].split('\n')
        products = []
        current_category = None
        current_subcategory = None
        product_counter = 1
        
        garbage = {'SOMMAIRE', 'SERIACNAB', 'SETRAC', 'SELANOITAN', 'SEL'}
        
        print("\n  Parsed structure:")
        print("  " + "-" * 60)
        
        for line in lines:
            #Remove  whitespace a
            line = line.strip()
            if not line or len(line) < 2: # Skip empty or very short lines
                continue
            if line in garbage: # Skip known garbage lines
                continue
            
            # Detecting Main category: "1.LES CARTES BANCAIRES"
            cat_match = re.match(r'^(\d+)\.(\s*)([A-Z][A-Z\s\u00C0-\u00FF]+)$', line, re.UNICODE) #Pattern for main category
            if cat_match:
                current_category = cat_match.group(3).strip()
                current_subcategory = None
                product_counter = 1
                print(f"  📁 Category: {current_category}")
                print(f"     → Product counter resets to {product_counter}")
                continue
            
            # Subcategory: "1.1LES CARTES NATIONALES"
            sub_match = re.match(r'^(\d+\.\d+)(\s*)([A-Z][A-Z\s\u00C0-\u00FF]+)$', line, re.UNICODE)
            if sub_match:
                current_subcategory = sub_match.group(3).strip()
                product_counter = 1
                print(f"    📂 Subcategory: {current_subcategory}")
                print(f"       → Product counter resets to {product_counter}")
                continue
            
            # Product line
            if current_category and line:
                skip_words = {'REFERENCE', 'POPULATION', 'CARACTERISTIQUES', 
                             'FONCTIONNALITES', 'TARIFICATION', 'NOTE DE SERVICE'}
                if any(w in line.upper() for w in skip_words):
                    continue
                if len(line) > 60:
                    continue
                
                product_num_match = re.match(r'^(\d+)\.\s*(.+)$', line)
                if product_num_match:
                    product_number = int(product_num_match.group(1)) # the number before the dot
                    product_name = product_num_match.group(2).strip() # the name after the dot
                    product_counter = product_number + 1 # case where the next product might not have a number
                else:
                    product_number = product_counter #we use the current counter if no number is found
                    product_name = line #we take the whole line as product name 
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
        """Find a line starting with  'X. ' on a single page."""
        if page_num not in self.page_texts:
            return None, None
        
        lines = self.page_texts[page_num].split('\n')
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            if re.match(rf'^{target_number}\.\s', line) or line.startswith(f"{target_number}."): # Match "X. " at start of line example "5. " or "5."
                header = re.sub(rf'^{target_number}\.\s*', '', line) # Remove the number and dot to get the header text
                if header and not header.isdigit() and len(header) > 2: #Filter out false positives that are just numbers or very short
                    return line_idx, header
        return None, None
    
    def find_multi_line_header(self, page_num: int, target_number: int) -> Tuple[Optional[int], Optional[str]]:
        """Find multi-line header and return start line index and full header."""
        if page_num not in self.page_texts:
            return None, None
        
        lines = self.page_texts[page_num].split('\n')
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            if re.match(rf'^{target_number}\.\s', line) or line.startswith(f"{target_number}."): # Match "X. " at start of line example "5. " or "5."
                first_part = re.sub(rf'^{target_number}\.\s*', '', line) # Remove the number and dot to get the first part of the header
                header_parts = [first_part]
                
                # Look ahead up to 4 lines to see if they are part of the header (e.g. all uppercase, short lines, or not starting with a number)
                for i in range(1, 5):
                    if line_idx + i >= len(lines):
                        break
                    next_line = lines[line_idx + i].strip()
                    if not next_line:
                        break
                    if re.match(r'^\d+\.', next_line): #Stop if the next product starts
                        break
                    if re.match(r'^(REFERENCE|POPULATION|CARACTERISTIQUES|FONCTIONNALITES|TARIFICATION|NOTE DE SERVICE|OBJET|CIBLE|GARANTIES)', next_line, re.IGNORECASE): #Stop if we hit a common section header
                        break
                    if next_line.startswith('...'):
                        break
                    if next_line.isupper() or len(next_line) < 60: #If line all uppercase or short , it's likely part of the header
                        header_parts.append(next_line)
                    else:
                        break
                
                full_header = ' '.join(header_parts)
                if len(full_header) > len(first_part):#Return the longer he der if we added lines , else just the first part
                    return line_idx, full_header
                elif first_part:
                    return line_idx, first_part
        
        return None, None
    
    def locate_products(self, products: List[Dict]) -> List[Dict]:
        """Locate each product's starting page using sequential search.Starting from the previous product's page for efficiency."""
        print("\n" + "=" * 80)
        print("  LOCATING PRODUCTS (sequential search)")
        print("=" * 80)
        
        results = []
        current_page = 4 #Table of contents starts at page 3, so we can start searching from page 4
        found_count = 0
        
        for prod in products:
            number = prod['number']
            name = prod['name']
            
            found_page = None
            line_idx = None
            
            if name in self.page_corrections:#Check if we have a manual correction for this product's page
                found_page = self.page_corrections[name]
                print(f"  🔧 #{number:2} {name[:45]:<45} → Page {found_page} (corrected)")
                prod['page'] = found_page
                prod['line_idx'] = None
                results.append(prod)
                found_count += 1
                continue
            
            for page_num in range(current_page, len(self.page_texts) + 1): #Search from current page to the end
                if page_num not in self.page_texts:
                    continue
                
                idx, _ = self.find_multi_line_header(page_num, number) #if we have multi-line headers
                if idx is not None:
                    found_page = page_num
                    line_idx = idx
                    current_page = page_num #Advance for next search
                    break
                
                idx2, _ = self.find_number_on_page(page_num, number) #Single-line detection
                if idx2 is not None:
                    found_page = page_num
                    line_idx = idx2
                    current_page = page_num
                    break
            
            if found_page:
                found_count += 1
                print(f"  ✅ #{number:2} {name[:45]:<45} → Page {found_page}")
                prod['page'] = found_page
                prod['line_idx'] = line_idx
            else:
                print(f"  ❌ #{number:2} {name[:45]:<45} → NOT FOUND")
                prod['page'] = None
            
            results.append(prod)
        
        print(f"\n  📊 Found: {found_count}/{len(products)} ({found_count/len(products)*100:.1f}%)")
        return results
    
    def extract_product_content(self, products_with_pages: List[Dict]) -> List[ProductContent]:
        """
        Extract FULL content for each product.
        Determines end boundary by looking at the next product's start position.
        """
        print("\n" + "=" * 80)
        print("  EXTRACTING PRODUCT CONTENT (multi-page support)")
        print("=" * 80)
        
        # Build a list of products that have valid start page with line index.
        product_positions = []
        for prod in products_with_pages:
            if prod.get('page') is None: #Skip product that were not found == page not located 
                continue
            number = prod['number']
            page = prod['page']
            line_idx = prod.get('line_idx')
            # If line index is not found for example for the manually corrected product we try to find it by searching for the product number on that page 
            if line_idx is None:
                lines = self.page_texts[page].split('\n')
                for i, line in enumerate(lines):
                    if re.match(rf'^{number}\.\s', line.strip()):
                        line_idx = i
                        break # once we find the line index we can stop searching
            if line_idx is not None:
                product_positions.append({
                    'number': number,
                    'name': prod['name'],
                    'prod': prod,
                    'page': page,
                    'line_idx': line_idx
                })
        
        # Sort by page then line index to ensure correct order for content extraction
        product_positions.sort(key=lambda x: (x['page'], x['line_idx']))
        
        product_contents = []
        
        for idx, pos in enumerate(product_positions):
            prod = pos['prod']
            number = pos['number']
            name = prod['name']
            start_page = pos['page']
            start_line = pos['line_idx']
            
            # Determine end page and line by finding the next product number in the PDF
            end_page = start_page # Default to same page assuming product content is on one page, we will adjust if we find the next product on a later page
            end_line = len(self.page_texts[start_page].split('\n')) - 1
            
            # Look for next product in the sorted list
            next_pos = product_positions[idx + 1] if idx + 1 < len(product_positions) else None
            
            if next_pos:
                next_page = next_pos['page']
                next_line = next_pos['line_idx']
                
                if next_page == start_page:
                    # Same page: end before next product's line
                    end_line = next_line - 1
                    end_page = start_page
                else:
                    # Different page: product spans from start_page to next_page-1
                    end_page = next_page - 1
                    # For the start page, we only take from start_line to end of page
                    # For pages in between, take whole pages
                    # The last page (end_page) we take all lines (no cut because next product is on a later page)
                    pass
            else:
                # Last product: go to end of PDF
                end_page = max(self.page_texts.keys())
            
            # Collect content
            content_parts = []
            for page_num in range(start_page, end_page + 1):
                if page_num not in self.page_texts:
                    continue
                page_lines = self.page_texts[page_num].split('\n')
                if page_num == start_page:
                    # From start_line to end of page
                    content_parts.extend(page_lines[start_line:])
                else:
                    # Entire page
                    content_parts.extend(page_lines)
            
            full_content = '\n'.join(content_parts).strip()
            
            # If there is a next product, ensure we cut at its number (in case it appears mid-page on the last page)
            if next_pos and next_pos['page'] == end_page:
                # The next product is on the same page as our end_page? That shouldn't happen because end_page = next_page-1.
                pass
            elif next_pos:
                # We might have captured extra content if the next product appears on a page we included incorrectly.
                # To be safe, search for the next product number in the full_content and cut there.
                next_number = next_pos['number']
                pattern = rf'\n{next_number}\.'
                match = re.search(pattern, full_content)
                if match:
                    full_content = full_content[:match.start()].strip()
            
            # Clean up: remove trailing category footers
            lines_clean = full_content.split('\n')
            if len(lines_clean) > 1:
                last_line = lines_clean[-1].strip()
                if last_line.isupper() and len(last_line) > 10 and ' ' in last_line:
                    full_content = '\n'.join(lines_clean[:-1]).strip()
            
            product_contents.append(ProductContent(
                number=number,
                name=name,
                category=prod['category'],
                subcategory=prod['subcategory'],
                page_start=start_page,
                page_end=end_page,
                content=full_content,
                confidence="high"
            ))
            
            line_count = len(full_content.split('\n'))
            print(f"  ✅ Extracted #{number:2} {name[:45]:<45} (pages {start_page}-{end_page}, {line_count} lines)")
        
        # Add the manually corrected product if not already included (it should be in product_positions, but double-check)
        for name, page in self.page_corrections.items():
            if not any(pc.name == name for pc in product_contents):
                original = next((p for p in products_with_pages if p['name'] == name), None)
                if original and page in self.page_texts:
                    # Extract content from that page (assuming it doesn't span pages)
                    # Find the start line
                    lines = self.page_texts[page].split('\n')
                    start_line = None
                    for i, line in enumerate(lines):
                        if re.match(rf'^{original["number"]}\.\s', line.strip()):
                            start_line = i
                            break
                    if start_line is not None:
                        content = '\n'.join(lines[start_line:]).strip()
                    else:
                        content = self.page_texts[page].strip()
                    product_contents.append(ProductContent(
                        number=original['number'],
                        name=original['name'],
                        category=original['category'],
                        subcategory=original['subcategory'],
                        page_start=page,
                        page_end=page,
                        content=content,
                        confidence="manual"
                    ))
                    print(f"  🔧 Manually added #{original['number']} {name[:45]} (page {page})")
        
        return product_contents
    
    def export_to_json(self, product_contents: List[ProductContent], output_path: str = "product_contents.json"):
        """Export all product content to a structured JSON file."""
        # Sort by page_start then number for consistent output
        product_contents.sort(key=lambda x: (x.page_start, x.number))
        
        data = {
            "total_products": len(product_contents),
            "products": []
        }
        
        for pc in product_contents:
            data["products"].append({
                "number": pc.number,
                "name": pc.name,
                "category": pc.category,
                "subcategory": pc.subcategory,
                "page_start": pc.page_start,
                "page_end": pc.page_end,
                "confidence": pc.confidence,
                "content": pc.content
            })
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n  ✅ Exported {len(product_contents)} products to {output_path}")
        
        # Also save a summary CSV
        import csv
        csv_path = output_path.replace('.json', '.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['#', 'Product Name', 'Category', 'Subcategory', 'Pages', 'Content Length (chars)'])
            for pc in product_contents:
                pages_str = f"{pc.page_start}" if pc.page_start == pc.page_end else f"{pc.page_start}-{pc.page_end}"
                writer.writerow([
                    pc.number, pc.name, pc.category, pc.subcategory or '',
                    pages_str, len(pc.content)
                ])
        print(f"  ✅ Saved summary to {csv_path}")
    
    def run(self):
        print("=" * 80)
        print("  FINAL PRODUCT CONTENT EXTRACTOR")
        print("  (Multi-page support, fixed Assur Senior)")
        print("=" * 80)
        
        if not self.extract_pdf():
            return
        
        products = self.parse_sommaire_with_subcategories()
        if not products:
            return
        
        products_with_pages = self.locate_products(products)
        
        product_contents = self.extract_product_content(products_with_pages)
        
        self.export_to_json(product_contents)
        
        print("\n✅ DONE! Each product's full content is saved in 'product_contents.json'")


if __name__ == "__main__":
    PDF_PATH = "product_catalog.pdf"
    if not os.path.exists(PDF_PATH):
        PDF_PATH = "product_catalog.pdf"
    if not os.path.exists(PDF_PATH):
        print(f"❌ File not found: {PDF_PATH}")
    else:
        extractor = FinalProductExtractor(PDF_PATH)
        extractor.run()