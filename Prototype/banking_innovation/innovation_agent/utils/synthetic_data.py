import random
import json
import os
from django.conf import settings
from faker import Faker
from innovation_agent.models import Customer

fake = Faker('fr_FR')

def load_catalog_product_names():
    """Load real product names from JSON catalog."""
    path = os.path.join(settings.BASE_DIR, 'product_catalog.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [p['name'] for p in data.get('products', []) if p.get('name')]
    except:
        return []

def generate_synthetic_customers(num_customers=150, quarters=['2025-Q1','2025-Q2','2025-Q3','2025-Q4']):
    # ------------------------------------------------------------------
    # CRITICAL FIX: Delete all existing customers to avoid duplicate keys
    # ------------------------------------------------------------------
    Customer.objects.all().delete()
    
    catalog_products = load_catalog_product_names()
    if not catalog_products:
        print("⚠ No catalog found – using fallback product list.")
        catalog_products = ["Carte Classique", "Compte Épargne", "Prêt Auto"]
    
    # Segment profiles (all numbers are random ranges)
    segments = {
        'YoungProfessional': {
            'age': (22,35), 'income': (1800,3500),
            'profession': ['Ingénieur','Consultant','Commercial','Développeur','Designer'],
            'tenure': (1,6),
            'spending': (1200,2500),
            'savings': (2000,15000),
            'investment': ['FCP','Assurance-Vie'],
            'credit': True, 'loan_prob':0.2, 'loan_type': ['Auto','Personnel'],
            'insurance': {'life':0.3,'health':0.6,'car':0.5,'home':0.2},
            'digital': {'mobile':0.9,'online':0.8,'contactless':0.8},
            'marital': ['Single','Married'], 'children': (0,1),
            'product_weights': [0.4,0.3,0.5,0.3,0.4,0.15,0.15,0.2]
        },
        'FamilyWithChildren': {
            'age': (30,50), 'income': (2500,5000),
            'profession': ['Enseignant','Fonctionnaire','Médecin','Directeur','Ingénieur'],
            'tenure': (5,20),
            'spending': (2000,4000),
            'savings': (5000,30000),
            'investment': ['Assurance-Vie','FCP','Obligations'],
            'credit': True, 'loan_prob':0.6, 'loan_type': ['Habitat','Auto','Personnel'],
            'insurance': {'life':0.7,'health':0.9,'car':0.8,'home':0.6},
            'digital': {'mobile':0.7,'online':0.7,'contactless':0.6},
            'marital': ['Married'], 'children': (1,4),
            'product_weights': [0.4,0.3,0.1,0.5,0.3,0.5,0.3,0.3,0.5]
        },
        'EmptyNester': {
            'age': (55,70), 'income': (2000,4000),
            'profession': ['Retraité','Enseignant','Cadre supérieur'],
            'tenure': (15,35),
            'spending': (1500,3000),
            'savings': (20000,80000),
            'investment': ['Assurance-Vie','Obligations','FCP'],
            'credit': True, 'loan_prob':0.2, 'loan_type': ['Habitat'],
            'insurance': {'life':0.6,'health':0.8,'car':0.5,'home':0.7},
            'digital': {'mobile':0.5,'online':0.6,'contactless':0.3},
            'marital': ['Married','Widowed'], 'children': (0,0),
            'product_weights': [0.3,0.6,0.4,0.5,0.4,0.6,0.4]
        },
        'HighNetWorth': {
            'age': (40,65), 'income': (6000,15000),
            'profession': ['PDG','Avocat','Médecin spécialiste','Entrepreneur'],
            'tenure': (8,30),
            'spending': (5000,10000),
            'savings': (50000,300000),
            'investment': ['Assurance-Vie','FCP','Actions','Obligations','Private Equity'],
            'credit': True, 'loan_prob':0.5, 'loan_type': ['Habitat','Personnel'],
            'insurance': {'life':0.9,'health':0.9,'car':0.9,'home':0.9},
            'digital': {'mobile':0.8,'online':0.9,'contactless':0.7},
            'marital': ['Married'], 'children': (0,2),
            'product_weights': [0.5,0.4,0.5,0.3,0.4,0.2,0.3,0.3]
        },
        'Entrepreneur': {
            'age': (30,55), 'income': (3000,8000),
            'profession': ['Entrepreneur','Patron PME','Freelance'],
            'tenure': (2,15),
            'spending': (2500,5000),
            'savings': (10000,50000),
            'investment': ['FCP','Assurance-Vie','Obligations'],
            'credit': True, 'loan_prob':0.7, 'loan_type': ['Auto','Personnel','Aménagement'],
            'insurance': {'life':0.5,'health':0.7,'car':0.8,'home':0.4},
            'digital': {'mobile':0.8,'online':0.9,'contactless':0.6},
            'marital': ['Married'], 'children': (0,2),
            'product_weights': [0.4,0.3,0.5,0.4,0.3,0.3,0.3]
        },
        'Student': {
            'age': (18,25), 'income': (300,1000),
            'profession': ['Étudiant'],
            'tenure': (0,3),
            'spending': (400,1200),
            'savings': (500,5000),
            'investment': [],
            'credit': False, 'loan_prob':0.1, 'loan_type': ['Études'],
            'insurance': {'life':0.1,'health':0.2,'car':0.1,'home':0.0},
            'digital': {'mobile':0.9,'online':0.8,'contactless':0.7},
            'marital': ['Single'], 'children': (0,0),
            'product_weights': [0.5,0.4,0.6,0.5,0.3,0.2,0.2]
        },
        'Retiree': {
            'age': (65,85), 'income': (1200,2500),
            'profession': ['Retraité'],
            'tenure': (20,45),
            'spending': (800,1800),
            'savings': (15000,60000),
            'investment': ['Assurance-Vie','Obligations'],
            'credit': True, 'loan_prob':0.05, 'loan_type': [],
            'insurance': {'life':0.8,'health':0.9,'car':0.3,'home':0.8},
            'digital': {'mobile':0.3,'online':0.3,'contactless':0.1},
            'marital': ['Married','Widowed'], 'children': (0,0),
            'product_weights': [0.5,0.7,0.5,0.8,0.7,0.6,0.4]
        }
    }
    
    seasonality = {
        '2025-Q1': {'spending':0.9, 'travel':0.8},
        '2025-Q2': {'spending':1.0, 'travel':1.3},
        '2025-Q3': {'spending':1.1, 'travel':1.2},
        '2025-Q4': {'spending':1.2, 'travel':0.7}
    }
    
    growth_trend = {q: 1 + (idx * 0.02) for idx, q in enumerate(quarters)}
    
    for quarter in quarters:
        for i in range(num_customers):
            seg = random.choice(list(segments.keys()))
            params = segments[seg]
            
            age = random.randint(*params['age'])
            gender = random.choice(['M','F'])
            income = int(random.randint(*params['income']) * growth_trend[quarter])
            profession = random.choice(params['profession'])
            tenure = random.randint(*params['tenure'])
            marital = random.choice(params['marital'])
            children = random.randint(*params['children'])
            
            spending = int(random.randint(*params['spending']) * seasonality[quarter]['spending'])
            supermarket = int(random.randint(50,400) * (1 + 0.3 if seg in ['FamilyWithChildren','Retiree'] else 1))
            online = random.randint(1,10)
            mobile = random.randint(1,10)
            
            savings = int(random.randint(*params['savings']) * growth_trend[quarter])
            investment = random.sample(params['investment'], k=min(len(params['investment']), random.randint(0,2))) if params['investment'] else []
            
            has_credit_card = params['credit'] and random.random() < 0.7
            has_loan = random.random() < params['loan_prob']
            loan_amount = random.randint(5000,50000) if has_loan else 0
            loan_type = random.choice(params['loan_type']) if has_loan and params['loan_type'] else ''
            
            life_ins = random.random() < params['insurance']['life']
            health_ins = random.random() < params['insurance']['health']
            car_ins = random.random() < params['insurance']['car']
            home_ins = random.random() < params['insurance']['home']
            
            mobile_bank = random.random() < params['digital']['mobile']
            online_bank = random.random() < params['digital']['online']
            contactless = random.random() < params['digital']['contactless']
            
            # Select random products from catalog
            num_products = random.randint(0, 3)
            if num_products == 0:
                selected_products = [random.choice(catalog_products)]
            else:
                selected_products = random.sample(catalog_products, min(num_products, len(catalog_products)))
            held_products = list(set(selected_products))
            
            Customer.objects.create(
                customer_id=f"C{quarter.replace('-','')}_{i:04d}",
                age=age,
                gender=gender,
                income=income,
                profession=profession,
                tenure=tenure,
                segment=seg,
                quarter=quarter,
                monthly_spending=spending,
                supermarket_spending=supermarket,
                online_shopping_score=online,
                mobile_payment_score=mobile,
                savings_balance=savings,
                investment_products=','.join(investment),
                has_credit_card=has_credit_card,
                has_loan=has_loan,
                loan_amount=loan_amount,
                loan_type=loan_type,
                has_life_insurance=life_ins,
                has_health_insurance=health_ins,
                has_car_insurance=car_ins,
                has_home_insurance=home_ins,
                uses_mobile_banking=mobile_bank,
                uses_online_banking=online_bank,
                uses_contactless=contactless,
                marital_status=marital,
                children_count=children,
                products_held=','.join(held_products)
            )
    print(f"✅ Generated {num_customers * len(quarters)} customers across {quarters}")