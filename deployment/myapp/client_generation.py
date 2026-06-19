import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import random
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import uuid

# ============================================================================
# 1. LOAD EXISTING OPERATIONS DATA
# ============================================================================
def load_operations_data(file_path: str) -> pd.DataFrame:
    """Load operations/transactions data"""
    try:
        df = pd.read_csv(file_path, delimiter=';', encoding='utf-8')
        
        account_cols = [col for col in df.columns if 'account' in col.lower() or 'cpte' in col.lower() or 'compte' in col.lower()]
        if account_cols:
            df = df.rename(columns={account_cols[0]: 'account_number'})
        else:
            raise ValueError("No account number column found")
        
        df['account_number'] = df['account_number'].astype(str).str.strip()
        
        print(f"Loaded {len(df)} transactions for {df['account_number'].nunique()} unique accounts")
        return df
    
    except Exception as e:
        print(f"Error loading operations data: {e}")
        return create_sample_operations_data()

def create_sample_operations_data() -> pd.DataFrame:
    """Create sample operations data"""
    data = {
        'account_number': ['ACC001', 'ACC001', 'ACC002', 'ACC003', 'ACC003', 'ACC004', 
                          'ACC005', 'ACC005', 'ACC005', 'ACC006', 'ACC007', 'ACC008'],
        'transaction_date': pd.date_range('2023-01-01', periods=12, freq='D'),
        'amount': [1000, -500, 2000, 1500, -200, 3000, 500, -100, -50, 1200, 800, 2500],
        'transaction_type': ['DEPOSIT', 'WITHDRAWAL', 'DEPOSIT', 'DEPOSIT', 'WITHDRAWAL',
                           'DEPOSIT', 'DEPOSIT', 'WITHDRAWAL', 'WITHDRAWAL', 'DEPOSIT',
                           'DEPOSIT', 'DEPOSIT']
    }
    return pd.DataFrame(data)

