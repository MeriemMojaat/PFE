"""
Step 1: Complete Data Cleaning & Preparation (with Recommended Outlier Handling)
================================================================================
- Load raw data (Clients.csv, Merchants.csv, Operations.xlsx)
- Remove duplicates
- Identify data types and unique values in categorical columns
- Calculate missing values as percentage
- Detect outliers (IQR) – for reporting only
- Treat outliers:
    * Age: cap between 18 and 100, remove >120 (data errors)
    * Transaction amount: cap at 99.9th percentile (winsorize), keep original for audit
    * Negative amounts: remove rows
- Impute remaining missing values (if any)
- Data validation (date ranges, future dates)
- Data formatting (standardise strings, dates, numbers)
- Save cleaned files and outlier report

Outputs:
- data/clients_clean.csv
- data/merchants_clean.csv
- data/operations_filtered.xlsx
- data/outlier_report.txt
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------
def print_missing_summary(df, name):
    """Print missing value count and percentage for each column."""
    missing = df.isnull().sum()
    missing_pct = (missing / len(df)) * 100
    missing_df = pd.DataFrame({'Missing Count': missing, 'Missing %': missing_pct})
    print(f"\nMissing values in {name}:")
    non_zero = missing_df[missing_df['Missing Count'] > 0]
    if not non_zero.empty:
        print(non_zero.to_string())
    else:
        print("  No missing values found.")

def detect_outliers_iqr(df, column):
    """Calculate IQR bounds and return lower, upper, and outlier count."""
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    outliers = df[(df[column] < lower_bound) | (df[column] > upper_bound)]
    return lower_bound, upper_bound, len(outliers)

def validate_date(df, column):
    """Count rows with date outside 1900-2100 range."""
    invalid = df[(df[column] < '1900-01-01') | (df[column] > '2100-01-01')]
    return len(invalid)

# ------------------------------------------------------------------
# 1. Load raw data
# ------------------------------------------------------------------
def load_raw_data(data_dir='data'):
    """Load Clients, Merchants, and Operations from the data directory."""
    print("Loading raw data...")
    clients = pd.read_csv(os.path.join(data_dir, 'clients.csv'))
    merchants = pd.read_csv(os.path.join(data_dir, 'merchant.csv'), delimiter=';')
    operations = pd.read_excel(os.path.join(data_dir, 'operations.xlsx'))
    print(f"Clients: {clients.shape[0]} rows, {clients.shape[1]} cols")
    print(f"Merchants: {merchants.shape[0]} rows, {merchants.shape[1]} cols")
    print(f"Operations: {operations.shape[0]} rows, {operations.shape[1]} cols")
    return clients, merchants, operations

# ------------------------------------------------------------------
# 2. Process Clients (with age outlier handling)
# ------------------------------------------------------------------
def process_clients(clients):
    """
    Clean clients:
    - Remove duplicates by client_id
    - Remove placeholder names and generic job positions
    - Convert date_of_birth, remove placeholder dates and missing
    - Validate date range
    - Format string columns
    (Age will be computed later, then capped)
    """
    print("\n" + "="*60)
    print("PROCESSING CLIENTS")
    print("="*60)
    
    # 2.1 Remove duplicates
    print(f"\nOriginal clients: {len(clients)}")
    clients = clients.drop_duplicates(subset=['client_id'], keep='first')
    print(f"After removing duplicates: {len(clients)}")
    
    # 2.2 Identify data types
    print("\nData types in clients:")
    print(clients.dtypes)
    
    # 2.3 Count unique values in categorical columns (using object columns)
    categorical_cols = clients.select_dtypes(include=['object', 'string']).columns
    print("\nUnique value counts in categorical columns:")
    for col in categorical_cols:
        print(f"  {col}: {clients[col].nunique()} unique values")
    
    # 2.4 Missing values summary
    print_missing_summary(clients, "Clients")
    
    # 2.5 Remove placeholder rows
    if 'full_name' in clients.columns:
        clients = clients[~clients['full_name'].str.contains(r'Client C\d+', na=False, regex=True)]
    if 'job_position' in clients.columns:
        clients = clients[clients['job_position'] != 'Professionnel']
    
    # 2.6 Clean date_of_birth
    clients['date_of_birth'] = pd.to_datetime(clients['date_of_birth'], errors='coerce')
    # Remove rows where month=1 and day=1 (placeholder)
    clients = clients[~((clients['date_of_birth'].dt.month == 1) & (clients['date_of_birth'].dt.day == 1))]
    clients = clients.dropna(subset=['date_of_birth'])
    
    # 2.7 Validate date range (1900-2100)
    invalid_dob = validate_date(clients, 'date_of_birth')
    if invalid_dob > 0:
        print(f"Removing {invalid_dob} rows with date_of_birth outside 1900-2100.")
        clients = clients[(clients['date_of_birth'] >= '1900-01-01') & (clients['date_of_birth'] <= '2100-01-01')]
    
    # 2.8 Data formatting (standardise strings)
    if 'full_name' in clients.columns:
        clients['full_name'] = clients['full_name'].str.title().str.strip()
    if 'job_position' in clients.columns:
        clients['job_position'] = clients['job_position'].str.strip().str.upper()
    if 'marital_status' in clients.columns:
        clients['marital_status'] = clients['marital_status'].str.strip().str.capitalize()
    if 'gender' in clients.columns:
        clients['gender'] = clients['gender'].str.strip().str.upper()
    if 'residence_location' in clients.columns:
        clients['residence_location'] = clients['residence_location'].str.strip().str.title()
    
    return clients

# ------------------------------------------------------------------
# 3. Process Merchants (robust column handling)
# ------------------------------------------------------------------
def process_merchants(merchants):
    """
    Clean merchants:
    - Drop completely empty columns (all NaN or all empty strings)
    - Rename 'Category' to 'category'
    - Remove duplicates
    - Impute missing merchant_name and category
    - Format strings
    """
    print("\n" + "="*60)
    print("PROCESSING MERCHANTS")
    print("="*60)
    
    # 3.1 Drop columns that are entirely NaN
    merchants = merchants.dropna(axis=1, how='all')
    
    # 3.2 Drop columns where all non‑null values are empty strings (after stripping)
    for col in merchants.columns:
        # Convert to string, strip, then check if all values are either NaN or empty string
        series_str = merchants[col].astype(str).str.strip()
        if series_str.isin(['', 'nan', 'None']).all():
            merchants = merchants.drop(columns=[col])
            print(f"Dropped column with only empty/NA strings: {col}")
    
    # 3.3 Also drop any column whose name contains 'unnamed' (case-insensitive)
    unnamed_cols = [col for col in merchants.columns if 'unnamed' in col.lower()]
    if unnamed_cols:
        merchants = merchants.drop(columns=unnamed_cols)
        print(f"Dropped unnamed columns: {unnamed_cols}")
    
    # 3.4 Standardise column names to lowercase
    merchants.columns = merchants.columns.str.lower()
    
    # 3.5 Remove duplicates
    print(f"\nOriginal merchants: {len(merchants)}")
    if 'merchant_key' in merchants.columns:
        merchants = merchants.drop_duplicates(subset=['merchant_key'], keep='first')
    else:
        merchants = merchants.drop_duplicates(subset=['merchant_name', 'merchant_code'], keep='first')
    print(f"After removing duplicates: {len(merchants)}")
    
    # 3.6 Convert merchant_code to integer (if possible)
    if 'merchant_code' in merchants.columns:
        merchants['merchant_code'] = merchants['merchant_code'].fillna(0).astype(int)
    
    # 3.7 Impute missing values
    if 'merchant_name' in merchants.columns:
        merchants['merchant_name'] = merchants['merchant_name'].fillna('Unknown')
    if 'category' in merchants.columns:
        merchants['category'] = merchants['category'].fillna('Other')
    
    # 3.8 Remove rows with missing merchant_code (already handled)
    merchants = merchants.dropna(subset=['merchant_code'])
    
    # 3.9 Data formatting
    if 'merchant_name' in merchants.columns:
        merchants['merchant_name'] = merchants['merchant_name'].str.strip().str.title()
    if 'category' in merchants.columns:
        merchants['category'] = merchants['category'].str.strip().str.upper()
    if 'merchant_key' in merchants.columns:
        merchants['merchant_key'] = merchants['merchant_key'].astype(str).str.strip()
    
    # 3.10 Final check for any remaining missing values
    print("\nRemaining missing values after imputation:")
    missing = merchants.isnull().sum()
    print(missing[missing > 0] if (missing > 0).any() else "  None")
    
    return merchants
# ------------------------------------------------------------------
# 4. Process Operations (with transaction amount outlier handling)
# ------------------------------------------------------------------
def process_operations(operations, clients_clean, merchants_clean):
    """
    Clean operations:
    - Remove duplicates
    - Convert date, remove future dates
    - Remove negative amounts
    - Impute missing amounts with median (correctly, no inplace)
    - Keep only transactions from cleaned clients
    - Add merchant category
    """
    print("\n" + "="*60)
    print("PROCESSING OPERATIONS")
    print("="*60)
    
    # 4.1 Remove duplicates
    print(f"\nOriginal operations: {len(operations)}")
    operations = operations.drop_duplicates()
    print(f"After removing duplicates: {len(operations)}")
    
    # 4.2 Data types
    print("\nData types in operations:")
    print(operations.dtypes)
    
    # 4.3 Convert transaction_date to datetime
    operations['transaction_date'] = pd.to_datetime(operations['transaction_date'], errors='coerce')
    operations = operations.dropna(subset=['transaction_date'])
    
    # 4.4 Missing values summary
    print_missing_summary(operations, "Operations")
    
    # 4.5 Outlier detection for authorized_amount (IQR) – report only
    if 'authorized_amount' in operations.columns:
        lower, upper, outlier_count = detect_outliers_iqr(operations, 'authorized_amount')
        print(f"\nOutlier detection for authorized_amount (IQR method):")
        print(f"  Lower bound: {lower:.2f}, Upper bound: {upper:.2f}")
        print(f"  Number of outliers: {outlier_count} ({outlier_count/len(operations)*100:.2f}%)")
    
    # 4.6 Remove negative amounts (data errors)
    if 'authorized_amount' in operations.columns:
        neg_count = (operations['authorized_amount'] < 0).sum()
        if neg_count > 0:
            print(f"Removing {neg_count} transactions with negative amount.")
            operations = operations[operations['authorized_amount'] >= 0]
    
    # 4.7 Impute missing authorized_amount with median (avoid chained assignment)
    if 'authorized_amount' in operations.columns and operations['authorized_amount'].isnull().any():
        median_amt = operations['authorized_amount'].median()
        operations['authorized_amount'] = operations['authorized_amount'].fillna(median_amt)
        print(f"Imputed missing authorized_amount with median: {median_amt}")
    
    # 4.8 Remove future dates
    future_dates = operations[operations['transaction_date'] > datetime.now()]
    if len(future_dates) > 0:
        print(f"Removing {len(future_dates)} transactions with future dates.")
        operations = operations[operations['transaction_date'] <= datetime.now()]
    
    # 4.9 Keep only transactions from cleaned clients
    operations['account_number'] = operations['account_number'].astype(str)
    clients_clean['account_number'] = clients_clean['account_number'].astype(str)
    operations = operations.merge(clients_clean[['account_number']], on='account_number', how='inner')
    
    # 4.10 Add merchant category (if merchant_key exists in both)
    if 'merchant_key' in operations.columns and 'merchant_key' in merchants_clean.columns:
        merchants_clean['merchant_key'] = merchants_clean['merchant_key'].astype(str)
        operations['merchant_key'] = operations['merchant_key'].astype(str)
        operations = operations.merge(merchants_clean[['merchant_key', 'category']], on='merchant_key', how='left')
    
    # 4.11 Data formatting
    if 'authorized_amount' in operations.columns:
        operations['authorized_amount'] = operations['authorized_amount'].round(3)
    
    return operations

# ------------------------------------------------------------------
# 5. Main execution (with outlier capping for age and amount)
# ------------------------------------------------------------------
def main():
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Load raw data
    clients_raw, merchants_raw, operations_raw = load_raw_data('data')
    
    # Process clients (without age yet)
    clients = process_clients(clients_raw)
    
    # Process merchants
    merchants = process_merchants(merchants_raw)
    
    # Process operations (will also filter to cleaned clients)
    operations = process_operations(operations_raw, clients, merchants)
    
    # Compute reference date (max transaction date) for age calculation
    ref_date = operations['transaction_date'].max()
    print(f"\nReference date for age calculation: {ref_date.date()}")
    
    # Compute age for clients
    clients['age'] = (ref_date - clients['date_of_birth']).dt.days // 365
    
    # --- Outlier treatment for age (domain‑based capping) ---
    print("\nOutlier treatment for age:")
    print(f"  Before capping: min={clients['age'].min()}, max={clients['age'].max()}")
    clients['age'] = clients['age'].clip(lower=18, upper=100)
    clients = clients[clients['age'] <= 120]
    print(f"  After capping: min={clients['age'].min()}, max={clients['age'].max()}")
    
    # --- Outlier treatment for transaction amount (percentile capping) ---
    print("\nOutlier treatment for authorized_amount:")
    # Keep original amount for audit
    operations['authorized_amount_original'] = operations['authorized_amount']
    # Cap at 99.9th percentile (winsorize extreme errors)
    cap_amt = operations['authorized_amount'].quantile(0.999)
    operations['authorized_amount_capped'] = operations['authorized_amount'].clip(upper=cap_amt)
    print(f"  Capped at {cap_amt:.2f} (99.9th percentile)")
    capped_count = (operations['authorized_amount'] > cap_amt).sum()
    print(f"  Number of transactions capped: {capped_count}")
    # Replace original with capped version for downstream analysis
    operations['authorized_amount'] = operations['authorized_amount_capped']
    
    # Impute any remaining missing values in clients (categorical columns)
    categorical_cols = clients.select_dtypes(include=['object', 'string']).columns
    for col in categorical_cols:
        if clients[col].isnull().any():
            mode_val = clients[col].mode()[0] if not clients[col].mode().empty else 'Unknown'
            clients[col] = clients[col].fillna(mode_val)
            print(f"Imputed missing values in {col} with mode: {mode_val}")
    
    # Final validation
    print("\n" + "="*60)
    print("FINAL VALIDATION")
    print("="*60)
    print(f"Clients final shape: {clients.shape}")
    print(f"Merchants final shape: {merchants.shape}")
    print(f"Operations final shape: {operations.shape}")
    
    # Check remaining missing values
    missing_clients = clients.isnull().sum()
    missing_merchants = merchants.isnull().sum()
    missing_ops = operations.isnull().sum()
    
    print("\nRemaining missing values in clients:")
    print(missing_clients[missing_clients > 0] if (missing_clients > 0).any() else "  None")
    print("\nRemaining missing values in merchants:")
    print(missing_merchants[missing_merchants > 0] if (missing_merchants > 0).any() else "  None")
    print("\nRemaining missing values in operations:")
    print(missing_ops[missing_ops > 0] if (missing_ops > 0).any() else "  None")
    
    # Save cleaned files
    clients.to_csv('data/clients_clean.csv', index=False)
    merchants.to_csv('data/merchants_clean.csv', index=False)
    operations.to_excel('data/operations_filtered.xlsx', index=False)
    
    # Save outlier report
    with open('data/outlier_report.txt', 'w') as f:
        f.write("OUTLIER TREATMENT REPORT\n")
        f.write("========================\n\n")
        f.write("Age: capped between 18 and 100. Values >120 removed.\n")
        f.write(f"Final age range: {clients['age'].min()} - {clients['age'].max()}\n\n")
        f.write("Transaction amount: capped at 99.9th percentile (winsorized).\n")
        f.write(f"Capping threshold: {cap_amt:.2f}\n")
        f.write(f"Number of capped transactions: {capped_count}\n")
        f.write(f"Original max amount: {operations['authorized_amount_original'].max():.2f}\n")
        f.write(f"Capped max amount: {operations['authorized_amount'].max():.2f}\n\n")
        f.write("Negative amounts: removed.\n")
        f.write("All other outliers are preserved (no removal).\n")
        f.write("\nRemaining missing values after imputation:\n")
        f.write(f"Clients: {missing_clients.sum()} missing\n")
        f.write(f"Merchants: {missing_merchants.sum()} missing\n")
        f.write(f"Operations: {missing_ops.sum()} missing\n")
    
    print("\n✅ Data preparation complete. Files saved:")
    print("   - data/clients_clean.csv")
    print("   - data/merchants_clean.csv")
    print("   - data/operations_filtered.xlsx")
    print("   - data/outlier_report.txt")

if __name__ == "__main__":
    main()