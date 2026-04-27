import pandas as pd
import numpy as np
import hashlib
import os
import sys
from datetime import datetime

# ====================
# CONFIGURATION
# ====================
CONFIG = {
    'operations_file': 'operations.txt',
    'clients_file': 'clients.txt',
    'account_column': 'cpte',
    'delimiter': ';',
    'encoding': 'utf-8',
    'prefix_length': 4,
    'hash_seed': 'tunisia_banking_2024',
    'output_suffix': '_masked',
    'save_mapping': True
}

# ====================
# SECURE ACCOUNT MASKER
# ====================
class SecureAccountMasker:
    """Mask account numbers while preserving relationships"""
    
    def __init__(self, prefix_length=4, seed=None):
        self.prefix_length = prefix_length
        self.seed = seed.encode('utf-8') if seed else b'default_secret'
        self.mapping_cache = {}
        self.stats = {
            'total_accounts_masked': 0,
            'unique_accounts': 0,
            'collisions': 0
        }
    
    def _generate_deterministic_digits(self, account_str, length):
        """Generate deterministic replacement digits"""
        digits = []
        for i in range(length):
            hash_input = self.seed + account_str.encode('utf-8') + str(i).encode('utf-8')
            hash_value = hashlib.sha256(hash_input).hexdigest()
            digit = str(int(hash_value, 16) % 10)
            digits.append(digit)
        return ''.join(digits)
    
    def mask_account(self, account):
        """Mask a single account number"""
        if pd.isna(account):
            return account
        
        account_str = str(account).strip()
        
        if account_str in self.mapping_cache:
            return self.mapping_cache[account_str]
        
        if len(account_str) <= self.prefix_length:
            masked = account_str
        else:
            prefix = account_str[:self.prefix_length]
            suffix = account_str[self.prefix_length:]
            
            digit_count = sum(1 for c in suffix if c.isdigit())
            
            if digit_count > 0:
                deterministic_digits = self._generate_deterministic_digits(account_str, digit_count)
                
                masked_suffix = ''
                digit_idx = 0
                for char in suffix:
                    if char.isdigit():
                        masked_suffix += deterministic_digits[digit_idx]
                        digit_idx += 1
                    else:
                        masked_suffix += char
                
                masked = prefix + masked_suffix
            else:
                masked = account_str
        
        self.mapping_cache[account_str] = masked
        self.stats['total_accounts_masked'] += 1
        
        return masked
    
    def mask_series(self, series):
        """Mask a pandas Series of account numbers"""
        return series.apply(self.mask_account)
    
    def mask_dataframe(self, df, account_column):
        """Mask account numbers in a DataFrame"""
        if account_column in df.columns:
            df = df.copy()
            df[account_column] = self.mask_series(df[account_column])
        return df
    
    def get_mapping_df(self):
        """Get mapping of original to masked accounts"""
        data = []
        for original, masked in self.mapping_cache.items():
            data.append({
                'original_account': original,
                'masked_account': masked,
                'masked_prefix': masked[:self.prefix_length]
            })
        
        df = pd.DataFrame(data)
        self.stats['unique_accounts'] = len(df)
        
        unique_masked = df['masked_account'].nunique()
        if len(df) > unique_masked:
            self.stats['collisions'] = len(df) - unique_masked
        
        return df

# ====================
# DATA LOADING
# ====================
def load_data(file_path, delimiter, encoding):
    """Load data from file with error handling"""
    print(f"Loading {file_path}...")
    
    try:
        df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding)
        print(f"  ✅ Loaded {len(df):,} rows, {len(df.columns)} columns")
        return df
    
    except FileNotFoundError:
        print(f"  ❌ File not found: {file_path}")
        return None
    except Exception as e:
        print(f"  ❌ Error loading {file_path}: {e}")
        return None

