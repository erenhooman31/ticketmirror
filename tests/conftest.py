import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
os.environ.setdefault("DJANGO_DEBUG", "false")
