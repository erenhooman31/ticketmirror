import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import UserProfile


class Command(BaseCommand):
    help = "Create an initial superuser from env vars if one does not exist."

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")

        if not username or not password:
            self.stdout.write(
                "Skipping initial admin creation; "
                "DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD are not set."
            )
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            user.profile.role = UserProfile.Role.ADMIN
            user.profile.save(update_fields=["role", "updated_at"])
            self.stdout.write(self.style.SUCCESS(f"Created admin user {username}."))
            return

        changed_fields = []
        if not user.is_staff:
            user.is_staff = True
            changed_fields.append("is_staff")
        if not user.is_superuser:
            user.is_superuser = True
            changed_fields.append("is_superuser")
        if email and user.email != email:
            user.email = email
            changed_fields.append("email")
        if changed_fields:
            user.save(update_fields=changed_fields)
        if user.profile.role != UserProfile.Role.ADMIN:
            user.profile.role = UserProfile.Role.ADMIN
            user.profile.save(update_fields=["role", "updated_at"])
        self.stdout.write(f"Admin user {username} already exists.")
