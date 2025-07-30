from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import get_user_model
import random
from django.utils import timezone
from datetime import timedelta


class CustomUser(AbstractUser):
    phone = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    profile_image = models.ImageField(
        upload_to='profile_images/', blank=True, null=True)

    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username
    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()


User = get_user_model()


class EmailOTP(models.Model):
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_otp(self):
        self.otp = str(random.randint(100000, 999999))
        self.created_at = timezone.now()  # update timestamp on new OTP
        self.save()

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)

    def __str__(self):
        return f"{self.email} - {self.otp}"


class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return self.user.username
class Address(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address_line = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.city}"
