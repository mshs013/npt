from django.urls import path
from core import views

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('camera-stream/', views.camera_stream, name='camera_stream'),
    path('menu/', views.menu, name='view_menu'),
    path('menu/add/', views.menuForm, name='add_menu'),
    path('menu/<int:pk>/change/', views.menuForm, name='change_menu'),
    path('menu/<int:pk>/delete/', views.menuDelete, name='delete_menu'),
    path('activitylog/', views.activitylog, name='view_activitylog'),
    path('activitylog/<int:pk>/', views.activitylogDetail, name='detail_activitylog'),
    path('user/', views.user, name='view_user'),
    path('user/add/', views.userForm, name='add_user'),
    path('user/<int:pk>/change/', views.userForm, name='change_user'),
    path('user/<int:pk>/delete/', views.userDelete, name='delete_user'),
]