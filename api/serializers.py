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
from django.db import IntegrityError
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

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        verification_url = f"{settings.FRONTEND_URL}/verify-email/?uid={uid}&token={token}/"

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
        instance.username = validated_data.get('username', instance.username)
        if 'email' in validated_data and validated_data['email'] != instance.email:
            instance.email = validated_data['email']
            instance.is_verified = False
            
            token = default_token_generator.make_token(instance)
            uid = urlsafe_base64_encode(force_bytes(instance.pk))
            verification_url = f"/verify-email/?uid={uid}&token={token}"
            
            
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

        try:
            uid = force_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError("Invalid reset link")

    
        if not default_token_generator.check_token(user, data['token']):
            raise serializers.ValidationError("Invalid or expired reset link")

        return data

    def reset_password(self, validated_data):
        try:
            uid = force_str(urlsafe_base64_decode(validated_data['uid']))
            user = User.objects.get(pk=uid)
        
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
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)

    class Meta:
        model = Question
        fields = (
            'id', 'assessment', 'assessment_title',
            'platform',         
            'platform_display', 
            'contest_id',       
            'problem_index',    
            'title', 'link', 'tags', 'rating', 'points',
        )
        read_only_fields = (
            'id', 'assessment', 'assessment_title', 'platform_display',
            'title', 'link', 'tags', 'rating' # Metadata and links are fetched/generated
        )
        extra_kwargs = {
            'contest_id': {'required': False, 'allow_null': True},
            'points': {'required': False} 
        }

    def validate(self, data):
        """Ensure contest_id is provided if and only if platform is codeforces."""
        platform = data.get('platform', getattr(self.instance, 'platform', None)) 
        contest_id = data.get('contest_id', getattr(self.instance, 'contest_id', None))

        if platform == 'codeforces':
            if contest_id is None:
                raise serializers.ValidationError({'contest_id': 'Contest ID is required for Codeforces questions.'})
        elif platform == 'codechef':
            if contest_id is not None:
                raise serializers.ValidationError({'contest_id': 'Contest ID must be blank (null) for CodeChef questions.'})

        if not data.get('problem_index', getattr(self.instance, 'problem_index', None)):
             raise serializers.ValidationError({'problem_index': 'Problem Index/Code is required.'})


        return data

class MentorAssignmentListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing assignments created by a mentor, including
    submission progress counts.
    """
    total_assigned_students = serializers.SerializerMethodField()
    submitted_students_count = serializers.SerializerMethodField()
    deadline = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True) 

    class Meta:
        model = Assessment
        fields = [
            'id',
            'title',
            'description',
            'deadline',
            'created_at',
            'preferred_criteria',
            'total_assigned_students', 
            'submitted_students_count', 
        ]
        read_only_fields = fields 

    def get_total_assigned_students(self, obj):
        """
        Returns the total number of students assigned to this assessment.
        Uses prefetched data if available.
        """
        # Check if 'assigned_students' was prefetched
        if hasattr(obj, 'assigned_students_count_annotation'):
             return obj.assigned_students_count_annotation 
        return obj.assigned_students.count()


    def get_submitted_students_count(self, obj):
        """
        Returns the count of unique students who have at least one 'OK'
        submission for this assessment. Uses prefetched data if available.
        """
        if hasattr(obj, 'successful_submission_students_count_annotation'):
            return obj.successful_submission_students_count_annotation 

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
    question_display = serializers.SerializerMethodField() 
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)

    class Meta:
        model = AssessmentSubmission
        fields = (
            'id', 'student', 'question', 'question_display', 'assessment', 'assessment_title',
            'status', 'evaluation_score', 'evaluation_feedback',
            'codeforces_verdict', 'codeforces_submission_id', 'plagiarism_score',
            'codeforces_passed_test_count', 'codeforces_time_consumed_millis',
            'codeforces_memory_consumed_bytes', 'solved_at', 'last_checked_at'
        )
        read_only_fields = ( 
            'id', 'student', 'question', 'question_display', 'assessment', 'assessment_title',
            'status', 'evaluation_score', 'evaluation_feedback',
            'codeforces_verdict', 'codeforces_submission_id', 'plagiarism_score',
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
    questions = QuestionSerializer(many=True, read_only=True)
    assigned_students = BasicUserSerializer(many=True, read_only=True)
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
        )
        read_only_fields = ('mentor', 'created_at', 'updated_at', 'questions', 'is_past_deadline', 'assigned_students')

    def validate_deadline(self, value):
        """Ensure deadline is in the future for new assessments or updates."""
        if value <= timezone.now():
             if self.instance and self.instance.deadline and value == self.instance.deadline:
                 pass 
             elif self.instance and self.instance.is_past_deadline and value < self.instance.deadline:
                 raise serializers.ValidationError("Cannot set deadline further in the past.")
             elif not (self.instance and self.instance.is_past_deadline): # Prevent setting past deadline on create or future->past update
                 raise serializers.ValidationError("Deadline must be set in the future.")
        return value

class SchedulerSubmissionUpdateSerializer(serializers.Serializer):
    """Serializer used by the scheduler endpoint to update submission status. Enforces CodeChef only."""
    student_id = serializers.IntegerField()
    question_id = serializers.IntegerField()
    assessment_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=AssessmentSubmission.STATUS_CHOICES)

    # Evaluation results
    evaluation_score = serializers.FloatField(allow_null=True, required=False)
    evaluation_feedback = serializers.CharField(allow_null=True, required=False, allow_blank=True)

    # Platform results
    codeforces_verdict = serializers.CharField(allow_null=True, required=False, max_length=50)
    codeforces_submission_id = serializers.IntegerField(allow_null=True, required=False)
    codeforces_passed_test_count = serializers.IntegerField(allow_null=True, required=False)
    codeforces_time_consumed_millis = serializers.IntegerField(allow_null=True, required=False)
    codeforces_memory_consumed_bytes = serializers.IntegerField(allow_null=True, required=False)

    # Submission and Plagirism
    submitted_code = serializers.CharField(allow_null=True, required=False, allow_blank=True, style={'base_template': 'textarea.html'})
    plagiarism_score = serializers.IntegerField(allow_null=True, required=False) 

    def validate(self, data):
        score = data.get('plagiarism_score')
        if score is not None and (score < 0 or score > 100): 
             raise serializers.ValidationError({'plagiarism_score': 'Score must be between 0 and 100.'})
        return data

    def create(self, validated_data):
        """Handles creation of submission status, enforcing CodeChef platform."""
        try:
            student = User.objects.get(pk=validated_data['student_id'], role='student')
            question = Question.objects.get(pk=validated_data['question_id'])

            # --- Platform Enforcement ---
            if question.platform != 'codechef':
                raise serializers.ValidationError(
                    f"Submissions are only allowed for CodeChef questions. "
                    f"Question ID {question.id} is on platform '{question.platform}'."
                )
            # --- End Platform Enforcement ---

            if question.assessment_id != validated_data['assessment_id']:
                 raise serializers.ValidationError("Question does not belong to the specified assessment.")
            assessment = question.assessment

            if not assessment.assigned_students.filter(pk=student.id).exists():
                 raise serializers.ValidationError("Student is not assigned to this assessment.")

        except User.DoesNotExist:
            raise serializers.ValidationError({"student_id": "Invalid student_id."})
        except Question.DoesNotExist:
            raise serializers.ValidationError({"question_id": "Invalid question_id."})


        # Use update_or_create, passing the new fields in defaults
        submission, created = AssessmentSubmission.objects.update_or_create(
            student=student,
            question=question,
            assessment=assessment,
            defaults={
                'status': validated_data.get('status'),
                'evaluation_score': validated_data.get('evaluation_score'),
                'evaluation_feedback': validated_data.get('evaluation_feedback'),
                'codeforces_verdict': validated_data.get('codeforces_verdict'),
                'codeforces_submission_id': validated_data.get('codeforces_submission_id'),
                'codeforces_passed_test_count': validated_data.get('codeforces_passed_test_count'),
                'codeforces_time_consumed_millis': validated_data.get('codeforces_time_consumed_millis'),
                'codeforces_memory_consumed_bytes': validated_data.get('codeforces_memory_consumed_bytes'),
                'submitted_code': validated_data.get('submitted_code'),
                'plagiarism_score': validated_data.get('plagiarism_score'),
                
            }
        )
        return submission

    def update(self, instance, validated_data):
        """Handles updates. Platform check done by model's save()."""
        instance.status = validated_data.get('status', instance.status)
        instance.evaluation_score = validated_data.get('evaluation_score', instance.evaluation_score)
        instance.evaluation_feedback = validated_data.get('evaluation_feedback', instance.evaluation_feedback)
        instance.codeforces_verdict = validated_data.get('codeforces_verdict', instance.codeforces_verdict)
        instance.codeforces_submission_id = validated_data.get('codeforces_submission_id', instance.codeforces_submission_id)
        instance.codeforces_passed_test_count = validated_data.get('codeforces_passed_test_count', instance.codeforces_passed_test_count)
        instance.codeforces_time_consumed_millis = validated_data.get('codeforces_time_consumed_millis', instance.codeforces_time_consumed_millis)
        instance.codeforces_memory_consumed_bytes = validated_data.get('codeforces_memory_consumed_bytes', instance.codeforces_memory_consumed_bytes)
        instance.submitted_code = validated_data.get('submitted_code', instance.submitted_code)
        instance.plagiarism_score = validated_data.get('plagiarism_score', instance.plagiarism_score)

        instance.save() 
        return instance