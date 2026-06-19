from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('generate-data/', views.generate_data, name='generate_data'),
    path('analysis/', views.analysis, name='analysis'),
    path('segment-trend/', views.segment_trend, name='segment_trend'),
    path('segment-adoption/', views.segment_adoption, name='segment_adoption'),
    path('recommendations/', views.get_recommendations, name='recommendations'),
    path('report/pdf/', views.generate_pdf_report, name='pdf_report'),
]