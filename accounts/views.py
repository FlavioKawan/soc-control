from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.views.generic.edit import FormView

from .forms import PlatformUserCreateForm, PlatformUserPasswordResetForm, PlatformUserUpdateForm

MAX_LOGIN_ATTEMPTS = 10
THROTTLE_WINDOW_SECONDS = 15 * 60


def _client_ip(request):
    # Nginx (docker/nginx/nginx.conf) always sets this; REMOTE_ADDR alone
    # would just be the "web" container's IP as seen from the proxy hop.
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR") or "unknown"


class ThrottledLoginView(LoginView):
    """
    Blocks further login attempts from an IP after too many failures in a
    row, instead of allowing unlimited password guesses. Throttles by IP
    (not by username) so an attacker can't lock a real admin out just by
    spamming their username with wrong passwords.
    """

    def _cache_key(self, request):
        return f"login-attempts:{_client_ip(request)}"

    def post(self, request, *args, **kwargs):
        if cache.get(self._cache_key(request), 0) >= MAX_LOGIN_ATTEMPTS:
            messages.error(
                request,
                "Muitas tentativas de login a partir deste endereço. "
                "Aguarde alguns minutos antes de tentar novamente.",
            )
            return self.get(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._cache_key(self.request)
        cache.set(key, cache.get(key, 0) + 1, THROTTLE_WINDOW_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._cache_key(self.request))
        return super().form_valid(form)


class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    permission_required = "auth.view_user"
    template_name = "accounts/user_list.html"
    context_object_name = "platform_users"
    paginate_by = 25

    def get_queryset(self):
        return User.objects.order_by("username").prefetch_related("groups")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add"] = self.request.user.has_perm("auth.add_user")
        ctx["can_change"] = self.request.user.has_perm("auth.change_user")
        ctx["can_delete"] = self.request.user.has_perm("auth.delete_user")
        return ctx


class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = User
    form_class = PlatformUserCreateForm
    permission_required = "auth.add_user"
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("user_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Usuário "{self.object.username}" criado com sucesso.')
        return response


class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = User
    form_class = PlatformUserUpdateForm
    permission_required = "auth.change_user"
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("user_list")

    def form_valid(self, form):
        # Deactivating your own account through this screen would lock you
        # out with no way back in short of another ADMIN or /admin/ access.
        if self.object == self.request.user and not form.cleaned_data["is_active"]:
            form.add_error("is_active", "Você não pode desativar sua própria conta.")
            return self.form_invalid(form)
        response = super().form_valid(form)
        messages.success(self.request, f'Usuário "{self.object.username}" atualizado com sucesso.')
        return response


class UserPasswordResetView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    form_class = PlatformUserPasswordResetForm
    permission_required = "auth.change_user"
    template_name = "accounts/user_password_form.html"
    success_url = reverse_lazy("user_list")

    def dispatch(self, request, *args, **kwargs):
        self.target_user = get_object_or_404(User, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.target_user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["target_user"] = self.target_user
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, f'Senha de "{self.target_user.username}" redefinida com sucesso.')
        return super().form_valid(form)


class UserDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = User
    permission_required = "auth.delete_user"
    template_name = "accounts/user_confirm_delete.html"
    success_url = reverse_lazy("user_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object == request.user:
            messages.error(request, "Você não pode excluir sua própria conta.")
            return redirect("user_list")
        return super().post(request, *args, **kwargs)
