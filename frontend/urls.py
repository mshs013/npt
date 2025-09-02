from django.urls import path
from frontend import views

urlpatterns = [
    path('', views.dashboard, name='home'),
    
    ### Mclogs
    path('mclogs/', views.mclogs, name='view_mclog'),

    ### Mcgraph
    path('mcgraph/', views.mcgraph, name='view_mcgraph'),
    path('api/mcgraph/', views.mcgraph_api, name='mcgraph_api'),

    ### Rotation Counter
    path('rotation_counter/', views.rotaionCounter, name='view_rotationcounter'),
    # path('download-rotation-excel/', views.download_rotation_excel, name='download_rotation_excel'),

    ### Report Daily-Performance
    path('daily_performance/', views.daily_performance, name='view_dailyperformance'),
    # path('api/daily_performance/', views.daily_performance_api, name='dailyperformance_api'),

    ### Report Overll-Performance
    path('overall_performance/', views.overall_performance, name='view_overallperformance'),

    ### Report Machine-Analysis
    # path('overall_performance/', views.overall_performance, name='view_overallperformance'),
]