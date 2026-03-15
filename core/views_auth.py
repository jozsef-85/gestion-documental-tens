from django.conf import settings
from django.contrib.auth.views import LoginView
from django.core.cache import cache

from .services.helpers import obtener_ip_cliente


class RateLimitedLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_attempt_limit(self):
        return settings.LOGIN_RATE_LIMIT_ATTEMPTS

    def get_rate_limit_window(self):
        return settings.LOGIN_RATE_LIMIT_WINDOW

    def get_rate_limit_message(self):
        minutos = max(1, self.get_rate_limit_window() // 60)
        return (
            'Demasiados intentos de acceso fallidos. '
            f'Espera {minutos} minuto(s) antes de volver a intentarlo.'
        )

    def get_identifiers(self):
        ip = obtener_ip_cliente(self.request) or 'unknown'
        username = self.request.POST.get('username', '').strip().lower()
        return ip, username

    def get_cache_keys(self, ip, username):
        keys = [f'auth:login:ip:{ip}']
        if username:
            keys.append(f'auth:login:ip_user:{ip}:{username}')
        return keys

    def is_rate_limited(self, ip, username):
        return any(
            int(cache.get(key, 0)) >= self.get_attempt_limit()
            for key in self.get_cache_keys(ip, username)
        )

    def register_failure(self, ip, username):
        timeout = self.get_rate_limit_window()
        for key in self.get_cache_keys(ip, username):
            cache.set(key, int(cache.get(key, 0)) + 1, timeout=timeout)

    def reset_failures(self, ip, username):
        cache.delete_many(self.get_cache_keys(ip, username))

    def post(self, request, *args, **kwargs):
        ip, username = self.get_identifiers()
        form = self.get_form()

        if self.is_rate_limited(ip, username):
            form.add_error(None, self.get_rate_limit_message())
            return self.render_to_response(self.get_context_data(form=form))

        if form.is_valid():
            self.reset_failures(ip, username)
            return self.form_valid(form)

        self.register_failure(ip, username)
        if self.is_rate_limited(ip, username):
            form.add_error(None, self.get_rate_limit_message())
        return self.form_invalid(form)
