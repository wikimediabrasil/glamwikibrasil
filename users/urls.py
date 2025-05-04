from django.urls import path, include
from users import views

app_name = "users"

urlpatterns = [
    path('accounts/login', views.login_oauth, name='login'),
    path('oauth/', include('social_django.urls', namespace='social')),
    path('logout', views.logout_oauth, name='logout'),
    path('login/', views.permission_denied, name='login'),
]
