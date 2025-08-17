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

    path('company/', views.company, name='view_company'),
    path('company/add/', views.companyForm, name='add_company'),
    path('company/<int:pk>/change/', views.companyForm, name='change_company'),
    path('company/<int:pk>/delete/', views.companyDelete, name='delete_company'),
    path('company/trashed/', views.companyTrashed, name='trashed_company'),
    path('company/<int:pk>/restore/', views.companyRestore, name='restore_company'),

    path('building/', views.building, name='view_building'),
    path('building/add/', views.buildingForm, name='add_building'),
    path('building/<int:pk>/change/', views.buildingForm, name='change_building'),
    path('building/<int:pk>/delete/', views.buildingDelete, name='delete_building'),
    path('building/trashed/', views.buildingTrashed, name='trashed_building'),
    path('building/<int:pk>/restore/', views.buildingRestore, name='restore_building'),

    path('floor/', views.floor, name='view_floor'),
    path('floor/add/', views.floorForm, name='add_floor'),
    path('floor/<int:pk>/change/', views.floorForm, name='change_floor'),
    path('floor/<int:pk>/delete/', views.floorDelete, name='delete_floor'),
    path('floor/trashed/', views.floorTrashed, name='trashed_floor'),
    path('floor/<int:pk>/restore/', views.floorRestore, name='restore_floor'),

    path('block/', views.block, name='view_block'),
    path('block/add/', views.blockForm, name='add_block'),
    path('block/<int:pk>/change/', views.blockForm, name='change_block'),
    path('block/<int:pk>/delete/', views.blockDelete, name='delete_block'),
    path('block/trashed/', views.blockTrashed, name='trashed_block'),
    path('block/<int:pk>/restore/', views.blockRestore, name='restore_block'),

    path('machinetype/', views.machinetype, name='view_machinetype'),
    path('machinetype/add/', views.machinetypeForm, name='add_machinetype'),
    path('machinetype/<int:pk>/change/', views.machinetypeForm, name='change_machinetype'),
    path('machinetype/<int:pk>/delete/', views.machinetypeDelete, name='delete_machinetype'),
    path('machinetype/trashed/', views.machinetypeTrashed, name='trashed_machinetype'),
    path('machinetype/<int:pk>/restore/', views.machinetypeRestore, name='restore_machinetype'),

    path('shift/', views.shift, name='view_shift'),
    path('shift/add/', views.shiftForm, name='add_shift'),
    path('shift/<int:pk>/change/', views.shiftForm, name='change_shift'),
    path('shift/<int:pk>/delete/', views.shiftDelete, name='delete_shift'),
    path('shift/trashed/', views.shiftTrashed, name='trashed_shift'),
    path('shift/<int:pk>/restore/', views.shiftRestore, name='restore_shift'),
]