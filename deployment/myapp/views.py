import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .rag_system import ProductIndex, OllamaClient, RAGSystem
import os
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Conversation, Message

from django.utils import timezone
from datetime import timedelta
from .models import RecommendationFeedback, ProductScoreModifier

# Initialize RAG system (only once when server starts)
index = ProductIndex("product_contents.json")
llm = OllamaClient(model="llama3:8b")   # or your model
rag = RAGSystem(index, llm)
json_path = os.path.join(settings.BASE_DIR, 'product_contents.json')
def get_current_conversation(request):
    """Get or create the user's current conversation (stored in session)."""
    user = request.user
    conv_id = request.session.get('current_conversation_id')
    if conv_id:
        try:
            conv = Conversation.objects.get(id=conv_id, user=user)
            return conv
        except Conversation.DoesNotExist:
            pass
    # Create new conversation
    conv = Conversation.objects.create(user=user, title="Nouvelle conversation")
    request.session['current_conversation_id'] = conv.id
    request.session.modified = True
    return conv
@login_required(login_url='/login/')
def homepage(request):
    return render(request, 'index.html')

@login_required(login_url='/login/')
def histoire(request):
    return render(request, 'histoire.html')

@login_required(login_url='/login/')
def nous_connaitre(request):
    return render(request, 'nous_connaitre.html')

@login_required(login_url='/login/')
def presentation(request):
    return render(request, 'presentation.html')

def login(request):
    return render(request, 'login.html')

@login_required
def chat_page(request):
    """Main chat page with sidebar and conversation area."""
    conversations = Conversation.objects.filter(user=request.user)
    return render(request, 'chat_page.html', {'conversations': conversations})


@login_required
def get_conversation(request, conversation_id):
    conv = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    messages = [{'role': msg.role, 'content': msg.content} for msg in conv.messages.all()]
    return JsonResponse({'messages': messages})

@login_required
def new_conversation(request):
    conv = Conversation.objects.create(user=request.user, title="Nouvelle conversation")
    request.session['current_conversation_id'] = conv.id
    request.session.modified = True
    return JsonResponse({'conversation_id': conv.id})

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .models import Conversation, Message  # adjust to your actual models
@login_required
@require_POST
def delete_conversation(request, conversation_id):
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        # Delete the conversation (cascade will delete messages)
        conversation.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def ask(request):
    data = json.loads(request.body)
    question = data.get('question', '')
    conversation_id = data.get('conversation_id')
    
    if not question:
        return JsonResponse({'error': 'Empty question'}, status=400)
    
    # Determine which conversation to use
    if conversation_id:
        conv = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    else:
        conv = get_current_conversation(request)
    
    # Save user message
    Message.objects.create(conversation=conv, role='user', content=question)
    
    # Build history for RAG (only previous messages, not including the new user message? Actually include it)
    # We'll use all messages up to now (including the new user message) as history for context.
    # But the RAG expects history before answering. So we fetch all messages.
    history = [{'role': msg.role, 'content': msg.content} for msg in conv.messages.all()]
    # The last message is the current user question; that's fine.
    
    answer = rag.answer(question, history)
    
    # Save assistant message
    Message.objects.create(conversation=conv, role='assistant', content=answer)
    
    # Update title if it's the first exchange (user+assistant = 2 messages)
    if conv.messages.count() == 2:
        title = question[:50] + ('...' if len(question) > 50 else '')
        conv.title = title
        conv.save()
    
    # Ensure session has the correct current conversation id
    request.session['current_conversation_id'] = conv.id
    request.session.modified = True
    
    return JsonResponse({'answer': answer, 'conversation_id': conv.id})
import json
import pandas as pd
import os
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .recommendation_engine import FORBIDDEN_WORDS, SAFE_EXPLANATION, RecommendationEngine
from .models import RecommendationFeedback   # you must create this model

# Initialise the engine once
recommendation_engine = RecommendationEngine()

@login_required
@require_http_methods(["GET"])
def recommend_client(request, client_id):
    recs = recommendation_engine.recommend_for_client(client_id)
    if not recs:
        return JsonResponse({'error': f'Aucune recommandation pour le client {client_id}', 'recommendations': []}, status=200)
    if 'error' in recs[0]:
        return JsonResponse({'error': recs[0]['error'], 'recommendations': []}, status=200)
    # Return the full list as‑is (each item contains product_name, score, explanation, xai)
    return JsonResponse({'client_id': client_id, 'recommendations': recs})

@login_required
@require_http_methods(["GET"])
def client_info(request, client_id):
    client = recommendation_engine.get_client_profile(client_id)
    if not client:
        return JsonResponse({'error': 'Client not found'}, status=404)
    # Convert NaN to None for JSON serialization
    for k, v in client.items():
        if pd.isna(v):
            client[k] = None
    return JsonResponse(client)

@login_required
@require_http_methods(["GET"])
def search_client(request):
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'error': 'Missing query'}, status=400)
    df = recommendation_engine.clients_df
    df['client_id'] = df['client_id'].astype(str)
    mask = df['full_name'].str.contains(q, case=False, na=False) | df['client_id'].str.contains(q, case=False, na=False)
    matched = df[mask][['client_id', 'full_name', 'age', 'job_position', 'rfm_segment']].to_dict(orient='records')
    return JsonResponse({'results': matched})



@csrf_exempt
@require_http_methods(["POST"])
@login_required
def feedback(request):
    data = json.loads(request.body)
    client_id = data.get('client_id')
    product_name = data.get('product_name')
    rating = data.get('rating')       # 1 = 👍, 0 = 👎
    comment = data.get('comment', '')

    # Save the feedback
    RecommendationFeedback.objects.create(
        client_id=client_id,
        product_name=product_name,
        rating=rating,
        comment=comment
    )

    # Update product modifier based on last 30 days of feedback
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent = RecommendationFeedback.objects.filter(
        product_name=product_name,
        created_at__gte=thirty_days_ago
    )
    net = recent.filter(rating=1).count() - recent.filter(rating=0).count()
    # Modifier = net / 10 (range roughly -1 to +1)
    modifier = net / 10.0
    # Clamp between -2 and +2
    modifier = max(-2.0, min(2.0, modifier))

    obj, created = ProductScoreModifier.objects.update_or_create(
        product_name=product_name,
        defaults={'modifier': modifier}
    )

    return JsonResponse({'status': 'ok', 'modifier': modifier})
# If you have not yet created a template view for the recommendations page, add:
@login_required
def recommendations_page(request):
    return render(request, 'recommendations.html')