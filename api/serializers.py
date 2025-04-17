from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
import logging
from .models import *
from .permissions import *
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()
logger = logging.getLogger(__name__)

class BasicUserSerializer(serializers.ModelSerializer):
    """Minimal user info"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    class Meta:
        model = User
        fields = ('id', 'username', 'full_name', 'role')

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        # Check if user is verified (Assuming you have a 'is_verified' field in User model)
        if not self.user.is_verified:
            raise AuthenticationFailed("Your account is not verified.")

        return data

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name','password', 'role', 'enrollment_year', 
                 'graduation_year', 'date_of_birth', 'phone_number', 'is_verified']
        extra_kwargs = {
            'password': {'write_only': True},
            'id': {'read_only': True},
            'is_verified': {'read_only': True}
        }

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

class QuestionSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    class Meta:
        model = Question
        fields = (
            'id', 'assessment', 'assessment_title', 'contest_id', 'problem_index',
            'title', 'link', 'tags', 'rating', 'points',
            # 'evaluation_criteria_override' # Include if using this field
        )
        read_only_fields = ('assessment', 'assessment_title', 'title', 'link', 'tags', 'rating') # Fetched/derived fields

    # Optional: Add validation for contest_id/problem_index if needed
    # def validate(self, data): ...

# serializers.py (in your app, e.g., 'assessments/serializers.py')

from rest_framework import serializers
from django.db.models import Count, Q, Prefetch # Import Prefetch
from .models import Assessment, AssessmentSubmission, User

class MentorAssignmentListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing assignments created by a mentor, including
    submission progress counts.
    """
    # Use SerializerMethodField to calculate counts dynamically
    total_assigned_students = serializers.SerializerMethodField()
    submitted_students_count = serializers.SerializerMethodField()
    deadline = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True) # Format deadline

    class Meta:
        model = Assessment
        fields = [
            'id',
            'title',
            'description',
            'deadline',
            'created_at',
            'preferred_criteria',
            'total_assigned_students', # Added field
            'submitted_students_count', # Added field
            # Add other fields you want in the list view
        ]
        read_only_fields = fields # Make all fields read-only for this list view

    def get_total_assigned_students(self, obj):
        """
        Returns the total number of students assigned to this assessment.
        Uses prefetched data if available.
        """
        # Check if 'assigned_students' was prefetched
        if hasattr(obj, 'assigned_students_count_annotation'):
             return obj.assigned_students_count_annotation # Use annotated value
        # Fallback if not annotated (less efficient)
        return obj.assigned_students.count()


    def get_submitted_students_count(self, obj):
        """
        Returns the count of unique students who have at least one 'OK'
        submission for this assessment. Uses prefetched data if available.
        """
         # Check if 'successful_submission_students_count_annotation' was prefetched/annotated
        if hasattr(obj, 'successful_submission_students_count_annotation'):
            return obj.successful_submission_students_count_annotation # Use annotated value

        # Fallback if not annotated (less efficient)
        # Count distinct students who have a submission for this assessment
        # with status EVALUATED and verdict OK.
        return AssessmentSubmission.objects.filter(
            assessment=obj,
            status=AssessmentSubmission.STATUS_CHOICES[2][0], # 'EVALUATED'
            codeforces_verdict='OK'
        ).values('student').distinct().count()

class AssessmentSubmissionSerializer(serializers.ModelSerializer):
    student = BasicUserSerializer(read_only=True)
    question_display = serializers.SerializerMethodField() # Combine contest/index/title
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)

    class Meta:
        model = AssessmentSubmission
        fields = (
            'id', 'student', 'question', 'question_display', 'assessment', 'assessment_title',
            'status', 'evaluation_score', 'evaluation_feedback',
            'codeforces_verdict', 'codeforces_submission_id',
            'codeforces_passed_test_count', 'codeforces_time_consumed_millis',
            'codeforces_memory_consumed_bytes', 'solved_at', 'last_checked_at'
        )
        read_only_fields = ( # Most fields are updated by the backend scheduler
            'id', 'student', 'question', 'question_display', 'assessment', 'assessment_title',
            'status', 'evaluation_score', 'evaluation_feedback',
            'codeforces_verdict', 'codeforces_submission_id',
            'codeforces_passed_test_count', 'codeforces_time_consumed_millis',
            'codeforces_memory_consumed_bytes', 'solved_at', 'last_checked_at'
        )

    def get_question_display(self, obj):
        q = obj.question
        title = q.title if q.title else f"Problem {q.contest_id}{q.problem_index}"
        return f"{title} (Rating: {q.rating or 'N/A'})"


class AssessmentListSerializer(serializers.ModelSerializer):
    """Serializer for listing assessments"""
    mentor = BasicUserSerializer(read_only=True)
    question_count = serializers.IntegerField(source='questions.count', read_only=True)
    assigned_student_count = serializers.IntegerField(source='assigned_students.count', read_only=True)
    is_past_deadline = serializers.BooleanField(read_only=True)

    class Meta:
        model = Assessment
        fields = (
            'id', 'title', 'mentor', 'deadline', 'is_past_deadline',
            'created_at', 'question_count', 'assigned_student_count'
        )


