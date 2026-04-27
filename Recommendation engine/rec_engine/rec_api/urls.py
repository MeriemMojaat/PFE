from django.urls import path
from . import views

urlpatterns = [
    path('recommend/<str:client_id>/', views.recommend, name='recommend'),
    path('recommend-by-name/<str:name>/', views.recommend_by_name, name='recommend_by_name'),
]