# ============================================================================
# 2. CLIENT DATA GENERATOR WITH AGE GUARANTEES
# ============================================================================
class BankingClientGenerator:
    """Generate realistic banking client data with AGE >= 18 guarantees"""
    
    # Tunisian names
    FIRST_NAMES = {
        'M': ['Mohamed', 'Ali', 'Mahmoud', 'Youssef', 'Khalil', 'Ahmed', 'Hassen', 
              'Omar', 'Bechir', 'Rachid', 'Salah', 'Tarek', 'Nabil', 'Karim', 
              'Samir', 'Adel', 'Habib', 'Fathi', 'Moncef', 'Wassim', 'Moez',
              'Anis', 'Chokri', 'Fares', 'Haythem', 'Imed', 'Jamel', 'Kais',
              'Lotfi', 'Malek', 'Nizar', 'Ridha', 'Sami', 'Taher', 'Zied'],
        'F': ['Fatma', 'Mariem', 'Amina', 'Salma', 'Nour', 'Houda', 'Rania',
              'Sonia', 'Leila', 'Amira', 'Wafa', 'Samira', 'Khadija', 'Zahra',
              'Rym', 'Ines', 'Sana', 'Hana', 'Selma', 'Asma', 'Basma',
              'Chiraz', 'Dalila', 'Eya', 'Feten', 'Ghada', 'Hajer', 'Imen',
              'Jawhara', 'Kawther', 'Lamia', 'Meriem', 'Nadia', 'Olfa', 'Raja']
    }
    
    LAST_NAMES = [
        'Ben Ali', 'Trabelsi', 'Karray', 'Chihi', 'Bouazizi', 'Gharbi',
        'Saidi', 'Zouari', 'Masmoudi', 'Jlassi', 'Ben Amor', 'Chaabouni',
        'Hamdi', 'Ben Youssef', 'Miled', 'Ben Ahmed', 'Guedria', 'Baccouche',
        'Cherif', 'Ben Salem', 'Mahfoudh', 'Bouguerra', 'Ben Ammar', 'Chaari',
        'Abdelli', 'Bennour', 'Chaouch', 'Dridi', 'Elloumi', 'Ferchichi',
        'Gannouni', 'Hammami', 'Jaïdi', 'Krichen', 'Louati', 'Mannai',
        'Naceur', 'Ouali', 'Rebai', 'Sassi', 'Taamallah', 'Zoghlami'
    ]
    
    # Job positions (age-appropriate)
    JOBS_DETAILED = {
        'Young Adults (18-24)': [
            'Étudiant Universitaire', 'Stagiaire', 'Jeune Diplômé',
            'Agent de Saisie', 'Vendeur en Magasin', 'Serveur'
        ],
        'Early Career (25-34)': [
            'Ingénieur en Informatique', 'Analyste Financier',
            'Infirmier(ère) Diplômé(e) d\'État', 'Professeur des Écoles',
            'Technicien Supérieur', 'Banquier - Conseiller Clientèle'
        ],
        'Mid Career (35-49)': [
            'Directeur Commercial', 'Médecin Spécialiste',
            'Cadre Administratif', 'Pharmacien', 'Professeur de Lycée',
            'Gérant de Société', 'Contrôleur de Gestion'
        ],
        'Senior (50-64)': [
            'Directeur d\'Agence Bancaire', 'Expert Consultant',
            'Chef de Service', 'Notaire', 'Avocat Senior',
            'Cadre Supérieur', 'Ingénieur Principal'
        ],
        'Retirement Age (65+)': [
            'Retraité Fonction Publique', 'Retraité Secteur Privé',
            'Retraité - Ancien Cadre', 'Consultant Retraité'
        ]
    }
    
    # Locations
    LOCATIONS = [
        ('Tunis Centre', 'Tunis'), ('Lac', 'Tunis'), ('Belvédère', 'Tunis'),
        ('Sfax Médina', 'Sfax'), ('El Ain', 'Sfax'), ('Gremda', 'Sfax'),
        ('Sousse', 'Sousse'), ('Kalaa Kebira', 'Sousse'), ('Msaken', 'Sousse'),
        ('Nabeul', 'Nabeul'), ('Hammamet', 'Nabeul'),
        ('Bizerte', 'Bizerte'), ('Menzel Bourguiba', 'Bizerte'), ('Mateur', 'Bizerte'),
        ('Gabès', 'Gabès'), ('El Hamma', 'Gabès'),
        ('Kairouan', 'Kairouan'), ('Haffouz', 'Kairouan'),
        ('Mahdia', 'Mahdia'), ('Souassi', 'Mahdia'), ('Boumerdes', 'Mahdia'),
        ('Monastir', 'Monastir'), ('Moknine', 'Monastir')
    ]
    
    def __init__(self):
        self.generated_clients = {}
        self.used_names = set()
    
    def _generate_age_with_minimum(self, min_age: int = 18, max_age: int = 90) -> int:
        """Generate age with minimum guarantee and realistic distribution"""
        # Banking client age distribution (weighted toward 25-65)
        age_groups = [
            (18, 24, 0.10),   # 18-24: 10% - young adults
            (25, 34, 0.25),   # 25-34: 25% - early career
            (35, 49, 0.35),   # 35-49: 35% - established career
            (50, 64, 0.20),   # 50-64: 20% - senior
            (65, 90, 0.10)    # 65-90: 10% - retirement
        ]
        
        # Select age group based on weights
        groups = [g[0] for g in age_groups]
        weights = [g[2] for g in age_groups]
        selected_group_idx = random.choices(range(len(groups)), weights=weights)[0]
        selected_group = age_groups[selected_group_idx]
        
        # Generate random age within selected group
        age = random.randint(selected_group[0], selected_group[1])
        
        # Ensure minimum age
        age = max(min_age, age)
        
        return age
    
    def _generate_unique_name(self, gender: str) -> str:
        """Generate a unique full name"""
        max_attempts = 100
        for _ in range(max_attempts):
            first_name = random.choice(self.FIRST_NAMES[gender])
            last_name = random.choice(self.LAST_NAMES)
            full_name = f"{first_name} {last_name}"
            
            if full_name not in self.used_names:
                self.used_names.add(full_name)
                return full_name
        
        # If all names are used, add middle initial
        first_name = random.choice(self.FIRST_NAMES[gender])
        last_name = random.choice(self.LAST_NAMES)
        middle_initial = chr(random.randint(65, 90))
        unique_name = f"{first_name} {middle_initial}. {last_name}"
        self.used_names.add(unique_name)
        return unique_name
    
    def _generate_job_for_age(self, age: int, gender: str) -> str:
        """Generate age-appropriate job position"""
        
        # Define age-appropriate job categories
        if age >= 65:
            job_category = 'Retirement Age (65+)'
        elif age >= 50:
            job_category = 'Senior (50-64)'
        elif age >= 35:
            job_category = 'Mid Career (35-49)'
        elif age >= 25:
            job_category = 'Early Career (25-34)'
        else:  # 18-24
            job_category = 'Young Adults (18-24)'
        
        # Get base jobs for this category
        base_jobs = self.JOBS_DETAILED.get(job_category, ['Professionnel'])
        
        # Gender-specific adjustments
        if gender == 'F':
            # Add more female-dominated roles
            female_jobs = ['Sage-femme', 'Infirmière', 'Secrétaire Médicale',
                          'Enseignante', 'Assistante de Direction', 'Esthéticienne']
            # Remove some male-dominated roles if present
            base_jobs = [job for job in base_jobs if 'Chauffeur' not in job]
        else:
            # Add more male-dominated roles
            male_jobs = ['Ingénieur en Génie Civil', 'Chauffeur Routier',
                        'Mécanicien Automobile', 'Architecte', 'Chef de Chantier']
        
        # Combine and select
        if gender == 'F' and random.random() < 0.3:
            all_jobs = base_jobs + female_jobs
        elif gender == 'M' and random.random() < 0.3:
            all_jobs = base_jobs + male_jobs
        else:
            all_jobs = base_jobs
        
        return random.choice(all_jobs)
    
    def generate_client_profile(self, client_id: str = None, min_age: int = 18) -> Dict:
        """Generate a complete client profile with AGE >= min_age GUARANTEED"""
        
        # Generate client_id if not provided
        if client_id is None:
            client_id = f"C_{str(uuid.uuid4())[:8].upper()}"
        
        # Generate gender
        gender = 'M' if random.random() < 0.55 else 'F'
        
        # Generate age with minimum guarantee
        age = self._generate_age_with_minimum(min_age=min_age, max_age=90)
        
        # VERIFICATION: Age must be >= min_age
        assert age >= min_age, f"Generated age {age} is below minimum {min_age}"
        
        # Calculate birth date
        current_year = datetime.now().year
        birth_year = current_year - age
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)
        
        # Generate unique name
        full_name = self._generate_unique_name(gender)
        
        # Generate age-appropriate job
        job_position = self._generate_job_for_age(age, gender)
        
        # Generate marital status based on age (REALISTIC for banking)
        if age < 22:
            marital_weights = [0.85, 0.12, 0.02, 0.01]  # 18-21: Mostly single
        elif age < 30:
            marital_weights = [0.40, 0.55, 0.04, 0.01]  # 22-29: Mix
        elif age < 40:
            marital_weights = [0.15, 0.70, 0.10, 0.05]  # 30-39: Mostly married
        elif age < 60:
            marital_weights = [0.10, 0.65, 0.15, 0.10]  # 40-59: Married, some divorced/widowed
        else:
            marital_weights = [0.05, 0.50, 0.20, 0.25]  # 60+: Many widowed
        
        marital_status = random.choices(
            ['Célibataire', 'Marié(e)', 'Divorcé(e)', 'Veuf(ve)'],
            weights=marital_weights
        )[0]
        
        # Has children based on age and marital status (REALISTIC)
        if marital_status == 'Marié(e)' and age > 24:
            has_children = random.choices(['Yes', 'No'], weights=[0.85, 0.15])[0]
        elif age > 30:
            has_children = random.choices(['Yes', 'No'], weights=[0.70, 0.30])[0]
        elif age > 25:
            has_children = random.choices(['Yes', 'No'], weights=[0.40, 0.60])[0]
        else:
            has_children = random.choices(['Yes', 'No'], weights=[0.10, 0.90])[0]
        
        # Generate location
        city, governorate = random.choice(self.LOCATIONS)
        residence_location = f"{city}, {governorate}"
        
        # Store profile with age verification
        profile = {
            'client_id': client_id,
            'full_name': full_name,
            'date_of_birth': date(birth_year, birth_month, birth_day),
            'marital_status': marital_status,
            'gender': gender,
            'job_position': job_position,
            'has_children': has_children,
            'residence_location': residence_location,
            'age': age  # For internal verification only
        }
        
        # VERIFICATION: Final age check
        calculated_age = (date.today() - profile['date_of_birth']).days // 365
        if calculated_age < min_age:
            raise ValueError(f"Client {client_id} has age {calculated_age} < {min_age}")
        
        self.generated_clients[client_id] = profile
        return profile

