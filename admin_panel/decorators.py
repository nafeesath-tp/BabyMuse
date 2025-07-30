from django.shortcuts import redirect
from functools import wraps


def admin_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'admin_id' not in request.session:
            return redirect('admin_panel:custom_admin_login')
        return view_func(request, *args, **kwargs)
    return wrapper
