from django.urls import path
from library import views

urlpatterns = [
    ### Shift
    path('shift/', views.shift, name='view_shift'),
    path('shift/add/', views.shiftForm, name='add_shift'),
    path('shift/<int:pk>/change/', views.shiftForm, name='change_shift'),
    path('shift/<int:pk>/delete/', views.shiftDelete, name='delete_shift'),
    path('shift/trashed/', views.shiftTrashed, name='trashed_shift'),
    path('shift/<int:pk>/restore/', views.shiftRestore, name='restore_shift'),
]