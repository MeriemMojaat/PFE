from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('histoire/', views.histoire, name='histoire'),
    path('nous_connaitre/', views.nous_connaitre, name='nous_connaitre'),
    path('presentation/', views.presentation, name='presentation'),
    # Chat page
    path('chat/', views.chat_page, name='chat_page'),  
    path('ask/', views.ask, name='ask'),
    path('api/conversations/<int:conversation_id>/', views.get_conversation, name='get_conversation'),
    path('api/new_conversation/', views.new_conversation, name='new_conversation'),
    path('api/delete_conversation/<int:conversation_id>/', views.delete_conversation, name='delete_conversation'),
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Recommendation engine endpoints
    path('recommend/client/<str:client_id>/', views.recommend_client, name='recommend_client'),
    path('recommend/search/', views.search_client, name='search_client'),
    path('recommendations/', views.recommendations_page, name='recommendations'),
    path('recommend/client-info/<str:client_id>/', views.client_info, name='client_info'),
    path('api/feedback/', views.feedback, name='feedback')
    ]