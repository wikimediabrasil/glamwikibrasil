from django.urls import path
from glams import views

app_name = "glams"

urlpatterns = [
    path('', views.index, name='index'),
    path('institutions/list', views.institution_list, name='institution_list'),
    path('institutions/create', views.institution_create, name='institution_create'),
    path('institutions/<str:pk>', views.institution_detail, name='institution_detail'),
    path('institutions/<str:pk>/delete', views.institution_delete, name='institution_delete'),
    path('institutions/<str:pk>/update', views.institution_update, name='institution_update'),
    path('glams/list', views.glam_list, name='glam_list'),
    path('glams/create', views.glam_create, name='glam_create'),
    path('glams/<str:pk>', views.glam_detail, name='glam_detail'),
    path('glams/<str:pk>/delete', views.glam_delete, name='glam_delete'),
    path('glams/<str:pk>/update', views.glam_update, name='glam_update'),
]
