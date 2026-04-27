import pandas as pd

# Read with semicolon delimiter
df = pd.read_csv('data/merchant.csv', sep=';')

# Drop any columns that are completely unnamed or empty (like the trailing ones)
df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
df = df.dropna(axis=1, how='all')  # drop columns that are all NaN

# Show cleaned columns
print("Columns after cleaning:", df.columns.tolist())

# Now find the column that contains the MCC-like code
# Likely 'merchant_code'
if 'merchant_code' in df.columns:
    df = df.dropna(subset=['merchant_code'])
elif 'mcc' in df.columns:
    df = df.dropna(subset=['mcc'])
else:
    print("No MCC-like column found. Available columns:", df.columns.tolist())
    exit()

# Deduplicate by merchant_key if present
if 'merchant_key' in df.columns:
    df = df.drop_duplicates(subset=['merchant_key'], keep='first')
else:
    # fallback: deduplicate by merchant_name + merchant_code
    df = df.drop_duplicates(subset=['merchant_name', 'merchant_code'], keep='first')

df.to_csv('merchants_clean.csv', index=False, sep=';')
print(f"Cleaned merchants: {len(df)} records saved to merchants_clean.csv")