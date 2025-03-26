import os
import django

# Ensure Django settings are loaded correctly
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coding_platform.settings')  # Update with your project name
django.setup()

from django.conf import settings
from django.core.mail import send_mail

# Verify if settings are loaded correctly
if not settings.configured:
    raise RuntimeError("Django settings are not configured correctly.")

# Test email parameters
subject = 'Test Gmail SMTP'
message = 'This is a test email sent via Gmail SMTP.'
from_email = settings.DEFAULT_FROM_EMAIL  # Ensure this is set in settings.py
recipient_list = ['adityauttarwar29@gmail.com']

try:
    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
        fail_silently=False,
    )
    print("✅ Email sent successfully!")
except Exception as e:
    print(f"❌ Failed to send email: {str(e)}")
