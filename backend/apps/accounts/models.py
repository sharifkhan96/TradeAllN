from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class EmailUserManager(UserManager):
    def _create_user(self, username, email, password, **extra):
        email = self.normalize_email(email)
        user = self.model(username=email, email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, email, password, **extra)

    def create_superuser(self, email=None, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, email, password, **extra)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=60, blank=True)
    timezone = models.CharField(max_length=64, default="America/New_York")
    ai_enabled = models.BooleanField(default=True)
    rules_paused = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = EmailUserManager()

    def __str__(self):
        return self.email

    @property
    def name(self):
        return self.display_name or self.email.split("@")[0]
