from django.urls import path
from core import views

urlpatterns = [
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

    path('department/', views.department, name='view_department'),
    path('department/add/', views.departmentForm, name='add_department'),
    path('department/<int:pk>/change/', views.departmentForm, name='change_department'),
    path('department/<int:pk>/delete/', views.departmentDelete, name='delete_department'),
    path('department/trashed/', views.departmentTrashed, name='trashed_department'),
    path('department/<int:pk>/restore/', views.departmentRestore, name='restore_department'),

    path('designation/', views.designation, name='view_designation'),
    path('designation/add/', views.designationForm, name='add_designation'),
    path('designation/<int:pk>/change/', views.designationForm, name='change_designation'),
    path('designation/<int:pk>/delete/', views.designationDelete, name='delete_designation'),
    path('designation/trashed/', views.designationTrashed, name='trashed_designation'),
    path('designation/<int:pk>/restore/', views.designationRestore, name='restore_designation'),

]