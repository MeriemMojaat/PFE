"""
One‑time script: Add structured columns to product_features.csv
by extracting from free‑text 'conditions' and 'target_audience'.
Run only once after initial product_features.csv is created.
"""

import pandas as pd
import re

df = pd.read_csv('data/product_features.csv')
df.columns = df.columns.str.strip().str.lower()

# Helper to detect keywords
def bool_from_conditions(text, keywords):
    if pd.isna(text):
        return False
    return any(k in text.lower() for k in keywords)

df['requires_domiciliation'] = df['conditions'].apply(lambda x: bool_from_conditions(x, ['domiciliation', 'salaire', 'revenus']))
df['requires_autofinancement_percent'] = df['conditions'].apply(lambda x: 20 if 'autofinancement' in str(x).lower() else 0)
# Max age: default 120, special products like Assur Senior >80? We keep 120 if not specified.
df['max_age'] = 120
df['min_income_smig'] = 0  # extract SMIG multipliers if present
df['requires_marital_status'] = df['conditions'].apply(lambda x: 'marié' if 'marié' in str(x).lower() else '')
df['requires_profession'] = df['conditions'].apply(lambda x: 'salarié' if 'salarié' in str(x).lower() else '')

# Save back
df.to_csv('data/product_features.csv', index=False)
print("✅ product_features.csv updated with structured columns.")