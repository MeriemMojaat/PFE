import json
import pandas as pd

with open('data/product_contents.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

products = []
for prod in data['products']:
    products.append({
        'name': prod['name'],
        'category': prod['category'],
        'subcategory': prod['subcategory'],
        'description': prod['content'][:500],  # first 500 chars as summary
        'page': prod['page_start']
    })

df = pd.DataFrame(products)
df.to_csv('product_features.csv', index=False)
print(f"Extracted {len(df)} products")