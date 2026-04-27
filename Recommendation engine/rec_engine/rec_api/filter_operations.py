import pandas as pd

# Load
ops = pd.read_excel('data/operations.xlsx')
clients = pd.read_csv('data/clients_clean.csv')

# Get list of valid account numbers
valid_accounts = clients['account_number'].unique()

# Filter
ops_filtered = ops[ops['account_number'].isin(valid_accounts)]

# Convert date
ops_filtered['transaction_date'] = pd.to_datetime(ops_filtered['transaction_date'])

# Save
ops_filtered.to_excel('operations_filtered.xlsx', index=False)
print(f"Filtered operations: {len(ops_filtered)} rows (from {len(ops)} original)")