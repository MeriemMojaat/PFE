import pandas as pd
import numpy as np

# Load
ops = pd.read_excel('data/operations_filtered.xlsx')
clients = pd.read_csv('data/clients_clean.csv')

# Reference date (max transaction date in ops)
ref_date = ops['transaction_date'].max()

# Compute RFM per client (by client_id, joining via account_number)
# First, get client_id for each account
account_to_client = clients[['account_number', 'client_id']].drop_duplicates('account_number')
ops_with_client = ops.merge(account_to_client, on='account_number', how='left')

# Group by client_id
rfm = ops_with_client.groupby('client_id').agg(
    recency_days=('transaction_date', lambda x: (ref_date - x.max()).days),
    frequency=('transaction_date', 'count'),
    monetary=('authorized_amount', 'sum')
).reset_index()

# Scoring
def score_recency(d):
    if d <= 30: return 3
    elif d <= 90: return 2
    else: return 1

def score_frequency(f):
    if f >= 80: return 3
    elif f >= 50: return 2
    else: return 1

def score_monetary(m):
    if m >= 15000: return 3
    elif m >= 8000: return 2
    else: return 1

rfm['recency_score'] = rfm['recency_days'].apply(score_recency)
rfm['frequency_score'] = rfm['frequency'].apply(score_frequency)
rfm['monetary_score'] = rfm['monetary'].apply(score_monetary)

# Segment
def get_segment(row):
    f = row['frequency_score']
    m = row['monetary_score']
    if f == 3 and m == 3:
        return 'Champion'
    elif f >= 2 and m == 3:
        return 'High Value'
    elif f >= 2 and m == 2:
        return 'Medium Value'
    elif f >= 2 and m == 1:
        return 'At Risk'
    else:
        return 'Low Value'

rfm['rfm_segment'] = rfm.apply(get_segment, axis=1)

# Augmented features
# Monthly aggregates
ops_with_client['year_month'] = ops_with_client['transaction_date'].dt.to_period('M')
monthly = ops_with_client.groupby(['client_id', 'year_month']).agg(
    monthly_amount=('authorized_amount', 'sum'),
    monthly_transactions=('transaction_date', 'count')
).reset_index()

client_monthly = monthly.groupby('client_id').agg(
    avg_monthly_amount=('monthly_amount', 'mean'),
    avg_monthly_transactions=('monthly_transactions', 'mean')
).reset_index()

# Spending regularity = std dev of transaction amounts per client
transaction_std = ops_with_client.groupby('client_id')['authorized_amount'].std().fillna(0).reset_index()
transaction_std.columns = ['client_id', 'spending_regularity']

# Merge
rfm = rfm.merge(client_monthly, on='client_id', how='left')
rfm = rfm.merge(transaction_std, on='client_id', how='left')
rfm['spending_capacity'] = rfm['avg_monthly_amount'].fillna(0)
rfm['activity_level'] = rfm['avg_monthly_transactions'].fillna(0)
rfm['spending_regularity'] = rfm['spending_regularity'].fillna(0)
rfm['engagement_score'] = rfm['recency_score'] + rfm['frequency_score']

# Merge demographic info from clients_clean (already deduplicated)
demo = clients[['client_id', 'full_name', 'marital_status', 'gender', 'job_position', 'residence_location', 'age']]
rfm = rfm.merge(demo, on='client_id', how='left')

# Save
rfm.to_csv('client_rfm_profiles.csv', index=False)
print(f"RFM profiles saved for {len(rfm)} clients")