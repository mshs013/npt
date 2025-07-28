from django.urls import path
from library import views

urlpatterns = [
    path('reason/', views.reason, name='view_nptreason'),
    path('reason/add/', views.reasonForm, name='add_nptreason'),
    path('reason/<int:pk>/change/', views.reasonForm, name='change_nptreason'),
    path('reason/<int:pk>/delete/', views.reasonDelete, name='delete_nptreason'),
]