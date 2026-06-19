from django.db import models

class Customer(models.Model):
    SEGMENT_CHOICES = [
        ('YoungProfessional', 'Jeunes Professionnels'),
        ('FamilyWithChildren', 'Familles avec Enfants'),
        ('EmptyNester', 'Nids Vides'),
        ('HighNetWorth', 'Haute Valeur Nette'),
        ('Entrepreneur', 'Entrepreneurs'),
        ('Student', 'Étudiants'),
        ('Retiree', 'Retraités'),
    ]
    
    # Core
    customer_id = models.CharField(max_length=10, unique=True)
    age = models.IntegerField()
    gender = models.CharField(max_length=1, choices=[('M','Homme'),('F','Femme')])
    income = models.IntegerField()
    profession = models.CharField(max_length=50)
    tenure = models.IntegerField()
    segment = models.CharField(max_length=20, choices=SEGMENT_CHOICES)
    quarter = models.CharField(max_length=7)
    
    # Financial behaviors
    monthly_spending = models.IntegerField()
    supermarket_spending = models.IntegerField()
    online_shopping_score = models.IntegerField()
    mobile_payment_score = models.IntegerField()
    savings_balance = models.IntegerField()
    investment_products = models.CharField(max_length=100, blank=True)
    
    # Credit & loans
    has_credit_card = models.BooleanField(default=False)
    has_loan = models.BooleanField(default=False)
    loan_amount = models.IntegerField(default=0)
    loan_type = models.CharField(max_length=30, blank=True)
    
    # Insurance
    has_life_insurance = models.BooleanField(default=False)
    has_health_insurance = models.BooleanField(default=False)
    has_car_insurance = models.BooleanField(default=False)
    has_home_insurance = models.BooleanField(default=False)
    
    # Digital
    uses_mobile_banking = models.BooleanField(default=False)
    uses_online_banking = models.BooleanField(default=False)
    uses_contactless = models.BooleanField(default=False)
    
    # Life
    marital_status = models.CharField(max_length=10, choices=[('Single','Célibataire'),('Married','Marié'),('Divorced','Divorcé'),('Widowed','Veuf')])
    children_count = models.IntegerField(default=0)
    
    # Products held (reference to catalog product names)
    products_held = models.TextField(blank=True)  # comma separated
    
    class Meta:
        unique_together = ['customer_id', 'quarter']