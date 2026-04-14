"""
OTP utilities for password reset functionality
"""

import random
import string
import logging
from datetime import timedelta

from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import PasswordResetOTP

logger = logging.getLogger(__name__)


def generate_otp(length=6):
    """Generate a random OTP of specified length"""
    return ''.join(random.choices(string.digits, k=length))


def send_otp_email(email, otp):
    """Send OTP email with timeout and better error handling"""
    subject = "PaperAIzer - Password Reset OTP"
    message = f"""
Hello,

Your One-Time Password (OTP) for resetting your PaperAIzer password is:

🔑 {otp}

This OTP is valid for 10 minutes. Please do not share this code with anyone.

If you didn't request a password reset, please ignore this email.

Best regards,
PaperAIzer Team
"""

    try:
        logger.info(f"Attempting to send OTP email to {email}")

        from_email = settings.DEFAULT_FROM_EMAIL

        # Use EMAIL_TIMEOUT from settings (we added it earlier)
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[email],
            fail_silently=False,
            # timeout is controlled by EMAIL_TIMEOUT in settings.py
        )

        logger.info(f"✅ OTP email sent successfully to {email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send OTP email to {email}: {str(e)}", exc_info=True)
        return False


def create_and_send_otp(email):
    """Create OTP and send email with safe handling"""
    try:
        # Prevent spam: Check for existing valid OTP
        existing = PasswordResetOTP.objects.filter(
            email=email, 
            is_used=False, 
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()

        if existing:
            otp = existing.otp
            reset_otp = existing
        else:
            # Clean old OTPs
            PasswordResetOTP.objects.filter(email=email, is_used=False).delete()

            otp = generate_otp()

            expires_at = timezone.now() + timedelta(minutes=10)

            reset_otp = PasswordResetOTP.objects.create(
                email=email,
                otp=otp,
                expires_at=expires_at
            )

        # FOR DEVELOPMENT: Print OTP in logs/console
        print(f"\n{'='*50}")
        print(f"🔑 OTP FOR {email} IS: {otp}")
        print(f"{'='*50}\n")

        logger.info(f"Generated OTP for {email}")

        # Send the email
        email_sent = send_otp_email(email, otp)

        return reset_otp, email_sent

    except Exception as e:
        logger.error(f"Error in create_and_send_otp for {email}: {str(e)}", exc_info=True)
        return None, False


def verify_otp(email, otp):
    """Verify OTP"""
    try:
        reset_otp = PasswordResetOTP.objects.get(email=email, otp=otp)
        
        if reset_otp.is_valid():
            return True, reset_otp
        else:
            return False, None
    except PasswordResetOTP.DoesNotExist:
        return False, None


def mark_otp_as_used(email, otp):
    """Mark OTP as used"""
    try:
        reset_otp = PasswordResetOTP.objects.get(email=email, otp=otp)
        reset_otp.is_used = True
        reset_otp.save()
        return True
    except PasswordResetOTP.DoesNotExist:
        return False