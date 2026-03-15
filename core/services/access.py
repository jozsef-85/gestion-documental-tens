from functools import wraps

from django.core.exceptions import PermissionDenied


def any_permission_required(*perms):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser or any(request.user.has_perm(perm) for perm in perms):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied

        return _wrapped_view

    return decorator


def model_access_required(app_label, model_name):
    model_name = model_name.lower()
    perms = [
        f'{app_label}.view_{model_name}',
        f'{app_label}.add_{model_name}',
        f'{app_label}.change_{model_name}',
        f'{app_label}.delete_{model_name}',
    ]
    return any_permission_required(*perms)
