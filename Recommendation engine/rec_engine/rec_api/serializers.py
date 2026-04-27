from rest_framework import serializers
from .models import ClientProfile, ProductRecommendation

class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = ['client_id', 'full_name', 'age', 'marital_status', 'gender', 
                  'job_position', 'residence_location', 'rfm_segment', 
                  'recency_score', 'frequency_score', 'monetary_score', 
                  'engagement_score', 'spending_capacity', 'activity_level']

class ProductRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRecommendation
        fields = ['product_name', 'relevance_score', 'explanation']