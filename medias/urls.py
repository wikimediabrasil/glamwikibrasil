from django.urls import path
from medias import views

app_name = "medias"

urlpatterns = [
    path('glams/<str:pk>/report', views.return_report, name='glam_report'),
    path('glams/<str:pk>/report/<str:timestamp>', views.return_report_for_month, name='glam_report_for_month'),
    path('glams/<str:pk>/medias', views.update_glam_mediafiles, name='glam_medias'),
    path('all_glams', views.all_glams_report, name='all_glams'),
    path('top_files', views.top_files_report, name='top_files'),
    path('glams/<str:pk>/requests/<str:start>/<str:end>', views.update_glam_mediafiles_requests, name='glam_requests_specific'),
    path('glams/<str:pk>/requests/<str:start>', views.update_glam_mediafiles_requests, name='glam_requests_since'),
    path('glams/<str:pk>/requests', views.update_glam_mediafiles_requests, name='glam_requests_all'),
    path('glams/<str:pk>/usage', views.update_glam_mediafiles_usage, name='glam_usage'),
    path('api/index-data', views.get_index_counter_data, name="index-data"),
    path('update_all', views.update_all_glams_from_start, name="update_all"),
]