class AssessmentDetailSerializer(serializers.ModelSerializer):
    """Serializer for viewing/editing a single assessment"""
    mentor = BasicUserSerializer(read_only=True)
    questions = QuestionSerializer(many=True, read_only=True) # Questions are managed separately
    assigned_students = BasicUserSerializer(many=True, read_only=True) # Use IDs for assignment
    assigned_student_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='student'),
        many=True, write_only=True, source='assigned_students'
    )
    is_past_deadline = serializers.BooleanField(read_only=True)

    class Meta:
        model = Assessment
        fields = (
            'id', 'mentor', 'title', 'description', 'deadline', 'created_at', 'updated_at', 'preferred_criteria',
            'assigned_students', 'assigned_student_ids', 'questions', 'is_past_deadline', 
            # 'evaluation_criteria_prompt' # Include if using this field
        )
        read_only_fields = ('mentor', 'created_at', 'updated_at', 'questions', 'is_past_deadline', 'assigned_students')

    def validate_deadline(self, value):
        """Ensure deadline is in the future for new assessments or updates."""
        # Allow updating other fields even if deadline is past, but not setting a past deadline.
        if value <= timezone.now():
             # Check if it's an update and the deadline hasn't changed or is already past
             if self.instance and self.instance.deadline and value == self.instance.deadline:
                 pass # Allow saving if deadline wasn't the field being changed
             elif self.instance and self.instance.is_past_deadline and value < self.instance.deadline:
                 raise serializers.ValidationError("Cannot set deadline further in the past.")
             elif not (self.instance and self.instance.is_past_deadline): # Prevent setting past deadline on create or future->past update
                 raise serializers.ValidationError("Deadline must be set in the future.")
        return value

# --- Serializer for the Scheduler Update ---
class SchedulerSubmissionUpdateSerializer(serializers.Serializer):
    """Serializer used by the scheduler endpoint to update submission status"""
    student_id = serializers.IntegerField()
    question_id = serializers.IntegerField()
    assessment_id = serializers.IntegerField() # Added for verification
    status = serializers.ChoiceField(choices=AssessmentSubmission.STATUS_CHOICES)
    evaluation_score = serializers.FloatField(allow_null=True, required=False)
    evaluation_feedback = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    codeforces_verdict = serializers.CharField(allow_null=True, required=False, max_length=50)
    codeforces_submission_id = serializers.IntegerField(allow_null=True, required=False)
    codeforces_passed_test_count = serializers.IntegerField(allow_null=True, required=False)
    codeforces_time_consumed_millis = serializers.IntegerField(allow_null=True, required=False)
    codeforces_memory_consumed_bytes = serializers.IntegerField(allow_null=True, required=False)
    # solved_at is handled in the model's save method

    def update(self, instance, validated_data):
        instance.status = validated_data.get('status', instance.status)
        instance.evaluation_score = validated_data.get('evaluation_score', instance.evaluation_score)
        instance.evaluation_feedback = validated_data.get('evaluation_feedback', instance.evaluation_feedback)
        instance.codeforces_verdict = validated_data.get('codeforces_verdict', instance.codeforces_verdict)
        instance.codeforces_submission_id = validated_data.get('codeforces_submission_id', instance.codeforces_submission_id)
        instance.codeforces_passed_test_count = validated_data.get('codeforces_passed_test_count', instance.codeforces_passed_test_count)
        instance.codeforces_time_consumed_millis = validated_data.get('codeforces_time_consumed_millis', instance.codeforces_time_consumed_millis)
        instance.codeforces_memory_consumed_bytes = validated_data.get('codeforces_memory_consumed_bytes', instance.codeforces_memory_consumed_bytes)
        # last_checked_at and solved_at are handled in save()
        instance.save()
        return instance

    def create(self, validated_data):
        # This serializer is primarily for updates, but handle creation if needed
        # Ensure student, question, assessment exist and are linked correctly
        try:
            student = User.objects.get(pk=validated_data['student_id'], role='student')
            question = Question.objects.get(pk=validated_data['question_id'])
            # Verify question belongs to the assessment
            if question.assessment_id != validated_data['assessment_id']:
                 raise serializers.ValidationError("Question does not belong to the specified assessment.")
            assessment = question.assessment # Get assessment via question

            # Verify student is assigned to the assessment
            if not assessment.assigned_students.filter(pk=student.id).exists():
                 raise serializers.ValidationError("Student is not assigned to this assessment.")

        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid student_id.")
        except Question.DoesNotExist:
            raise serializers.ValidationError("Invalid question_id.")

        # Create or update logic
        submission, created = AssessmentSubmission.objects.update_or_create(
            student=student,
            question=question,
            assessment=assessment, # Set assessment explicitly
            defaults={
                'status': validated_data.get('status'),
                'evaluation_score': validated_data.get('evaluation_score'),
                'evaluation_feedback': validated_data.get('evaluation_feedback'),
                'codeforces_verdict': validated_data.get('codeforces_verdict'),
                'codeforces_submission_id': validated_data.get('codeforces_submission_id'),
                'codeforces_passed_test_count': validated_data.get('codeforces_passed_test_count'),
                'codeforces_time_consumed_millis': validated_data.get('codeforces_time_consumed_millis'),
                'codeforces_memory_consumed_bytes': validated_data.get('codeforces_memory_consumed_bytes'),
                # last_checked_at and solved_at handled in save()
            }
        )
        return submission