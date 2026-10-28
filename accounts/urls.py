from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (
    ThrottledLoginView,
    UserCreateView,
    UserDeleteView,
    UserListView,
    UserPasswordResetView,
    UserUpdateView,
)

urlpatterns = [
    path("login/", ThrottledLoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("usuarios/", UserListView.as_view(), name="user_list"),
    path("usuarios/novo/", UserCreateView.as_view(), name="user_create"),
    path("usuarios/<int:pk>/editar/", UserUpdateView.as_view(), name="user_update"),
    path("usuarios/<int:pk>/senha/", UserPasswordResetView.as_view(), name="user_password_reset"),
    path("usuarios/<int:pk>/excluir/", UserDeleteView.as_view(), name="user_delete"),
]
