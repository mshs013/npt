from django.urls import path
from core import views

urlpatterns = [
    path("switch-company/", views.switch_company, name="switch_company"),

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

    ### Department
    path('department/', views.department, name='view_department'),
    path('department/add/', views.departmentForm, name='add_department'),
    path('department/<int:pk>/change/', views.departmentForm, name='change_department'),
    path('department/<int:pk>/delete/', views.departmentDelete, name='delete_department'),
    path('department/trashed/', views.departmentTrashed, name='trashed_department'),
    path('department/<int:pk>/restore/', views.departmentRestore, name='restore_department'),

    ### Designation
    path('designation/', views.designation, name='view_designation'),
    path('designation/add/', views.designationForm, name='add_designation'),
    path('designation/<int:pk>/change/', views.designationForm, name='change_designation'),
    path('designation/<int:pk>/delete/', views.designationDelete, name='delete_designation'),
    path('designation/trashed/', views.designationTrashed, name='trashed_designation'),
    path('designation/<int:pk>/restore/', views.designationRestore, name='restore_designation'),

    ### NPTReason
    path('reason/', views.reason, name='view_nptreason'),
    path('reason/add/', views.reasonForm, name='add_nptreason'),
    path('reason/<int:pk>/change/', views.reasonForm, name='change_nptreason'),
    path('reason/<int:pk>/delete/', views.reasonDelete, name='delete_nptreason'),
    path('reason/trashed/', views.reasonTrashed, name='trashed_nptreason'),
    path('reason/<int:pk>/restore/', views.reasonRestore, name='restore_nptreason'),
    path('npt/', views.npt, name='view_processednpt'),
    path('rotation/', views.rotation, name='view_rotationstatus'),
    
    ### Brand
    path('brand/', views.brand, name='view_brand'),
    path('brand/add/', views.brandForm, name='add_brand'),
    path('brand/<int:pk>/change/', views.brandForm, name='change_brand'),
    path('brand/<int:pk>/delete/', views.brandDelete, name='delete_brand'),
    path('brand/trashed/', views.brandTrashed, name='trashed_brand'),
    path('brand/<int:pk>/restore/', views.brandRestore, name='restore_brand'),

    ### Company
    path('company/', views.company, name='view_company'),
    path('company/add/', views.companyForm, name='add_company'),
    path('company/<int:pk>/change/', views.companyForm, name='change_company'),
    path('company/<int:pk>/delete/', views.companyDelete, name='delete_company'),
    path('company/trashed/', views.companyTrashed, name='trashed_company'),
    path('company/<int:pk>/restore/', views.companyRestore, name='restore_company'),

    ### Building
    path('building/', views.building, name='view_building'),
    path('building/add/', views.buildingForm, name='add_building'),
    path('building/<int:pk>/change/', views.buildingForm, name='change_building'),
    path('building/<int:pk>/delete/', views.buildingDelete, name='delete_building'),
    path('building/trashed/', views.buildingTrashed, name='trashed_building'),
    path('building/<int:pk>/restore/', views.buildingRestore, name='restore_building'),

    ### Floor
    path('floor/', views.floor, name='view_floor'),
    path('floor/add/', views.floorForm, name='add_floor'),
    path('floor/<int:pk>/change/', views.floorForm, name='change_floor'),
    path('floor/<int:pk>/delete/', views.floorDelete, name='delete_floor'),
    path('floor/trashed/', views.floorTrashed, name='trashed_floor'),
    path('floor/<int:pk>/restore/', views.floorRestore, name='restore_floor'),

    ### Block
    path('block/', views.block, name='view_block'),
    path('block/add/', views.blockForm, name='add_block'),
    path('block/<int:pk>/change/', views.blockForm, name='change_block'),
    path('block/<int:pk>/delete/', views.blockDelete, name='delete_block'),
    path('block/trashed/', views.blockTrashed, name='trashed_block'),
    path('block/<int:pk>/restore/', views.blockRestore, name='restore_block'),

    ### Machine Type
    path('machinetype/', views.machinetype, name='view_machinetype'),
    path('machinetype/add/', views.machinetypeForm, name='add_machinetype'),
    path('machinetype/<int:pk>/change/', views.machinetypeForm, name='change_machinetype'),
    path('machinetype/<int:pk>/delete/', views.machinetypeDelete, name='delete_machinetype'),
    path('machinetype/trashed/', views.machinetypeTrashed, name='trashed_machinetype'),
    path('machinetype/<int:pk>/restore/', views.machinetypeRestore, name='restore_machinetype'),

    ### machine ###
    path('machine/', views.machine, name='view_machine'),
    path('machine/add/', views.machineForm, name='add_machine'),
    path('machine/<int:pk>/change/', views.machineForm, name='change_machine'),
    path('machine/<int:pk>/delete/', views.machineDelete, name='delete_machine'),
    path('machine/trashed/', views.machineTrashed, name='trashed_machine'),
    path('machine/<int:pk>/restore/', views.machineRestore, name='restore_machine'),
]