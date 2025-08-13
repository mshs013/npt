from django.urls import path
from library import views

urlpatterns = [
    path('reason/', views.reason, name='view_nptreason'),
    path('reason/add/', views.reasonForm, name='add_nptreason'),
    path('reason/<int:pk>/change/', views.reasonForm, name='change_nptreason'),
    path('reason/<int:pk>/delete/', views.reasonDelete, name='delete_nptreason'),
    path('reason/trashed/', views.reasonTrashed, name='trashed_nptreason'),
    path('reason/<int:pk>/restore/', views.reasonRestore, name='restore_nptreason'),
    path('npt/', views.npt, name='view_processednpt'),
    path('rotation/', views.rotation, name='view_rotationstatus'),
]