# ====================
# MASKING PROCESS
# ====================
def mask_banking_data():
    """Main function to mask banking data"""
    
    print("\n" + "="*70)
    print("🏦 BANKING DATA MASKING PROCESS")
    print("="*70)
    
    # Load operations data
    operations_df = load_data(
        CONFIG['operations_file'], 
        CONFIG['delimiter'], 
        CONFIG['encoding']
    )
    
    if operations_df is None:
        print("❌ Cannot proceed without operations data.")
        return None
    
    if CONFIG['account_column'] not in operations_df.columns:
        print(f"❌ Account column '{CONFIG['account_column']}' not found in operations data.")
        print(f"   Available columns: {list(operations_df.columns)}")
        return None
    
    # Load clients data
    clients_df = None
    if os.path.exists(CONFIG['clients_file']):
        clients_df = load_data(
            CONFIG['clients_file'], 
            CONFIG['delimiter'], 
            CONFIG['encoding']
        )
        if clients_df is not None and CONFIG['account_column'] not in clients_df.columns:
            print(f"⚠️  Account column '{CONFIG['account_column']}' not found in clients data.")
            clients_df = None
    else:
        print(f"ℹ️  Clients file not found: {CONFIG['clients_file']}")
    
    # Initialize masker
    print(f"\n🔐 Initializing masker (keeping first {CONFIG['prefix_length']} digits)...")
    masker = SecureAccountMasker(
        prefix_length=CONFIG['prefix_length'],
        seed=CONFIG['hash_seed']
    )
    
    # Show sample of original data
    print("\n📊 ORIGINAL DATA SAMPLE:")
    print("-" * 80)
    
    # Show operations sample
    ops_sample = operations_df.head(5).copy()
    print("OPERATIONS (first 5 rows):")
    
    # Get operations display columns
    ops_display_cols = [CONFIG['account_column']]
    for col in ['mnt_autorise', 'dat_trans', 'ref_aut_bh', 'nom_term']:
        if col in ops_sample.columns:
            ops_display_cols.append(col)
    
    print(ops_sample[ops_display_cols].to_string(index=False))
    
    if clients_df is not None:
        clients_sample = clients_df.head(5).copy()
        print("\nCLIENTS (first 5 rows):")
        
        # Get clients display columns
        clients_display_cols = [CONFIG['account_column']]
        for col in ['client_id', 'full_name', 'gender', 'residence_location']:
            if col in clients_sample.columns:
                clients_display_cols.append(col)
        
        print(clients_sample[clients_display_cols].to_string(index=False))
    
    # Mask the data
    print(f"\n🔄 Masking account numbers...")
    
    # Mask operations
    masked_operations = masker.mask_dataframe(operations_df, CONFIG['account_column'])
    print(f"  ✅ Operations masked: {len(operations_df):,} records")
    
    # Mask clients if available
    masked_clients = None
    if clients_df is not None:
        masked_clients = masker.mask_dataframe(clients_df, CONFIG['account_column'])
        print(f"  ✅ Clients masked: {len(clients_df):,} records")
    
    # Get mapping
    mapping_df = masker.get_mapping_df()
    print(f"  📈 Unique accounts processed: {masker.stats['unique_accounts']:,}")
    
    if masker.stats['collisions'] > 0:
        print(f"  ⚠️  Collisions detected: {masker.stats['collisions']:,}")
        print(f"     (This is acceptable - {masker.stats['collisions']/masker.stats['unique_accounts']*100:.2f}% collision rate)")
    else:
        print(f"  ✅ No collisions (perfect mapping)")
    
    # Show sample of masked data
    print("\n🔒 MASKED DATA SAMPLE:")
    print("-" * 80)
    
    # Show masked operations sample
    masked_ops_sample = masked_operations.head(5).copy()
    print("MASKED OPERATIONS (first 5 rows):")
    print(masked_ops_sample[ops_display_cols].to_string(index=False))
    
    if masked_clients is not None:
        masked_clients_sample = masked_clients.head(5).copy()
        print("\nMASKED CLIENTS (first 5 rows):")
        print(masked_clients_sample[clients_display_cols].to_string(index=False))
    
    # Show examples of masking
    print("\n🔍 EXAMPLES OF MASKING:")
    print("-" * 40)
    
    # Show a few examples
    sample_accounts = operations_df[CONFIG['account_column']].dropna().unique()[:3]
    for i, account in enumerate(sample_accounts, 1):
        original = str(account)
        masked = masker.mask_account(account)
        print(f"  Example {i}: {original} → {masked}")
        print(f"           First {CONFIG['prefix_length']} digits preserved: '{original[:CONFIG['prefix_length']]}' → '{masked[:CONFIG['prefix_length']]}'")
    
    # Show relationship preservation
    if clients_df is not None:
        print(f"\n🔗 RELATIONSHIP PRESERVATION:")
        print("-" * 40)
        
        # Find a client with multiple accounts
        client_counts = clients_df['client_id'].value_counts()
        multi_account_clients = client_counts[client_counts > 1]
        
        if len(multi_account_clients) > 0:
            sample_client = multi_account_clients.index[0]
            print(f"  Client '{sample_client}' has {client_counts[sample_client]} accounts")
            
            # Show original and masked accounts for this client
            client_original_accounts = clients_df[clients_df['client_id'] == sample_client][CONFIG['account_column']].tolist()
            client_masked_accounts = masked_clients[masked_clients['client_id'] == sample_client][CONFIG['account_column']].tolist()
            
            print(f"  Original accounts: {client_original_accounts[:3]}")
            print(f"  Masked accounts:   {client_masked_accounts[:3]}")
            print(f"  ✅ Same client still links to same masked accounts")
    
    return masked_operations, masked_clients, masker, mapping_df

