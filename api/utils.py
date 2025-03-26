# utils.py
from django.contrib.auth.tokens import PasswordResetTokenGenerator

class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # No need for six.text_type; just use str() directly in Python 3
        return (
            str(user.pk) + str(timestamp) + str(user.is_verified)
        )

account_activation_token = EmailVerificationTokenGenerator()