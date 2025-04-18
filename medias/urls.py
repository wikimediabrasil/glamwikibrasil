from django.urls import path
from medias import views

app_name = "medias"

urlpatterns = [
    path('glams/<str:pk>/report', views.return_report, name='glam_report'),
    path('glams/<str:pk>/report/<str:timestamp>', views.return_report_for_month, name='glam_report_for_month'),
    path('glams/<str:pk>/status/<str:timestamp>', views.return_status, name='glam_status'),
    path('glams/<str:pk>/medias', views.update_glam_mediafiles, name='glam_medias'),
    path('glams/<str:pk>/requests/<str:start>/<str:end>', views.update_glam_mediafiles_requests, name='glam_requests_specific'),
    path('glams/<str:pk>/requests/<str:start>', views.update_glam_mediafiles_requests, name='glam_requests_since'),
    path('glams/<str:pk>/requests', views.update_glam_mediafiles_requests, name='glam_requests_all'),
    path('glams/<str:pk>/usage', views.update_glam_mediafiles_usage, name='glam_usage'),
]
