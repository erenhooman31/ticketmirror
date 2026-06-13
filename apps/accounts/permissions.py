from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from .models import UserProfile


def is_admin(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.role == UserProfile.Role.ADMIN)


def is_operator(user) -> bool:
    if not user.is_authenticated:
        return False
    profile = getattr(user, "profile", None)
    return bool(profile and profile.role == UserProfile.Role.OPERATOR)


def can_mutate(user) -> bool:
    return is_admin(user) or is_operator(user)


def can_view(user) -> bool:
    return user.is_authenticated


viewer_required = login_required


def operator_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not can_mutate(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


class ViewerRequiredMixin(LoginRequiredMixin):
    pass


class OperatorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_mutate(self.request.user)


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)
