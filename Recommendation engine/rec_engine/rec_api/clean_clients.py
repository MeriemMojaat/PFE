import pandas as pd
from datetime import datetime

# Load
df = pd.read_csv('data/clients.csv')

# Define reference date (max transaction date from operations, or fixed)
REF_DATE = pd.to_datetime('2025-06-29')

# Remove placeholder names (Client Cxxxxx)
df = df[~df['full_name'].str.contains(r'Client C\d+', na=False)]

# Remove generic job "Professionnel"
df = df[df['job_position'] != 'Professionnel']

# Remove rows with suspicious birthdate (month=1, day=1) or missing
df['date_of_birth'] = pd.to_datetime(df['date_of_birth'], errors='coerce')
df = df[~((df['date_of_birth'].dt.month == 1) & (df['date_of_birth'].dt.day == 1))]
df = df[df['date_of_birth'].notna()]

# Compute age at reference date
df['age'] = (REF_DATE.year - df['date_of_birth'].dt.year).astype('Int64')

# Deduplicate by client_id: keep first occurrence
df = df.drop_duplicates(subset=['client_id'], keep='first')

# Save
df.to_csv('clients_clean.csv', index=False)
print(f"Cleaned clients: {len(df)} unique records saved to clients_clean.csv")