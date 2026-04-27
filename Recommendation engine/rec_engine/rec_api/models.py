from django.db import models

class ClientProfile(models.Model):
    # Identification
    client_id = models.CharField(max_length=50, unique=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)  # one account per row (deduplicated)
    full_name = models.CharField(max_length=200, blank=True, null=True)
    
    # Demographics
    date_of_birth = models.DateField(blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)
    marital_status = models.CharField(max_length=50, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    job_position = models.CharField(max_length=100, blank=True, null=True)
    residence_location = models.CharField(max_length=100, blank=True, null=True)
    
    # RFM raw values
    recency_days = models.IntegerField()
    frequency = models.IntegerField()
    monetary = models.DecimalField(max_digits=15, decimal_places=2)
    
    # RFM scores
    recency_score = models.IntegerField()
    frequency_score = models.IntegerField()
    monetary_score = models.IntegerField()
    
    # Segment
    rfm_segment = models.CharField(max_length=50)
    
    # Augmented financial profile
    spending_capacity = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    activity_level = models.FloatField(blank=True, null=True)
    spending_regularity = models.FloatField(blank=True, null=True)
    engagement_score = models.IntegerField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['client_id']),
            models.Index(fields=['rfm_segment']),
        ]

class ProductRecommendation(models.Model):
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='recommendations')
    product_name = models.CharField(max_length=200)
    relevance_score = models.FloatField()
    explanation = models.TextField()
    recommended_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-recommended_at']