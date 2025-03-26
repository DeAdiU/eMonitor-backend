from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
import logging
from .models import User, PlatformProfile, MentorStudentMapping
from .permissions import IsStudent, IsMentor


User = get_user_model()
logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'confirm_password', 'role', 'enrollment_year', 
                 'graduation_year', 'date_of_birth', 'phone_number', 'is_verified']
        extra_kwargs = {
            'password': {'write_only': True},
            'id': {'read_only': True},
            'is_verified': {'read_only': True}
        }

    def validate(self, data):
        # Password confirmation validation
        if 'password' in data and 'confirm_password' in data:
            if data['password'] != data['confirm_password']:
                raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
            data.pop('confirm_password')
        return data

    def create(self, validated_data):
        # Create the user
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data['role'],
            enrollment_year=validated_data.get('enrollment_year'),
            graduation_year=validated_data.get('graduation_year'),
            date_of_birth=validated_data.get('date_of_birth'),
            phone_number=validated_data.get('phone_number'),
            is_verified=False
        )

        # Generate verification token and URL
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        verification_url = f"{settings.FRONTEND_URL}/verify-email/?uid={uid}&token={token}/"

        # Send verification email
        try:
            send_mail(
                'Verify Your Email Address',
                f'Hello {user.username},\n\n'
                f'Please click this link to verify your email:\n{verification_url}\n\n'
                f'This link will expire in 24 hours.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            print(verification_url)
            logger.info(f"Verification email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
            user.delete()
            raise serializers.ValidationError(f"Failed to send verification email: {str(e)}")

        return user

    def update(self, instance, validated_data):
        # Update username
        instance.username = validated_data.get('username', instance.username)

        # Handle email change with new verification
        if 'email' in validated_data and validated_data['email'] != instance.email:
            instance.email = validated_data['email']
            instance.is_verified = False
            
            # Generate new verification token
            token = default_token_generator.make_token(instance)
            uid = urlsafe_base64_encode(force_bytes(instance.pk))
            verification_url = f"/verify-email/?uid={uid}&token={token}"
            
            # Send verification email
            try:
                send_mail(
                    'Verify Your New Email Address',
                    f'Please verify your new email:\n{verification_url}',
                    settings.DEFAULT_FROM_EMAIL,
                    [instance.email],
                    fail_silently=False,
                )
                logger.info(f"Verification email sent to {instance.email}")
            except Exception as e:
                logger.error(f"Failed to send verification email to {instance.email}: {str(e)}")
                raise serializers.ValidationError(f"Failed to send verification email: {str(e)}")

        # Update password if provided
        if 'password' in validated_data:
            instance.set_password(validated_data['password'])

        # Update other fields
        instance.enrollment_year = validated_data.get('enrollment_year', instance.enrollment_year)
        instance.graduation_year = validated_data.get('graduation_year', instance.graduation_year)
        instance.date_of_birth = validated_data.get('date_of_birth', instance.date_of_birth)
        instance.phone_number = validated_data.get('phone_number', instance.phone_number)

        instance.save()
        return instance

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, email):
        # Check if email exists in the system
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address.")
        return email

    def send_password_reset_email(self, validated_data):
        try:
            user = User.objects.get(email=validated_data['email'])
            
            # Generate password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

            # Send password reset email
            send_mail(
                'Password Reset Request',
                f'Hello {user.username},\n\n'
                f'Please click this link to reset your password:\n{reset_url}\n\n'
                f'This link will expire in 1 hour.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Password reset email sent to {user.email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            raise serializers.ValidationError(f"Failed to send password reset email: {str(e)}")

class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        # Validate passwords match
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})

        # Validate UID and token
        try:
            uid = force_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError("Invalid reset link")

        # Validate token
        if not default_token_generator.check_token(user, data['token']):
            raise serializers.ValidationError("Invalid or expired reset link")

        return data

    def reset_password(self, validated_data):
        try:
            uid = force_str(urlsafe_base64_decode(validated_data['uid']))
            user = User.objects.get(pk=uid)
            
            # Set new password
            user.set_password(validated_data['new_password'])
            user.save()
            
            logger.info(f"Password reset successful for user {user.email}")
            return user
        except Exception as e:
            logger.error(f"Password reset failed: {str(e)}")
            raise serializers.ValidationError("Password reset failed")

class PlatformProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformProfile
        fields = ['id', 'user', 'platform', 'profile_id', 'is_verified']
        read_only_fields = ['id', 'user', 'is_verified']

class MentorStudentMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorStudentMapping
        fields = ['id', 'mentor', 'student']