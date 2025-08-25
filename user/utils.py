



# user/utils.py
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.conf import settings
from .models import EmailOTP
import logging

logger = logging.getLogger(__name__)

def generate_and_send_otp(email):
    otp = get_random_string(length=6, allowed_chars='0123456789')
    logger.debug(f"Generated OTP for {email}: {otp}")

    # Store or update OTP for this email with new timestamp
    EmailOTP.objects.update_or_create(
        email=email,
        defaults={'otp': otp, 'created_at': timezone.now()}
    )
    logger.debug(f"OTP stored in EmailOTP for {email}")

    # Send email with OTP
    try:
        send_mail(
            subject="Verify your new email",
            message=f"Your OTP is {otp}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.debug(f"OTP email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        raise