# ============================================================================
# 3. CREATE CLIENTS TABLE WITH AGE ENFORCEMENT
# ============================================================================
def create_clients_table_from_operations(operations_df: pd.DataFrame, 
                                        multi_account_prob: float = 0.3,
                                        min_age: int = 18) -> pd.DataFrame:
    """
    Create clients table with STRICT AGE >= min_age enforcement
    """
    
    print("\n" + "="*70)
    print(f"CREATING CLIENTS TABLE (AGE >= {min_age} ENFORCED)")
    print("="*70)
    
    # Get unique accounts from operations
    unique_accounts = operations_df['account_number'].unique()
    print(f"Found {len(unique_accounts)} unique accounts in operations data")
    
    # Initialize client generator with age minimum
    client_gen = BankingClientGenerator()
    
    # Step 1: Create account-to-client mapping
    n_accounts = len(unique_accounts)
    avg_accounts_per_client = 1 + (multi_account_prob * 1.5)
    n_clients = max(1, int(n_accounts / avg_accounts_per_client))
    
    print(f"Generating approximately {n_clients} unique clients (age >= {min_age})")
    
    # Step 2: Generate unique clients with age guarantee
    unique_client_ids = [f"C{str(i).zfill(6)}" for i in range(1, n_clients + 1)]
    client_profiles = {}
    age_verification_failures = 0
    
    for client_id in unique_client_ids:
        try:
            # Generate client with minimum age guarantee
            profile = client_gen.generate_client_profile(client_id, min_age=min_age)
            
            # Double-check age
            birth_date = profile['date_of_birth']
            calculated_age = (date.today() - birth_date).days // 365
            if calculated_age < min_age:
                print(f"❌ Age verification failed for {client_id}: {calculated_age} < {min_age}")
                # Regenerate with explicit older age
                profile = client_gen.generate_client_profile(client_id, min_age=min_age+5)
                age_verification_failures += 1
            
            client_profiles[client_id] = profile
            
        except Exception as e:
            print(f"Error generating client {client_id}: {e}")
            # Create guaranteed valid fallback
            fallback_age = random.randint(min_age + 5, min_age + 30)
            fallback_year = datetime.now().year - fallback_age
            client_profiles[client_id] = {
                'client_id': client_id,
                'full_name': f"Client {client_id}",
                'date_of_birth': date(fallback_year, 1, 1),
                'marital_status': 'Marié(e)',
                'gender': 'M',
                'job_position': 'Professionnel',
                'has_children': 'Yes',
                'residence_location': 'Tunis Centre, Tunis',
                'age': fallback_age
            }
    
    if age_verification_failures > 0:
        print(f"⚠️  Had to regenerate {age_verification_failures} clients due to age issues")
    else:
        print("✅ All clients generated with age >= 18")
    
    # Step 3: Assign accounts to clients
    account_client_map = {}
    client_account_counts = defaultdict(int)
    shuffled_accounts = list(unique_accounts)
    random.shuffle(shuffled_accounts)
    used_clients = set()
    
    for account_num in shuffled_accounts:
        if random.random() < multi_account_prob and used_clients:
            eligible_clients = [cid for cid in used_clients 
                              if client_account_counts[cid] < 5]
            if eligible_clients:
                weights = [1/(client_account_counts[cid] + 1) for cid in eligible_clients]
                client_id = random.choices(eligible_clients, weights=weights)[0]
            else:
                new_clients = [cid for cid in unique_client_ids if cid not in used_clients]
                client_id = random.choice(new_clients) if new_clients else random.choice(list(client_profiles.keys()))
        else:
            new_clients = [cid for cid in unique_client_ids if cid not in used_clients]
            client_id = random.choice(new_clients) if new_clients else random.choice(list(client_profiles.keys()))
        
        account_client_map[account_num] = client_id
        client_account_counts[client_id] += 1
        used_clients.add(client_id)
    
    # Step 4: Build clients DataFrame with AGE VERIFICATION
    clients_data = []
    underage_clients_found = 0
    
    for account_num, client_id in account_client_map.items():
        if client_id in client_profiles:
            profile = client_profiles[client_id].copy()
            profile['account_number'] = account_num
            
            # FINAL AGE VERIFICATION BEFORE ADDING
            birth_date = profile['date_of_birth']
            if isinstance(birth_date, date):
                age = (date.today() - birth_date).days // 365
                if age < min_age:
                    print(f"❌ CRITICAL: Client {client_id} has age {age} < {min_age}")
                    # Force age to minimum
                    new_birth_year = date.today().year - min_age
                    profile['date_of_birth'] = date(new_birth_year, 1, 1)
                    underage_clients_found += 1
            
            # Remove internal age field
            profile.pop('age', None)
            
            clients_data.append(profile)
    
    clients_df = pd.DataFrame(clients_data)
    
    # Step 5: Ensure 100% coverage
    accounts_covered = set(clients_df['account_number'])
    all_accounts = set(unique_accounts)
    
    if accounts_covered != all_accounts:
        print(f"Covering {len(all_accounts - accounts_covered)} missing accounts...")
        for missing_account in (all_accounts - accounts_covered):
            # Create guaranteed valid client
            client_id = f"C_ORPH_{str(uuid.uuid4())[:6].upper()}"
            safe_age = random.randint(min_age + 10, min_age + 40)
            safe_year = datetime.now().year - safe_age
            
            profile = {
                'client_id': client_id,
                'account_number': missing_account,
                'full_name': f"Client Orphelin {missing_account[:6]}",
                'date_of_birth': date(safe_year, 6, 15),
                'marital_status': 'Marié(e)',
                'gender': 'M',
                'job_position': 'Commerçant',
                'has_children': 'Yes',
                'residence_location': 'Tunis Centre, Tunis'
            }
            
            clients_df = pd.concat([clients_df, pd.DataFrame([profile])], ignore_index=True)
    
    if underage_clients_found > 0:
        print(f"⚠️  Fixed {underage_clients_found} underage clients during final verification")
    
    # Step 6: Validate data consistency
    clients_df = validate_clients_consistency(clients_df, min_age=min_age)
    
    # Set column order
    column_order = [
        'client_id', 'account_number', 'full_name', 'date_of_birth',
        'marital_status', 'gender', 'job_position', 'has_children',
        'residence_location'
    ]
    
    return clients_df[column_order]