# ====================
# SAVE RESULTS
# ====================
def save_results(masked_operations, masked_clients, masker, mapping_df):
    """Save masked data and mapping to files"""
    
    print("\n" + "="*70)
    print("💾 SAVING RESULTS")
    print("="*70)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create output directory
    output_dir = f"masked_data_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}/")
    
    # Save masked operations
    ops_output = os.path.join(output_dir, f"operations{CONFIG['output_suffix']}.txt")
    masked_operations.to_csv(ops_output, sep=CONFIG['delimiter'], index=False, encoding=CONFIG['encoding'])
    print(f"✅ Masked operations saved to: {ops_output}")
    print(f"   Records: {len(masked_operations):,}")
    
    # Save masked clients if exists
    if masked_clients is not None:
        clients_output = os.path.join(output_dir, f"clients{CONFIG['output_suffix']}.txt")
        masked_clients.to_csv(clients_output, sep=CONFIG['delimiter'], index=False, encoding=CONFIG['encoding'])
        print(f"✅ Masked clients saved to: {clients_output}")
        print(f"   Records: {len(masked_clients):,}")
    
    # Save mapping if requested
    if CONFIG['save_mapping'] and mapping_df is not None:
        mapping_output = os.path.join(output_dir, "account_mapping.csv")
        mapping_df.to_csv(mapping_output, index=False, encoding='utf-8-sig')
        print(f"✅ Account mapping saved to: {mapping_output}")
        print(f"   Mappings: {len(mapping_df):,}")
    
    # Save summary report
    report_output = os.path.join(output_dir, "masking_report.txt")
    with open(report_output, 'w', encoding='utf-8') as f:
        f.write("BANKING DATA MASKING REPORT\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Operations records: {len(masked_operations):,}\n")
        f.write(f"Clients records: {len(masked_clients) if masked_clients is not None else 0:,}\n")
        f.write(f"Unique accounts masked: {masker.stats['unique_accounts']:,}\n")
        f.write(f"Collisions: {masker.stats['collisions']:,}\n")
        f.write(f"Collision rate: {masker.stats['collisions']/masker.stats['unique_accounts']*100:.4f}%\n")
        f.write(f"Output directory: {output_dir}\n")
    
    print(f"✅ Summary report saved to: {report_output}")
    
    return output_dir

# ====================
# MAIN EXECUTION
# ====================
def main():
    """Main execution function"""
    
    print("\n" + "="*70)
    print("🏦 TUNISIAN BANKING DATA MASKING")
    print("="*70)
    
    # Step 1: Mask the data
    result = mask_banking_data()
    
    if result is None:
        print("\n❌ Masking process failed.")
        return
    
    masked_operations, masked_clients, masker, mapping_df = result
    
    # Step 2: Save results
    output_dir = save_results(masked_operations, masked_clients, masker, mapping_df)
    
    # Final summary
    print("\n" + "="*70)
    print("✅ MASKING COMPLETE!")
    print("="*70)
    
    print(f"""
📊 SUMMARY:
• Operations masked: {len(masked_operations):,} records
• Clients masked: {len(masked_clients) if masked_clients is not None else 0:,} records
• Unique accounts: {masker.stats['unique_accounts']:,}
• Collisions: {masker.stats['collisions']:,} ({masker.stats['collisions']/masker.stats['unique_accounts']*100:.4f}%)

📁 OUTPUT FILES:
• {output_dir}/operations_masked.txt
• {output_dir}/clients_masked.txt
• {output_dir}/account_mapping.csv
• {output_dir}/masking_report.txt

🔒 SECURITY:
• First {CONFIG['prefix_length']} digits preserved for format recognition
• Remaining digits replaced with deterministic fake data
• Same original account → Same masked account (always)
• Relationships between tables preserved

🚀 NEXT STEPS:
1. Use the masked files for development/testing
2. All joins on 'cpte' column will still work
3. Real account numbers are protected
4. Analyze data safely!
    """)

# ====================
# RUN THE SCRIPT
# ====================
if __name__ == "__main__":
    print("Starting Tunisian Banking Data Masking...")
    
    # Check if files exist
    if not os.path.exists(CONFIG['operations_file']):
        print(f"❌ Operations file not found: {CONFIG['operations_file']}")
        print(f"\nCurrent directory: {os.getcwd()}")
        print("\nFiles in directory:")
        for file in os.listdir('.'):
            if file.endswith('.txt'):
                print(f"  • {file}")
    else:
        main()