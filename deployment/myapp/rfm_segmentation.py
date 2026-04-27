"""
Step 2: RFM Segmentation & Augmented Financial Profile
=======================================================
Inputs (from Step 1):
- data/clients_clean.csv
- data/operations_filtered.xlsx

Output:
- data/client_rfm_profiles.csv (one row per client with RFM scores, segment, augmented profile, demographics)

Steps:
1. Load cleaned clients and operations.
2. Compute RFM per client (aggregate over all accounts):
   - Recency: days since last transaction (score 1-3)
   - Frequency: total number of transactions (score 1-3)
   - Monetary: total authorized amount (score 1-3)
3. Assign RFM segment (rule-based)
4. Augmented financial profile:
   - Spending capacity = average monthly amount
   - Activity level = average transactions per month
   - Spending regularity = std dev of transaction amounts
   - Engagement score = Recency score + Frequency score (2-6)
5. Merge demographics from clients_clean
6. Save to CSV
"""

import pandas as pd
import numpy as np
from datetime import datetime

# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------
def compute_rfm_scores(recency_days: int, frequency_count: int, monetary_sum: float):
    """Return (recency_score, frequency_score, monetary_score) based on thresholds."""
    # Recency: ≤30 days → 3, ≤90 → 2, >90 → 1
    if recency_days <= 30:
        r_score = 3
    elif recency_days <= 90:
        r_score = 2
    else:
        r_score = 1
    
    # Frequency: ≥80 → 3, ≥50 → 2, <50 → 1
    if frequency_count >= 80:
        f_score = 3
    elif frequency_count >= 50:
        f_score = 2
    else:
        f_score = 1
    
    # Monetary: ≥15000 → 3, ≥8000 → 2, <8000 → 1
    if monetary_sum >= 15000:
        m_score = 3
    elif monetary_sum >= 8000:
        m_score = 2
    else:
        m_score = 1
    
    return r_score, f_score, m_score

def assign_segment(f_score: int, m_score: int) -> str:
    """Assign RFM segment based on frequency and monetary scores."""
    if f_score == 3 and m_score == 3:
        return "Champion"
    elif f_score >= 2 and m_score == 3:
        return "High Value"
    elif f_score >= 2 and m_score == 2:
        return "Medium Value"
    elif f_score >= 2 and m_score == 1:
        return "At Risk"
    else:
        return "Low Value"