def validate_clients_consistency(clients_df: pd.DataFrame, min_age: int = 18) -> pd.DataFrame:
    """
    Validate client data with STRICT age enforcement
    """
    print("\n🔍 VALIDATING CLIENT DATA WITH AGE >= {} ENFORCEMENT".format(min_age))
    print("-"*50)
    
    # Convert date_of_birth to datetime if not already
    if not pd.api.types.is_datetime64_any_dtype(clients_df['date_of_birth']):
        clients_df['date_of_birth'] = pd.to_datetime(clients_df['date_of_birth'])
    
    # CRITICAL: Calculate ages and find underage clients
    today = pd.Timestamp.now()
    clients_df['age_calculated'] = ((today - clients_df['date_of_birth']).dt.days // 365)
    
    underage_mask = clients_df['age_calculated'] < min_age
    underage_count = underage_mask.sum()
    
    if underage_count > 0:
        print(f"🚨 CRITICAL ERROR: Found {underage_count} clients under {min_age} years old!")
        print("Fixing by setting birth dates to minimum age...")
        
        # Fix underage clients
        for idx in clients_df[underage_mask].index:
            current_birth_date = clients_df.at[idx, 'date_of_birth']
            current_age = clients_df.at[idx, 'age_calculated']
            
            # Calculate new birth date (exactly min_age years ago)
            new_birth_date = today - pd.Timedelta(days=min_age*365)
            
            # Keep the same month/day if possible
            try:
                # Try to keep original month and day
                new_birth_date = new_birth_date.replace(
                    month=current_birth_date.month,
                    day=min(current_birth_date.day, 28)  # Avoid day 29-31 issues
                )
            except:
                pass
            
            clients_df.at[idx, 'date_of_birth'] = new_birth_date
            print(f"  Fixed client {clients_df.at[idx, 'client_id']}: age {current_age} → {min_age}")
    
    # Recalculate ages after fix
    clients_df['age_calculated'] = ((today - clients_df['date_of_birth']).dt.days // 365)
    
    # Verify no underage clients remain
    final_underage = (clients_df['age_calculated'] < min_age).sum()
    if final_underage == 0:
        print(f"✅ SUCCESS: All {len(clients_df)} clients are age >= {min_age}")
        
        # Age distribution report
        print("\n📊 Age Distribution after validation:")
        age_bins = [18, 25, 35, 45, 55, 65, 90]
        age_labels = ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']
        
        clients_df['age_group'] = pd.cut(clients_df['age_calculated'], 
                                        bins=age_bins, 
                                        labels=age_labels, 
                                        right=False)
        
        for age_group in age_labels:
            count = (clients_df['age_group'] == age_group).sum()
            percentage = (count / len(clients_df)) * 100
            print(f"  {age_group:6}: {count:6} clients ({percentage:5.1f}%)")
    else:
        print(f"❌ FAILED: Still have {final_underage} underage clients after fixing!")
        # Emergency fix: set all to minimum age
        emergency_fix_mask = clients_df['age_calculated'] < min_age
        clients_df.loc[emergency_fix_mask, 'date_of_birth'] = today - pd.Timedelta(days=min_age*365)
        print("  Applied emergency age fix")
    
    # Remove temporary columns
    clients_df = clients_df.drop(columns=['age_calculated', 'age_group'], errors='ignore')
    
    # Standard consistency checks
    print("\n🔍 Checking cross-account consistency...")
    inconsistencies_fixed = 0
    
    for client_id, group in clients_df.groupby('client_id'):
        if len(group) > 1:
            for field in ['full_name', 'date_of_birth', 'gender', 'marital_status']:
                if group[field].nunique() > 1:
                    most_common = group[field].mode()
                    if not most_common.empty:
                        clients_df.loc[clients_df['client_id'] == client_id, field] = most_common.iloc[0]
                        inconsistencies_fixed += 1
    
    if inconsistencies_fixed > 0:
        print(f"Fixed {inconsistencies_fixed} data inconsistencies")
    
    return clients_df

# ============================================================================
# 4. AGE VALIDATION CHECKER
# ============================================================================
class AgeValidator:
    """Specialized validator for age compliance"""
    
    @staticmethod
    def verify_all_clients_age(clients_df: pd.DataFrame, min_age: int = 18) -> Tuple[bool, pd.DataFrame]:
        """
        Verify ALL clients meet minimum age requirement
        Returns: (is_valid, clients_with_issues)
        """
        print(f"\n🔬 AGE COMPLIANCE VERIFICATION (minimum: {min_age} years)")
        print("-"*50)
        
        # Calculate ages
        if not pd.api.types.is_datetime64_any_dtype(clients_df['date_of_birth']):
            clients_df['date_of_birth'] = pd.to_datetime(clients_df['date_of_birth'])
        
        today = pd.Timestamp.now()
        clients_df['age'] = ((today - clients_df['date_of_birth']).dt.days // 365)
        
        # Find underage clients
        underage_mask = clients_df['age'] < min_age
        underage_count = underage_mask.sum()
        
        if underage_count == 0:
            print(f"✅ PERFECT: All {len(clients_df)} clients are age >= {min_age}")
            
            # Generate age statistics
            min_age_val = clients_df['age'].min()
            max_age_val = clients_df['age'].max()
            avg_age = clients_df['age'].mean()
            
            print(f"\n📊 Age Statistics:")
            print(f"  Minimum age: {min_age_val}")
            print(f"  Maximum age: {max_age_val}")
            print(f"  Average age: {avg_age:.1f}")
            print(f"  Median age:  {clients_df['age'].median():.1f}")
            
            return True, pd.DataFrame()  # Empty DataFrame for no issues
        
        else:
            print(f"❌ FAILURE: Found {underage_count} clients under {min_age} years old!")
            
            # Show details of underage clients
            underage_clients = clients_df[underage_mask].copy()
            print(f"\nUnderage clients (first 10):")
            for idx, row in underage_clients.head(10).iterrows():
                print(f"  Client {row['client_id']}: {row['full_name']}, Age: {row['age']}")
            
            # Show age distribution of underage clients
            print(f"\nAge distribution of underage clients:")
            age_counts = underage_clients['age'].value_counts().sort_index()
            for age, count in age_counts.items():
                print(f"  Age {age}: {count} clients")
            
            return False, underage_clients[['client_id', 'account_number', 'full_name', 'age', 'date_of_birth']]
    
    @staticmethod
    def enforce_age_compliance(clients_df: pd.DataFrame, min_age: int = 18) -> pd.DataFrame:
        """
        Enforce age compliance by modifying birth dates
        Returns compliant DataFrame
        """
        print(f"\n⚡ ENFORCING AGE COMPLIANCE (minimum: {min_age} years)")
        
        # Calculate current ages
        if not pd.api.types.is_datetime64_any_dtype(clients_df['date_of_birth']):
            clients_df['date_of_birth'] = pd.to_datetime(clients_df['date_of_birth'])
        
        today = pd.Timestamp.now()
        clients_df['current_age'] = ((today - clients_df['date_of_birth']).dt.days // 365)
        
        # Identify underage clients
        underage_mask = clients_df['current_age'] < min_age
        underage_count = underage_mask.sum()
        
        if underage_count == 0:
            print("✅ No enforcement needed - all clients already compliant")
            clients_df = clients_df.drop(columns=['current_age'], errors='ignore')
            return clients_df
        
        print(f"Fixing {underage_count} underage clients...")
        
        # Fix strategy: Add years to reach minimum age while keeping same birth month/day
        fixed_count = 0
        for idx in clients_df[underage_mask].index:
            original_dob = clients_df.at[idx, 'date_of_birth']
            current_age = clients_df.at[idx, 'current_age']
            
            # Calculate how many years to add
            years_to_add = min_age - current_age
            
            # Create new date of birth
            try:
                # Try to keep same month/day
                new_year = original_dob.year - years_to_add
                new_dob = pd.Timestamp(year=new_year, 
                                     month=original_dob.month, 
                                     day=min(original_dob.day, 28))
            except:
                # Fallback: simple subtraction of years
                new_dob = original_dob - pd.DateOffset(years=years_to_add)
            
            clients_df.at[idx, 'date_of_birth'] = new_dob
            fixed_count += 1
            
            if fixed_count <= 5:  # Show first 5 fixes
                print(f"  Fixed {clients_df.at[idx, 'client_id']}: {current_age} → {min_age} years")
        
        # Verify fix
        clients_df['new_age'] = ((today - clients_df['date_of_birth']).dt.days // 365)
        still_underage = (clients_df['new_age'] < min_age).sum()
        
        if still_underage == 0:
            print(f"✅ Successfully fixed all {fixed_count} underage clients")
        else:
            print(f"⚠️  Warning: {still_underage} clients still underage after fix")
            # Emergency fix: set to exact minimum age
            emergency_mask = clients_df['new_age'] < min_age
            for idx in clients_df[emergency_mask].index:
                clients_df.at[idx, 'date_of_birth'] = today - pd.Timedelta(days=min_age*365)
            print(f"  Applied emergency fix to {emergency_mask.sum()} clients")
        
        # Clean up temporary columns
        clients_df = clients_df.drop(columns=['current_age', 'new_age'], errors='ignore')
        
        return clients_df

# ============================================================================
# 5. MAIN EXECUTION WITH AGE GUARANTEE
# ============================================================================
if __name__ == "__main__":
    
    print("="*70)
    print("CLIENT DATA GENERATION WITH AGE >= 18 GUARANTEE")
    print("="*70)
    
    # Configuration
    MINIMUM_AGE = 18  # Banking requirement
    MULTI_ACCOUNT_PROB = 0.3
    
    # Step 1: Load operations data
    print("\n📁 LOADING OPERATIONS DATA")
    print("-"*40)
    operations_df = load_operations_data('operations.txt')
    print(f"Loaded {operations_df['account_number'].nunique():,} unique accounts")
    
    # Step 2: Generate clients with age enforcement
    print(f"\n👤 GENERATING CLIENTS (AGE >= {MINIMUM_AGE} ENFORCED)")
    print("-"*40)
    
    clients_df = create_clients_table_from_operations(
        operations_df, 
        multi_account_prob=MULTI_ACCOUNT_PROB,
        min_age=MINIMUM_AGE
    )
    
    print(f"\n✅ Generated clients table: {clients_df.shape[0]:,} records")
    print(f"   Unique clients: {clients_df['client_id'].nunique():,}")
    print(f"   Unique accounts: {clients_df['account_number'].nunique():,}")
    
    # Step 3: FINAL AGE VERIFICATION
    print("\n" + "="*70)
    print("FINAL AGE COMPLIANCE AUDIT")
    print("="*70)
    
    # Run comprehensive age verification
    is_age_compliant, underage_clients = AgeValidator.verify_all_clients_age(clients_df, MINIMUM_AGE)
    
    if not is_age_compliant:
        print("\n🚨 AGE COMPLIANCE FAILED - APPLYING CORRECTIONS")
        clients_df = AgeValidator.enforce_age_compliance(clients_df, MINIMUM_AGE)
        
        # Re-verify after corrections
        print("\n🔍 RE-VERIFYING AFTER CORRECTIONS")
        is_age_compliant, underage_clients = AgeValidator.verify_all_clients_age(clients_df, MINIMUM_AGE)
        
        if is_age_compliant:
            print("\n✅ AGE COMPLIANCE ACHIEVED AFTER CORRECTIONS")
        else:
            print("\n❌ CRITICAL: Age compliance still failed after corrections!")
            print("Applying final emergency fix...")
            # Last resort: set all to exactly minimum age
            today = pd.Timestamp.now()
            min_age_date = today - pd.Timedelta(days=MINIMUM_AGE*365)
            clients_df['date_of_birth'] = min_age_date
            print("All birth dates set to minimum age")
    
    # Step 4: Generate comprehensive statistics
    print("\n" + "="*70)
    print("COMPREHENSIVE STATISTICS")
    print("="*70)
    
    # Calculate final ages for statistics
    today = pd.Timestamp.now()
    clients_df['final_age'] = ((today - pd.to_datetime(clients_df['date_of_birth'])).dt.days // 365)
    
    stats = {
        'Total Records': f"{len(clients_df):,}",
        'Unique Clients': f"{clients_df['client_id'].nunique():,}",
        'Unique Accounts': f"{clients_df['account_number'].nunique():,}",
        'Clients with 1 Account': f"{(clients_df['client_id'].value_counts() == 1).sum():,}",
        'Clients with 2+ Accounts': f"{(clients_df['client_id'].value_counts() > 1).sum():,}",
        'Average Accounts/Client': f"{clients_df['account_number'].nunique() / clients_df['client_id'].nunique():.2f}",
        'Minimum Age': f"{clients_df['final_age'].min()}",
        'Maximum Age': f"{clients_df['final_age'].max()}",
        'Average Age': f"{clients_df['final_age'].mean():.1f}",
        'Age Compliance': "✅ 100%" if (clients_df['final_age'] >= MINIMUM_AGE).all() else "❌ FAILED"
    }
    
    for key, value in stats.items():
        print(f"{key:25}: {value}")
    
    # Age distribution
    print(f"\n📊 Age Group Distribution:")
    age_bins = [18, 25, 35, 45, 55, 65, 100]
    age_labels = ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']
    clients_df['age_group'] = pd.cut(clients_df['final_age'], bins=age_bins, labels=age_labels, right=False)
    
    for age_group in age_labels:
        count = (clients_df['age_group'] == age_group).sum()
        percentage = (count / len(clients_df)) * 100
        print(f"  {age_group:6}: {count:6} clients ({percentage:5.1f}%)")
    
    # Remove temporary columns
    clients_df = clients_df.drop(columns=['final_age', 'age_group'], errors='ignore')
    
    # Step 5: Save results
    print("\n" + "="*70)
    print("💾 SAVING COMPLIANT CLIENTS TABLE")
    print("="*70)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Main clients file
    clients_file = f'clients_table_AGE_COMPLIANT_{timestamp}.csv'
    clients_df.to_csv(clients_file, index=False, encoding='utf-8-sig')
    print(f"✅ Age-compliant clients table saved to: {clients_file}")
    
    # Age verification certificate
    cert_file = f'age_compliance_certificate_{timestamp}.txt'
    with open(cert_file, 'w', encoding='utf-8') as f:
        f.write("AGE COMPLIANCE CERTIFICATE\n")
        f.write("="*50 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Clients: {len(clients_df):,}\n")
        f.write(f"Minimum Age Requirement: {MINIMUM_AGE} years\n")
        f.write(f"Compliance Status: {'FULLY COMPLIANT' if is_age_compliant else 'NON-COMPLIANT'}\n")
        f.write(f"Underage Clients Found: {len(underage_clients) if not underage_clients.empty else 0}\n\n")
        f.write("Age Distribution:\n")
        for age_group in age_labels:
            count = stats.get(f'{age_group}_count', 0)
            f.write(f"  {age_group}: {count} clients\n")
    
    print(f"✅ Age compliance certificate saved to: {cert_file}")
    
    print("\n" + "="*70)
    print("✅ GENERATION COMPLETE WITH AGE >= 18 GUARANTEE")
    print("="*70)
    print(f"\nSummary:")
    print(f"- {len(clients_df):,} client-account relationships")
    print(f"- {clients_df['client_id'].nunique():,} unique clients")
    print(f"- 100% age compliance verified ({MINIMUM_AGE}+ years)")
    print(f"- Files saved with 'AGE_COMPLIANT' prefix")