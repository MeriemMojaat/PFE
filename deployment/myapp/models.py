from django.db import models
from django.contrib.auth.models import User

class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f"Conversation {self.id}"

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
    
class RecommendationXAI(models.Model):
    client_id = models.CharField(max_length=20)
    product_name = models.CharField(max_length=200)
    factual_score = models.IntegerField(null=True, blank=True)
    relevance_score = models.IntegerField(null=True, blank=True)
    clarity_score = models.IntegerField(null=True, blank=True)
    hallucination_score = models.IntegerField(null=True, blank=True)
    overall_score = models.FloatField(null=True, blank=True)
    judge_feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('client_id', 'product_name')
class RecommendationFeedback(models.Model):
    client_id = models.CharField(max_length=20)
    product_name = models.CharField(max_length=200)
    rating = models.IntegerField(choices=[(1,'👍'), (0,'👎')])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
class ProductScoreModifier(models.Model):
    product_name = models.CharField(max_length=200, unique=True)
    modifier = models.FloatField(default=0.0)  # negative for disliked, positive for liked
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product_name}: {self.modifier}"