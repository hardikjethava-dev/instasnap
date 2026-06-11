from django.urls import path
from downloader import views

app_name = 'downloader'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/fetch/', views.api_fetch, name='api_fetch'),
    path('api/status/<str:task_id>/', views.api_status, name='api_status'),
]
