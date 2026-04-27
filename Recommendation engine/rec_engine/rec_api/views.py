from rest_framework.decorators import api_view
from rest_framework.response import Response
from .recommendation_engine import RecommendationEngine
from .models import ProductRecommendation, ClientProfile
from .serializers import ProductRecommendationSerializer

engine = RecommendationEngine()

@api_view(['GET'])
def recommend(request, client_id):
    """Get recommendations for a specific client"""
    result = engine.get_recommendations(client_id)
    if "error" in result:
        return Response({"error": result["error"]}, status=404)
    
    # Save recommendations to database
    try:
        client = ClientProfile.objects.get(client_id=client_id)
        # Delete old recommendations for this client (optional)
        ProductRecommendation.objects.filter(client=client).delete()
        for rec in result.get('recommendations', []):
            ProductRecommendation.objects.create(
                client=client,
                product_name=rec['product_name'],
                relevance_score=rec['score'],
                explanation=rec['explanation']
            )
    except ClientProfile.DoesNotExist:
        pass
    
    return Response(result)

@api_view(['GET'])
def recommend_by_name(request, name):
    """Find client by name (partial match) and return recommendations"""
    clients = ClientProfile.objects.filter(full_name__icontains=name)
    if not clients:
        return Response({"error": f"No client found with name containing '{name}'"}, status=404)
    # For simplicity, take the first match
    client = clients.first()
    return recommend(request, client.client_id)