# ------------------------------------------------------------------
# Main processing
# ------------------------------------------------------------------
def main():
    print("="*60)
    print("STEP 2: RFM SEGMENTATION & AUGMENTED FINANCIAL PROFILE")
    print("="*60)
    
    # 1. Load cleaned data
    print("\nLoading cleaned data...")
    clients = pd.read_csv('data/clients_clean.csv')
    operations = pd.read_excel('data/operations_filtered.xlsx')
    
    print(f"Clients: {clients.shape[0]} rows")
    print(f"Operations: {operations.shape[0]} rows")
    
    # Ensure transaction_date is datetime
    operations['transaction_date'] = pd.to_datetime(operations['transaction_date'])
    
    # Reference date for recency: max transaction date + 1 day (or just max date)
    ref_date = operations['transaction_date'].max()
    print(f"Reference date for recency: {ref_date.date()}")
    
    # 2. Compute RFM per client (aggregate over all accounts)
    # Group by account_number? But client may have multiple accounts. Merge with clients to get client_id.
    # We need to link operations to client_id via account_number.
    # Already in operations_filtered we have account_number, but not client_id. Merge with clients.
    ops_with_client = operations.merge(clients[['account_number', 'client_id']], on='account_number', how='left')
    print(f"Operations matched to clients: {ops_with_client.shape[0]} rows")
    
    # 3. Aggregate per client
    # Recency: max transaction date per client, then days since ref_date
    # Frequency: count of transactions
    # Monetary: sum of authorized_amount
    rfm_agg = ops_with_client.groupby('client_id').agg(
        last_transaction_date=('transaction_date', 'max'),
        frequency=('transaction_date', 'count'),
        monetary=('authorized_amount', 'sum')
    ).reset_index()
    
    # Compute recency in days
    rfm_agg['recency_days'] = (ref_date - rfm_agg['last_transaction_date']).dt.days
    
    # Compute scores
    scores = rfm_agg.apply(
        lambda row: compute_rfm_scores(row['recency_days'], row['frequency'], row['monetary']),
        axis=1, result_type='expand'
    )
    scores.columns = ['recency_score', 'frequency_score', 'monetary_score']
    rfm_agg = pd.concat([rfm_agg, scores], axis=1)
    
    # Assign segment
    rfm_agg['rfm_segment'] = rfm_agg.apply(
        lambda row: assign_segment(row['frequency_score'], row['monetary_score']),
        axis=1
    )
    
    # 4. Augmented financial profile
    # Spending capacity = average monthly amount
    # First, get monthly spending per client
    ops_with_client['year_month'] = ops_with_client['transaction_date'].dt.to_period('M')
    monthly_spending = ops_with_client.groupby(['client_id', 'year_month'])['authorized_amount'].sum().reset_index()
    monthly_agg = monthly_spending.groupby('client_id').agg(
        spending_capacity=('authorized_amount', 'mean'),  # average monthly amount
        activity_level=('authorized_amount', 'count')     # number of months with transactions
    ).reset_index()
    
    # Activity level: average transactions per month (total transactions / number of active months)
    # We already have frequency (total transactions) and number of months with transactions (activity_level)
    # Compute average transactions per month = frequency / number_of_months
    # But careful: number_of_months = distinct months the client had at least one transaction.
    # We already have that as 'activity_level' from count of months.
    # However, 'activity_level' as defined in original spec is "average number of transactions per month".
    # Let's rename:
    monthly_agg['avg_transactions_per_month'] = monthly_agg['spending_capacity'] / monthly_agg['activity_level']  # Wait, no. spending_capacity is average amount, not count.
    # Actually: activity_level = number of months active.
    # avg_transactions_per_month = total frequency / number_of_months
    # Merge frequency from rfm_agg
    monthly_agg = monthly_agg.merge(rfm_agg[['client_id', 'frequency']], on='client_id', how='left')
    monthly_agg['avg_transactions_per_month'] = monthly_agg['frequency'] / monthly_agg['activity_level']
    monthly_agg = monthly_agg.rename(columns={'activity_level': 'active_months'})
    
    # Spending regularity = std dev of transaction amounts (higher = less regular)
    # Compute per client the std dev of authorized_amount
    spending_std = ops_with_client.groupby('client_id')['authorized_amount'].std().reset_index()
    spending_std.columns = ['client_id', 'spending_regularity']
    # Replace NaN (only one transaction) with 0 (perfect regularity)
    spending_std['spending_regularity'] = spending_std['spending_regularity'].fillna(0)
    
    # Engagement score = recency_score + frequency_score (range 2-6)
    rfm_agg['engagement_score'] = rfm_agg['recency_score'] + rfm_agg['frequency_score']
    
    # Merge augmented features
    rfm_final = rfm_agg.merge(monthly_agg[['client_id', 'active_months', 'avg_transactions_per_month', 'spending_capacity']], on='client_id', how='left')
    rfm_final = rfm_final.merge(spending_std, on='client_id', how='left')
    
    # 5. Merge demographics from clients_clean
    # Select relevant demographic columns
    demo_cols = ['client_id', 'account_number', 'full_name', 'age', 'marital_status', 'gender', 'job_position', 'residence_location']
    demographics = clients[demo_cols].copy()
    rfm_final = rfm_final.merge(demographics, on='client_id', how='inner')
    
    # 6. Final column selection and ordering
    final_columns = [
        'client_id', 'account_number', 'full_name', 'age', 'marital_status', 'gender', 
        'job_position', 'residence_location',
        'recency_days', 'recency_score', 'frequency', 'frequency_score', 'monetary', 'monetary_score',
        'rfm_segment', 'engagement_score',
        'spending_capacity', 'active_months', 'avg_transactions_per_month', 'spending_regularity'
    ]
    rfm_final = rfm_final[final_columns]
    
    # Round numerical values
    rfm_final['spending_capacity'] = rfm_final['spending_capacity'].round(2)
    rfm_final['avg_transactions_per_month'] = rfm_final['avg_transactions_per_month'].round(2)
    rfm_final['spending_regularity'] = rfm_final['spending_regularity'].round(2)
    rfm_final['monetary'] = rfm_final['monetary'].round(2)
    
    # 7. Save to CSV
    output_path = 'data/client_rfm_profiles.csv'
    rfm_final.to_csv(output_path, index=False)
    
    # 8. Summary statistics
    print("\n" + "="*60)
    print("RFM SEGMENTATION SUMMARY")
    print("="*60)
    print(f"Total clients with transactions: {rfm_final.shape[0]}")
    print("\nSegment distribution:")
    segment_counts = rfm_final['rfm_segment'].value_counts()
    for seg, cnt in segment_counts.items():
        print(f"  {seg}: {cnt} ({cnt/len(rfm_final)*100:.1f}%)")
    
    print("\nRFM score distribution:")
    print(f"  Recency score 3: {(rfm_final['recency_score']==3).sum()} ({ (rfm_final['recency_score']==3).mean()*100:.1f}%)")
    print(f"  Frequency score 3: {(rfm_final['frequency_score']==3).sum()} ({ (rfm_final['frequency_score']==3).mean()*100:.1f}%)")
    print(f"  Monetary score 3: {(rfm_final['monetary_score']==3).sum()} ({ (rfm_final['monetary_score']==3).mean()*100:.1f}%)")
    
    print(f"\n✅ Saved RFM profiles to {output_path}")

if __name__ == "__main__":
    main()