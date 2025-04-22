from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .permissions import *
from .models import *
import requests  # For fetching platform data
from rest_framework.permissions import AllowAny
from .codechef import *
from rest_framework import status, viewsets, permissions, generics 
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from .utils import account_activation_token
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView
import logging
from django.http import HttpResponseRedirect # Ensure this permission exists
from .leetcode import *
from .codechef_api import *
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .serializers import *
from rest_framework.decorators import action
from .codeforces import *
from django.utils import timezone
import datetime
from django.db.models import Avg, Max, Min, Count, F, FloatField, Case, When, Q, Sum
from django.db.models.functions import Cast
from .codeforces_api import *
from .codechef_questions import *
logger = logging.getLogger(__name__)

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class UserRegistrationView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "User registered successfully. Please check your email to verify your account.",
                "user_id": user.id
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class EmailVerificationView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        # Get UID and token from query parameters
        uidb64 = request.query_params.get('uid')
        token = request.query_params.get('token')
        
        # Validate input
        if not uidb64 or not token:
            return Response({
                'success': False,
                'message': 'Missing verification parameters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Decode the user ID
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)

            # Clean the token (remove any extra characters after the actual token)
            clean_token = token.split('/')[0] if '/' in token else token

            # Check if the token is valid
            if default_token_generator.check_token(user, clean_token):
                # Mark user as verified
                user.is_verified = True
                user.save()

                logger.info(f"Email verified for user {user.email}")
                return HttpResponseRedirect("http://127.0.0.1:3000/auth?mode=login")
            else:
                logger.warning(f"Invalid token for user {user.email}")
                return Response({
                    'success': False,
                    'message': 'Invalid or expired verification link.'
                }, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            logger.error(f"Verification attempted with non-existent user ID: {uid}")
            return Response({
                'success': False,
                'message': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Verification error: {str(e)}")
            return Response({
                'success': False,
                'message': 'Verification failed due to an unexpected error.'
            }, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.send_password_reset_email(serializer.validated_data)
                return Response({
                    "message": "Password reset link sent to your email."
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    "message": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.reset_password(serializer.validated_data)
                return Response({
                    "message": "Password reset successfully."
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    "message": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AddPlatformProfileView(APIView):
    permission_classes = [IsAuthenticated,IsStudent]

    def post(self, request):
        profile = PlatformProfile.objects.filter(user=request.user, platform=request.data.get('platform'), profile_id=request.data.get('profile_id')).first()
        if profile:
            return Response({"error": "Profile already exists"}, status=status.HTTP_200_OK)
        serializer = PlatformProfileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class VerifyPlatformView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        profiles = PlatformProfile.objects.filter(user=request.user)
        serializer = PlatformProfileSerializer(profiles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        platform = request.data.get('platform')
        profile_id = request.data.get('profile_id')
        random_string = request.data.get('random_string')

        if not platform or not profile_id or not random_string:
            return Response({"message": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch the first matching profile, or create a new one if none exist
            profile = PlatformProfile.objects.filter(
                user=request.user, platform=platform, profile_id=profile_id
            ).first()

        except Exception as e:
            return Response({"message": f"Database error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Platform Verification Logic
        try:
            if platform == 'codechef':
                response = get_name_display(profile_id)  # Fetch display name
                if response == random_string:
                    profile.is_verified = True
                    profile.save()
                    return Response({
                        "message": "Verified the profile on CodeChef",
                        "profile": PlatformProfileSerializer(profile).data
                    }, status=status.HTTP_200_OK)

            elif platform == 'leetcode':
                response = get_user_about_me(profile_id)
                if random_string == response:  # Check "about me" section
                    profile.is_verified = True
                    profile.save()
                    return Response({
                        "message": "Verified the profile on LeetCode",
                        "profile": PlatformProfileSerializer(profile).data
                    }, status=status.HTTP_200_OK)

            return Response({
                "message": "Profile verified",
                "profile": PlatformProfileSerializer(profile).data
            }, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.RequestException as e:
            return Response({"message": f"Error fetching platform data: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class PlatformProfileDeleteView(APIView):
    def delete(self, request, id):  # Capture `id` from the URL
        try:
            profile = PlatformProfile.objects.get(id=id)
            profile.delete()
            return Response({"message": "Profile deleted successfully"}, status=status.HTTP_200_OK)
        except PlatformProfile.DoesNotExist:
            return Response({"message": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"message": f"Error deleting profile: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsMentor]

    def get(self, request, id):
        platform = request.query_params.get('platform')
        profiles = PlatformProfile.objects.filter(
            user=id,
            is_verified=True,
            platform=platform
        )
        analytics = {}
        if profiles.exists():
            profile = profiles.first()  # Get the first matching profile
            if platform.lower() == 'leetcode':
                # Assuming 'profile_id' is the field storing the LeetCode username
                # Replace 'profile_id' with the actual field name if different
                username = profile.profile_id  
                analytics = self.get_leetcode_analytics(username)
            if platform.lower() == 'codechef':
                # Assuming 'profile_id' is the field storing the CodeChef username
                # Replace 'profile_id' with the actual field name if different
                username = profile.profile_id  
                analytics = self.get_codechef_analytics(username)
            if platform.lower() == 'codeforces':
                # Assuming 'profile_id' is the field storing the Codeforces username
                # Replace 'profile_id' with the actual field name if different
                username = profile.profile_id  
                analytics = self.get_codeforces_analytics(username)
        
        return Response(analytics)
    
    def get_leetcode_analytics(self, username):        
        analytics = {
            'profile': get_user_profile(username),
            'ranking_contest': get_user_ranking_and_contest(username),
            'language_distribution': get_language_wise_distribution(username),
            'topic_distribution': get_topic_wise_distribution(username),
            'recent_submissions': get_recent_submissions(username),
            'about_me': get_user_about_me(username)
        }
        return analytics
    
    def get_codechef_analytics(self, username):
        codechef_data = CodechefAPI(username)
        analytics = {
            'profile': codechef_data.get_rating(),
            'ranking_contest': codechef_data.get_rank(),
            'stars': codechef_data.get_stars(),
            'submissions_monthly': codechef_data.get_submissions_monthly(),
            'submissions_weekly': codechef_data.get_submissions_weekly(),
            'ratings_graph': codechef_data.get_ratings_graph()
        }
        return analytics
    
    def get_codeforces_analytics(self, username):
        
        analytics = {
            'profile': get_cf_user_info(username),
            'solved_counts': get_cf_solved_counts(username),
            'language_distribution': get_cf_language_distribution(username),
            'tag_distribution': get_cf_tag_distribution(username),
            'submissions_monthly': get_cf_submission_calendar(username)["monthly_submissions"],
            'submissions_weekly': get_cf_submission_calendar(username)["weekly_submissions"],
            'ratings_graph': get_cf_rating_history(username)
        }
        return analytics


class StudentAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        platform = request.query_params.get('platform')
        profiles = PlatformProfile.objects.filter(
            user=request.user, 
            is_verified=True, 
            platform=platform
        )
        

        analytics = {}
        
        if profiles.exists():
            profile = profiles.first()  # Get the first matching profile
            if platform.lower() == 'leetcode':
                # Assuming 'profile_id' is the field storing the LeetCode username
                # Replace 'profile_id' with the actual field name if different
                username = profile.profile_id  
                analytics = self.get_leetcode_analytics(username)
            if platform.lower() == 'codechef':
                # Assuming 'profile_id' is the field storing the CodeChef username
                # Replace 'profile_id' with the actual field name if different
                username = profile.profile_id  
                analytics = self.get_codechef_analytics(username)
            if platform.lower() == 'codeforces':
                # Assuming 'profile_id' is the field storing the Codeforces username
                # Replace 'profile_id' with the actual field name if different
                username = profile.profile_id  
                analytics = self.get_codeforces_analytics(username)
        
        return Response(analytics)


    def get_leetcode_analytics(self, username):        
        analytics = {
            'profile': get_user_profile(username),
            'ranking_contest': get_user_ranking_and_contest(username),
            'language_distribution': get_language_wise_distribution(username),
            'topic_distribution': get_topic_wise_distribution(username),
            'recent_submissions': get_recent_submissions(username),
            'about_me': get_user_about_me(username)
        }
        return analytics
    
    def get_codechef_analytics(self, username):
        codechef_data = CodechefAPI(username)
        analytics = {
            'profile': codechef_data.get_rating(),
            'ranking_contest': codechef_data.get_rank(),
            'stars': codechef_data.get_stars(),
            'submissions_monthly': codechef_data.get_submissions_monthly(),
            'submissions_weekly': codechef_data.get_submissions_weekly(),
            'ratings_graph': codechef_data.get_ratings_graph()
        }
        return analytics
    def get_codeforces_analytics(self, username):
        
        analytics = {
            'profile': get_cf_user_info(username),
            'solved_counts': get_cf_solved_counts(username),
            'language_distribution': get_cf_language_distribution(username),
            'tag_distribution': get_cf_tag_distribution(username),
            'submissions_monthly': get_cf_submission_calendar(username)["monthly_submissions"],
            'submissions_weekly': get_cf_submission_calendar(username)["weekly_submissions"],
            'ratings_graph': get_cf_rating_history(username)
        }
        return analytics
class MentorStudentAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsMentor]

    def get(self, request):
        students = MentorStudentMapping.objects.filter(mentor=request.user).values_list('student', flat=True)
        analytics = {}
        for student_id in students:
            profiles = PlatformProfile.objects.filter(user_id=student_id, is_verified=True)
            student_analytics = {}
            for profile in profiles:
                if profile.platform == 'codeforces':
                    response = requests.get(f"https://codeforces.com/api/user.info?handles={profile.profile_id}")
                    student_analytics[profile.platform] = response.json()
            analytics[student_id] = student_analytics
        return Response(analytics)

class MentorStudentMappingView(APIView):
    permission_classes = [IsAuthenticated,IsStudent]

    def get(self, request):
        mentors = User.objects.filter(role='mentor')
        serializer = UserSerializer(mentors, many=True)
        return Response(serializer.data)

    def post(self, request):
        mentor_id = request.data.get('mentor_id')
        if not mentor_id:
            return Response({"message": "Mentor is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            mentor = User.objects.get(id=mentor_id, role='mentor')
            MentorStudentMapping.objects.get_or_create(mentor=mentor, student=request.user)
            return Response({"message": "You have successfully joined the mentor."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"message": "Mentor not found"}, status=status.HTTP_404_NOT_FOUND)

class StudentMentorMappingView(APIView):
    permission_classes = [IsAuthenticated,IsMentor]

    def get(self, request):
        students = User.objects.filter(role='student')
        serializer = UserSerializer(students, many=True)
        return Response(serializer.data)

class AssessmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Mentors to Create/Manage Assessments and
    for Students to View Assigned Assessments.
    """
    queryset = Assessment.objects.prefetch_related('assigned_students', 'questions').all()
    # permission_classes = [IsAuthenticated] # Base permission

    def get_serializer_class(self):
        if self.action == 'list':
            return AssessmentListSerializer
        return AssessmentDetailSerializer

    def get_permissions(self):
        """Instantiates and returns the list of permissions for the action."""
        if self.action in ['create', 'destroy', 'update', 'partial_update', 'add_question', 'remove_question', 'assign_students']:
            # Only mentors can create/modify assessments
            permission_classes = [IsAuthenticated, IsMentor, IsAssessmentMentorOwner]
            # For create, ownership check doesn't apply yet
            if self.action == 'create':
                 permission_classes = [IsAuthenticated, IsMentor]
        elif self.action in ['list', 'retrieve', 'questions', 'submissions', 'results']:
            # Students can view assigned, Mentors can view owned
            permission_classes = [IsAuthenticated, IsAssignedStudentOrMentorOwnerReadOnly]
        else:
            permission_classes = [IsAuthenticated] # Default restrictive
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Filter assessments based on user role."""
        user = self.request.user
        if not user.is_authenticated:
            return Assessment.objects.none()
        if user.role == 'mentor':
            # Mentors see assessments they created
            return Assessment.objects.filter(mentor=user).prefetch_related('assigned_students', 'questions')
        elif user.role == 'student':
            # Students see assessments assigned to them
            return Assessment.objects.filter(assigned_students=user).prefetch_related('questions')
        return Assessment.objects.none() # Should not happen for authenticated users

    def perform_create(self, serializer):
        serializer.save(mentor=self.request.user)



    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsMentor, IsAssessmentMentorOwner])
    def add_question(self, request, pk=None):
        """
        Add a question (by platform, contest_id/index) to an assessment, fetching metadata.
        Requires 'platform', 'problem_index', and optionally 'contest_id' (for Codeforces).
        Calls platform-specific metadata fetcher (API for CF, Selenium for CC).
        """
        assessment = self.get_object()
        if assessment.is_past_deadline:
             return Response({"detail": "Cannot add questions after the deadline."}, status=status.HTTP_400_BAD_REQUEST)

        input_serializer = QuestionSerializer(data=request.data, context={'request': request, 'assessment': assessment})
        if not input_serializer.is_valid():
            logger.warning(f"Add question validation failed for assessment {pk}: {input_serializer.errors}")
            return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        platform = input_serializer.validated_data['platform']
        problem_index = input_serializer.validated_data['problem_index']
        contest_id = input_serializer.validated_data.get('contest_id')
        points = input_serializer.validated_data.get('points', Question._meta.get_field('points').default)

        metadata = None
        identifier = problem_index # Default identifier

        try:
            if platform == 'codeforces':
                identifier = f"{contest_id}{problem_index}"
                # --- Call Codeforces Fetcher (Assumed API based) ---
                metadata = fetch_problem_metadata_cf(contest_id, problem_index)
                # ---
            elif platform == 'codechef':
                identifier = problem_index
                # --- Call CodeChef Selenium Scraper ---
                metadata = fetch_problem_metadata_cc(problem_index)
                # ---
            else:
                logger.warning(f"Metadata fetching not implemented for platform: {platform} on assessment {pk}")

        except Exception as e:
            # Catch errors during the metadata fetch process itself
            logger.error(f"Error during metadata fetch call for {platform} problem {identifier} for assessment {pk}: {e}", exc_info=True)
            # Proceeding without metadata: metadata remains None

        # --- Handle Metadata Fetch Result ---
        fetched_title = None
        fetched_tags_str = None # Store tags as comma-separated string
        fetched_rating = None
        if metadata is not None:
            fetched_title = metadata.get('title')
            fetched_tags_list = metadata.get('tags') # Expecting a list from both fetchers now
            if isinstance(fetched_tags_list, list):
                fetched_tags_str = ','.join(filter(None, fetched_tags_list))
            elif isinstance(fetched_tags_list, str): # Handle if CF fetcher returns string
                 fetched_tags_str = fetched_tags_list
            fetched_rating = metadata.get('rating')
        else:
            logger.warning(f"Could not fetch or process metadata for {platform} problem {identifier}. Adding question without title/tags/rating.")

        # --- Create and Save the Question ---
        try:
            # Standardize case for problem index before saving
            problem_index_upper = problem_index.upper()
            question = Question.objects.create(
                assessment=assessment,
                platform=platform,
                contest_id=contest_id,
                problem_index=problem_index_upper, # Save standardized index
                points=points,
                title=fetched_title,
                tags=fetched_tags_str, # Save comma-separated string or None
                rating=fetched_rating
            )
            output_serializer = QuestionSerializer(question, context={'request': request})
            logger.info(f"Successfully added {platform} question {question.id} ({identifier}) to assessment {assessment.id}")
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)

        except IntegrityError as e:
             logger.warning(f"Attempt to add duplicate question ({platform}, {identifier}) to assessment {assessment.id}: {e}")
             # Specific error messages based on constraint name
             if 'unique_assessment_codeforces_question' in str(e):
                 error_detail = "This Codeforces problem (contest_id, problem_index) already exists in the assessment."
             elif 'unique_assessment_codechef_question' in str(e):
                 # Use the standardized index in the error message
                 error_detail = f"This CodeChef problem ({problem_index_upper}) already exists in the assessment."
             else:
                 error_detail = "This problem already exists in the assessment."
             return Response({"detail": error_detail}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
             logger.error(f"Database or unexpected error saving question {platform} {identifier} for assessment {assessment.id}: {e}", exc_info=True)
             return Response({"detail": "An error occurred while saving the question."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'], url_path='remove_question/(?P<question_pk>[^/.]+)', permission_classes=[IsAuthenticated, IsMentor, IsAssessmentMentorOwner])
    def remove_question(self, request, pk=None, question_pk=None):
        """Remove a question from an assessment."""
        assessment = self.get_object()
        if assessment.is_past_deadline:
             return Response({"detail": "Cannot remove questions after the deadline."}, status=status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(Question, pk=question_pk, assessment=assessment)
        # Consider if submissions exist - maybe prevent deletion?
        if AssessmentSubmission.objects.filter(question=question).exists():
             return Response({"detail": "Cannot remove question with existing student submissions."}, status=status.HTTP_400_BAD_REQUEST)

        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='questions', permission_classes=[IsAuthenticated, IsAssignedStudentOrMentorOwnerReadOnly])
    def list_questions(self, request, pk=None):
        """List all questions for a specific assessment."""
        assessment = self.get_object()
        questions = Question.objects.filter(assessment=assessment)
        serializer = QuestionSerializer(questions, many=True, context={'request': request})
        return Response(serializer.data)

    # --- Custom Actions for Submissions/Results ---

    @action(detail=True, methods=['get'], url_path='submissions', permission_classes=[IsAuthenticated, IsAssignedStudentOrMentorOwnerReadOnly])
    def list_submissions(self, request, pk=None):
        """
        List submission statuses for an assessment.
        Mentors see all, Students see only their own.
        """
        assessment = self.get_object()
        user = request.user
        submissions = AssessmentSubmission.objects.filter(assessment=assessment).select_related('student', 'question')

        if user.role == 'student':
            submissions = submissions.filter(student=user)

        serializer = AssessmentSubmissionSerializer(submissions, many=True, context={'request': request})
        return Response(serializer.data)

    # views.py (or wherever your AssessmentViewSet is)

    @action(detail=True, methods=['get'], url_path='results',
            permission_classes=[IsAuthenticated]) # Add specific permissions if needed
    def view_results(self, request, pk=None):
        """
        Provide an aggregated view of results (overall stats, per-question stats)
        and a list of individual student scores (including non-participants) for the mentor.
        """
        try:
            # Use prefetch_related for efficiency
            assessment = Assessment.objects.prefetch_related(
                'questions', # Prefetch related Question objects
                'assigned_students' # Prefetch related User objects (students)
            ).get(pk=pk)
            # self.check_object_permissions(request, assessment) # Apply object-level permissions if needed
        except Assessment.DoesNotExist:
            return Response({"error": "Assessment not found"}, status=status.HTTP_404_NOT_FOUND)

        # --- Configuration ---
        # PASS_THRESHOLD_PERCENT = 50.0 # Example: Define what constitutes a passing score

        # --- Data Fetching ---
        assigned_students_qs = assessment.assigned_students.all()
        # Fetch Question objects linked to this assessment
        assessment_questions_qs = assessment.questions.all().order_by('id') # Order for consistency

        # Fetch evaluated submissions efficiently
        submissions = AssessmentSubmission.objects.filter(
            assessment=assessment,
            # Use the string value directly as defined in STATUS_CHOICES tuple
            status='EVALUATED',
            evaluation_score__isnull=False
        ).select_related('student', 'question') # Select related for details

        total_assigned_students = assigned_students_qs.count()
        all_assigned_student_ids = {s.id for s in assigned_students_qs}

        # Calculate max score based on fetched Question objects
        max_total_score = sum(q.points for q in assessment_questions_qs if q.points and q.points > 0)

        # --- Initializations ---
        student_total_scores = defaultdict(float)
        student_solved_counts = defaultdict(int)
        participating_student_ids = set() # Track who actually submitted

        # --- Process Submissions (Calculate scores and solved counts for participants) ---
        for sub in submissions:
            # Ensure the student is actually assigned (safety check)
            if sub.student_id not in all_assigned_student_ids:
                continue

            student_id = sub.student_id
            participating_student_ids.add(student_id)

            # Use question points from the related Question object
            # Check if sub.question exists before accessing points
            question_points = sub.question.points if sub.question else 0
            score = sub.evaluation_score # Already checked for null

            # Ensure score doesn't exceed question points if points are defined and positive
            if question_points and question_points > 0:
                 score = min(score, question_points)
            elif score < 0: # Ensure score isn't negative if points are 0 or null
                 score = 0

            student_total_scores[student_id] += score

            # Count solved questions (verdict 'OK')
            if sub.codeforces_verdict == 'OK':
                 student_solved_counts[student_id] += 1


        participating_students_count = len(participating_student_ids)

        # --- Calculate Overall Stats ---
        # Initialize with defaults or N/A (returning numbers or None)
        overall_stats = {
            "average_score": None,
            "completed_count": participating_students_count,
            "total_participants": total_assigned_students,
            # "pass_rate": None, # Example: Calculate pass rate if needed
        }

        if participating_students_count > 0 and max_total_score > 0:
            total_score_sum = sum(student_total_scores.values())
            # Average score among participants
            average_score_among_participants = total_score_sum / participating_students_count
            overall_stats["average_score"] = round(average_score_among_participants, 1)

            # Example Pass Rate Calculation (based on participants)
            # passing_score_threshold = (PASS_THRESHOLD_PERCENT / 100.0) * max_total_score
            # passing_students_count = sum(
            #     1 for student_id in participating_student_ids
            #     if student_total_scores.get(student_id, 0) >= passing_score_threshold
            # )
            # pass_rate_percentage = (passing_students_count / participating_students_count) * 100
            # overall_stats["pass_rate"] = round(pass_rate_percentage, 1) # Return number

        elif participating_students_count == 0:
             overall_stats["average_score"] = 0.0 # Or None, depending on preference
             # overall_stats["pass_rate"] = 0.0 # Or None

        # --- Calculate Per-Question Stats ---
        question_stats_list = []
        for q in assessment_questions_qs: # Iterate through Question objects
            question_points = q.points
            question_display = q.title or f"{q.contest_id}{q.problem_index}"

            # Filter submissions in memory for this Question
            q_submissions = [s for s in submissions if s.question_id == q.id]
            num_attempts = len(q_submissions) # Number of evaluated attempts
            num_successful = sum(1 for s in q_submissions if s.codeforces_verdict == 'OK')

            q_stat = {
                "question_id": q.id, # ID of the Question object
                "question_name": question_display,
                "average_score": None,
                "highest_score": None,
                # "lowest_score": None, # Optional
                "attempt_count": num_attempts,
                "success_rate": None, # Percentage of attempts that were 'OK'
            }

            if num_attempts > 0 and question_points and question_points > 0:
                total_score = 0
                max_score = 0.0
                # min_score = question_points # Start high for min calculation
                for sub in q_submissions:
                    # Use capped score for consistency if needed
                    raw_score = sub.evaluation_score
                    capped_score = max(0.0, min(raw_score, question_points))
                    total_score += capped_score
                    max_score = max(max_score, capped_score)
                    # min_score = min(min_score, capped_score)

                q_stat["average_score"] = round(total_score / num_attempts, 1)
                q_stat["highest_score"] = round(max_score, 1)
                # q_stat["lowest_score"] = round(min_score, 1)
                q_stat["success_rate"] = round((num_successful / num_attempts) * 100, 1)

            elif num_attempts > 0: # Handle case with attempts but 0 points
                 q_stat["average_score"] = 0.0
                 q_stat["highest_score"] = 0.0
                 # q_stat["lowest_score"] = 0.0
                 q_stat["success_rate"] = round((num_successful / num_attempts) * 100, 1)


            question_stats_list.append(q_stat)


        # --- Prepare Individual Student Score List (Including Non-Participants) ---
        student_scores_list = []
        if total_assigned_students > 0:
            # Fetch student details for ALL assigned students
            # Use values() to fetch only necessary fields for efficiency
            student_details = User.objects.filter(
                id__in=list(all_assigned_student_ids)
            ).values('id', 'username', 'first_name', 'last_name')

            student_map = {}
            for student_data in student_details:
                # Construct full name or use username as fallback
                first = student_data.get('first_name', '')
                last = student_data.get('last_name', '')
                # Use .strip() to remove leading/trailing whitespace if one name is missing
                name = f"{first} {last}".strip() or student_data.get('username', f"User {student_data['id']}")
                student_map[student_data['id']] = name

            # Iterate through ALL assigned students
            for student_id in all_assigned_student_ids:
                student_name = student_map.get(student_id, f"Unknown User {student_id}")
                # Get score from calculated dict, default to 0 if not found (non-participant)
                total_score = student_total_scores.get(student_id, 0.0)
                # Get solved count, default to 0
                solved_count = student_solved_counts.get(student_id, 0)

                student_scores_list.append({
                    "student_id": student_id, # Use student_id for consistency
                    "student_name": student_name,
                    "total_score": round(total_score, 1), # Return number
                    "solved_count": solved_count
                })

            # Optional: Sort the student list (e.g., by name)
            student_scores_list.sort(key=lambda x: x.get('student_name', ''))

        # --- Structure Final Response ---
        results = {
            "overall_stats": overall_stats,
            "question_stats": question_stats_list,
            "student_scores": student_scores_list
        }

        return Response(results, status=status.HTTP_200_OK)

    # ... other viewset methods ...

    # ... other viewset methods ...

    # --- Add other Assessment actions (list, retrieve, create, update, destroy) ---
    # Example:
    # def perform_create(self, serializer):
    #     serializer.save(mentor=self.request.user)

    # def get_queryset(self):
    #     user = self.request.user
    #     if user.role == 'mentor':
    #         # Mentors see assessments they created or maybe students they mentor?
    #         return Assessment.objects.filter(mentor=user)
    #     elif user.role == 'student':
    #         # Students see assessments assigned to them
    #         return user.assigned_assessments.all()
    #     return Assessment.objects.none() # Or handle admin/other roles

# --- Codeforces Problem Fetching View ---
class SuggestCodeforcesProblemView(generics.GenericAPIView):
    """
    Endpoint for mentors to find Codeforces problems based on criteria
    (tags, rating range, count).
    """
    permission_classes = [IsAuthenticated, IsMentor]

    def get(self, request, *args, **kwargs):
        tags_str = request.query_params.get('tags', None)
        min_rating_str = request.query_params.get('min_rating', None)
        max_rating_str = request.query_params.get('max_rating', None)
        count_str = request.query_params.get('count', None) # <-- Get count parameter

        min_rating: Optional[int] = None
        max_rating: Optional[int] = None
        count: Optional[int] = None # <-- Variable for count

        # Validate Ratings
        try:
            if min_rating_str is not None and min_rating_str != '':
                min_rating = int(min_rating_str)
                if min_rating < 0: raise ValueError("Minimum rating cannot be negative.")
            if max_rating_str is not None and max_rating_str != '':
                max_rating = int(max_rating_str)
                if max_rating < 0: raise ValueError("Maximum rating cannot be negative.")

            if min_rating is not None and max_rating is not None and min_rating > max_rating:
                return Response({"detail": "Minimum rating cannot be greater than maximum rating."}, status=status.HTTP_400_BAD_REQUEST)

            # Validate Count
            if count_str is not None and count_str != '':
                count = int(count_str)
                # Set reasonable limits for count
                if count <= 0 or count > 50: # Example limit: max 50 problems
                    raise ValueError("Count must be between 1 and 50.")

        except ValueError as e:
            return Response({"detail": f"Invalid parameter value: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        # Call the updated utility function
        try:
            problems = find_problems_by_criteria(
                tags_str=tags_str,
                min_rating=min_rating,
                max_rating=max_rating,
                n=count # <-- Pass the validated count
            )

            if problems is None:
                 return Response({"detail": "Could not fetch problems based on the provided criteria."}, status=status.HTTP_404_NOT_FOUND)

            # Return empty list if no problems matched (utility function handles this)
            # if not problems:
            #      return Response([], status=status.HTTP_200_OK) # Utility now returns empty list

            # Format response
            formatted_problems = [
                {
                    "id": f"{p.get('contestId')}{p.get('index')}",
                    "contest_id": p.get("contestId"),
                    "problem_index": p.get("index"),
                    "title": p.get("name"),
                    "rating": p.get("rating"),
                    "tags": ", ".join(p.get("tags", [])),
                    "link": f"https://codeforces.com/problemset/problem/{p.get('contestId')}/{p.get('index')}"
                }
                for p in problems if p.get("contestId") and p.get("index")
            ]
            return Response(formatted_problems)

        except Exception as e:
            print(f"Error in SuggestCodeforcesProblemView: {e}")
            import traceback
            traceback.print_exc()
            return Response({"detail": "An internal error occurred while processing the request."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
             
# --- Scheduler Endpoint View ---

class SchedulerCheckSubmissionsView(generics.GenericAPIView):
    """
    Endpoint hit by the external scheduler to trigger submission checks
    and update AssessmentSubmission status. Ensures records exist for all
    student-question pairs. Checks repeatedly until the deadline passes.
    Only marks as finally EVALUATED (with score 0 if no submission found)
    after the deadline.
    Requires API Key authentication in production.
    """
    permission_classes = [IsAuthenticated] # <-- Switch to HasSchedulerAPIKey in production!
    serializer_class = SchedulerSubmissionUpdateSerializer

    # Define constants for statuses to avoid typos
    STATUS_EVALUATED = 'EVALUATED'
    STATUS_PENDING = 'PENDING_EVALUATION'
    STATUS_NOT_ATTEMPTED = 'NOT_ATTEMPTED'
    STATUS_ERROR = 'ERROR'
    # Define a verdict for when no submission is found by deadline
    VERDICT_NOT_FOUND_DEADLINE = "NOT_FOUND_BY_DEADLINE"

    def post(self, request, *args, **kwargs):
        start_run_time = timezone.now()
        logger.info(f"Scheduler run starting at {start_run_time}")
        processed_count = 0
        created_count = 0
        error_count = 0
        skipped_final_success_count = 0
        skipped_final_failure_count = 0
        skipped_recent_count = 0
        reverted_to_not_attempted_count = 0

        # --- Configuration ---
        # How long after a check should we wait before checking again? Avoids hammering API.
        RECENT_CHECK_THRESHOLD = datetime.timedelta(minutes=1)
        # How far past the deadline should we still check? (e.g., 1 day for final cleanup)
        POST_DEADLINE_CHECK_WINDOW = datetime.timedelta(minutes=0)
        # Assessments ending within the next N days are considered active
        ACTIVE_ASSESSMENT_WINDOW = datetime.timedelta(days=5)

        # 1. Find relevant assessments
        # Check assessments ending soon or recently ended
        assessment_cutoff_time = start_run_time + ACTIVE_ASSESSMENT_WINDOW
        assessments_to_check = Assessment.objects.filter(
            # deadline__lte=assessment_cutoff_time, # Ending within the window
            # deadline__gte=start_run_time - POST_DEADLINE_CHECK_WINDOW, # Not too old
            assigned_students__isnull=False,
            questions__isnull=False
        ).distinct().prefetch_related(
            'assigned_students',
            'assigned_students__platforms',
            'questions'
        )

        logger.info(f"Found {assessments_to_check.count()} assessments potentially needing checks.")

        for assessment in assessments_to_check:
            logger.info(f"--- Checking Assessment: {assessment.id} - {assessment.title} (Deadline: {assessment.deadline}) ---")
            is_past_deadline = start_run_time > assessment.deadline
            start_time_unix = int(assessment.created_at.timestamp())
            # Use deadline itself as the strict end time for searching submissions
            end_time_unix = int(assessment.deadline.timestamp())

            preferred_criteria = assessment.preferred_criteria or \
                "Focus on correctness (OK verdict). Consider efficiency if multiple OK submissions exist."

            assessment_questions = list(assessment.questions.all())
            if not assessment_questions:
                logger.warning(f"  Assessment {assessment.id} has no questions. Skipping.")
                continue

            for student in assessment.assigned_students.all():
                try:
                    cf_profile = student.platforms.filter(platform='codeforces').first()
                    if not cf_profile or not cf_profile.profile_id:
                        logger.warning(f"  Skipping student {student.username} (ID: {student.id}) for Assessment {assessment.id}: No Codeforces handle.")
                        continue

                    handle = cf_profile.profile_id
                    # logger.debug(f"  Checking Student: {student.username} (Handle: {handle})") # Debug level

                    for question in assessment_questions:
                        # --- Ensure Submission Record Exists ---
                        submission_record, created = AssessmentSubmission.objects.get_or_create(
                            student=student,
                            question=question,
                            assessment=assessment,
                            defaults={'status': self.STATUS_NOT_ATTEMPTED}
                        )

                        if created:
                            created_count += 1
                            logger.info(f"    Created Submission Record for S:{student.id}/Q:{question.id} (Status: {self.STATUS_NOT_ATTEMPTED})")

                        # --- Decide if Codeforces Check is Needed ---
                        should_check_cf = True
                        skip_reason = ""

                        # Condition 1: Final Success State - Already evaluated with a positive score
                        # (Assumes score > 0 means success, adjust if needed)
                        if submission_record.status == self.STATUS_EVALUATED and \
                           submission_record.evaluation_score is not None and \
                           submission_record.evaluation_score > 0:
                            should_check_cf = False
                            skipped_final_success_count += 1
                            skip_reason = "Already evaluated with positive score"

                        # Condition 2: Final Failure State - Past deadline and already marked EVALUATED (score 0 or null)
                        elif submission_record.status == self.STATUS_EVALUATED and is_past_deadline:
                            should_check_cf = False
                            skipped_final_failure_count += 1
                            skip_reason = "Already evaluated (failed) after deadline"

                        # Condition 3: Checked Recently (apply only if not skipped for other reasons)
                        elif submission_record.last_checked_at and \
                             submission_record.last_checked_at > start_run_time - RECENT_CHECK_THRESHOLD:
                            should_check_cf = False
                            skipped_recent_count += 1
                            skip_reason = f"Checked recently ({submission_record.last_checked_at.strftime('%Y-%m-%d %H:%M:%S')})"

                        # --- Perform Codeforces Check and Update ---
                        if should_check_cf:
                            logger.info(f"    Checking CF for S:{student.id}/Q:{question.id} (Current Status: {submission_record.status}, Past Deadline: {is_past_deadline})")

                            # Mark as PENDING and update check time immediately
                            AssessmentSubmission.objects.filter(pk=submission_record.pk).update(
                                status=self.STATUS_PENDING,
                                last_checked_at=start_run_time
                            )

                            try:
                                evaluation_data = find_and_evaluate_submission_incremental(
                                    handle=handle,
                                    contest_id=question.contest_id,
                                    problem_index=question.problem_index,
                                    start_time_unix=start_time_unix,
                                    end_time_unix=end_time_unix, # Strict deadline
                                    preferred_criteria_str=preferred_criteria
                                )

                                if evaluation_data:
                                    # Found a suitable submission - Final EVALUATED state
                                    submission_details, evaluation_result = evaluation_data
                                    update_data = {
                                        "status": self.STATUS_EVALUATED,
                                        "evaluation_score": evaluation_result.get('score'),
                                        "evaluation_feedback": evaluation_result.get('feedback'),
                                        "codeforces_verdict": submission_details.get('verdict'),
                                        "codeforces_submission_id": submission_details.get('id'),
                                        "codeforces_passed_test_count": submission_details.get('passedTestCount'),
                                        "codeforces_time_consumed_millis": submission_details.get('timeConsumedMillis'),
                                        "codeforces_memory_consumed_bytes": submission_details.get('memoryConsumedBytes'),
                                        # Add solved_at if verdict is OK?
                                        "solved_at": timezone.make_aware(datetime.datetime.fromtimestamp(submission_details.get('creationTimeSeconds'))) if submission_details.get('verdict') == 'OK' else None
                                    }
                                    logger.info(f"      -> Evaluation Success: Score={update_data['evaluation_score']}, Verdict={update_data['codeforces_verdict']}")
                                    # Use serializer for validation and saving
                                    serializer = SchedulerSubmissionUpdateSerializer(instance=submission_record, data=update_data, partial=True)
                                    if serializer.is_valid():
                                        serializer.save()
                                        processed_count += 1
                                    else:
                                        logger.error(f"      ERROR saving successful evaluation for S:{student.id}/Q:{question.id}: {serializer.errors}")
                                        AssessmentSubmission.objects.filter(pk=submission_record.pk).update(
                                            status=self.STATUS_ERROR,
                                            evaluation_feedback=f"Internal error saving record: {serializer.errors}"
                                        )
                                        error_count += 1

                                else:
                                    # No suitable submission found this time
                                    if is_past_deadline:
                                        # Deadline passed - Mark as final EVALUATED (failure)
                                        update_data = {
                                            "status": self.STATUS_EVALUATED,
                                            "evaluation_score": 0,
                                            "evaluation_feedback": "No suitable submission found by the deadline.",
                                            "codeforces_verdict": self.VERDICT_NOT_FOUND_DEADLINE,
                                            # Clear other CF fields
                                            "codeforces_submission_id": None,
                                            "codeforces_passed_test_count": None,
                                            "codeforces_time_consumed_millis": None,
                                            "codeforces_memory_consumed_bytes": None,
                                            "solved_at": None,
                                        }
                                        logger.info("      -> No submission found (after deadline). Marking as final EVALUATED failure.")
                                        # Use serializer for validation and saving
                                        serializer = SchedulerSubmissionUpdateSerializer(instance=submission_record, data=update_data, partial=True)
                                        if serializer.is_valid():
                                            serializer.save()
                                            processed_count += 1 # Counts as a processed attempt
                                        else:
                                            logger.error(f"      ERROR saving final failure evaluation for S:{student.id}/Q:{question.id}: {serializer.errors}")
                                            AssessmentSubmission.objects.filter(pk=submission_record.pk).update(
                                                status=self.STATUS_ERROR,
                                                evaluation_feedback=f"Internal error saving record: {serializer.errors}"
                                            )
                                            error_count += 1
                                    else:
                                        # Before deadline - Revert to NOT_ATTEMPTED to allow re-check
                                        AssessmentSubmission.objects.filter(pk=submission_record.pk).update(
                                            status=self.STATUS_NOT_ATTEMPTED
                                            # Keep last_checked_at, clear score/feedback if they existed
                                            # evaluation_score=None, # Ensure these are cleared if reverting
                                            # evaluation_feedback=None,
                                            # codeforces_verdict=None,
                                            # codeforces_submission_id=None,
                                            # ... clear other fields ...
                                        )
                                        reverted_to_not_attempted_count += 1
                                        logger.info("      -> No submission found (before deadline). Reverted to NOT_ATTEMPTED for later check.")
                                        # Increment processed count as an attempt was made
                                        processed_count += 1


                            except Exception as eval_exc:
                                logger.exception(f"      ERROR during evaluation call for S:{student.id}/Q:{question.id}: {eval_exc}")
                                AssessmentSubmission.objects.filter(pk=submission_record.pk).update(
                                    status=self.STATUS_ERROR,
                                    evaluation_feedback=f"Error during Codeforces check: {eval_exc}"
                                )
                                error_count += 1
                        # else: # Skipped check
                            # logger.debug(f"    Skipping CF check for S:{student.id}/Q:{question.id}. Reason: {skip_reason}") # Debug level
                            # pass

                except PlatformProfile.DoesNotExist:
                     # Handled by the check inside the loop
                     pass
                except Exception as student_loop_exc:
                    logger.exception(f"  UNEXPECTED ERROR processing student {student.username} for assessment {assessment.id}: {student_loop_exc}")
                    # Mark any PENDING submissions for this student/assessment as ERROR
                    AssessmentSubmission.objects.filter(
                        student=student, assessment=assessment, status=self.STATUS_PENDING
                    ).update(status=self.STATUS_ERROR, evaluation_feedback=f"Scheduler processing error for student: {student_loop_exc}")
                    error_count += 1

        end_run_time = timezone.now()
        duration = end_run_time - start_run_time
        logger.info("\n--- Scheduler Run Summary ---")
        logger.info(f"Run Duration: {duration}")
        logger.info(f"Assessments Checked: {assessments_to_check.count()}")
        logger.info(f"New Submission Records Created: {created_count}")
        logger.info(f"Codeforces Check Attempts: {processed_count}")
        logger.info(f"Reverted to NOT_ATTEMPTED (pre-deadline): {reverted_to_not_attempted_count}")
        logger.info(f"Skipped (Final Success): {skipped_final_success_count}")
        logger.info(f"Skipped (Final Failure - Post Deadline): {skipped_final_failure_count}")
        logger.info(f"Skipped (Checked Recently): {skipped_recent_count}")
        logger.info(f"Errors Encountered: {error_count}")
        logger.info(f"Scheduler run finished at {end_run_time}.")

        return Response({
            "message": "Submission check process completed.",
            "duration_seconds": duration.total_seconds(),
            "assessments_checked": assessments_to_check.count(),
            "new_records_created": created_count,
            "cf_checks_attempted": processed_count,
            "reverted_to_not_attempted": reverted_to_not_attempted_count,
            "skipped_final_success": skipped_final_success_count,
            "skipped_final_failure": skipped_final_failure_count,
            "skipped_recent": skipped_recent_count,
            "errors": error_count
        }, status=status.HTTP_200_OK)

class MentorAssessmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows mentors to view assignments they created.

    Provides a list of assessments with submission progress counts.
    """
    serializer_class = MentorAssignmentListSerializer
    permission_classes = [IsAuthenticated, IsAssessmentMentorOwner] # Must be logged in AND be a mentor

    def get_queryset(self):
        """
        This view should return a list of all the assessments
        created by the currently authenticated mentor.
        Optimize by prefetching related data and annotating counts.
        """
        user = self.request.user

        # Annotate the counts directly in the queryset for efficiency
        queryset = Assessment.objects.filter(mentor=user).annotate(
            # Count total assigned students
            assigned_students_count_annotation=Count('assigned_students', distinct=True),
            # Count students with at least one successful submission for this assessment
            successful_submission_students_count_annotation=Count(
                'submissions__student', # Count distinct students via the submission relation
                filter=Q(submissions__status='EVALUATED', submissions__codeforces_verdict='OK'),
                distinct=True
            )
        ).select_related('mentor') # Select related mentor in one query

        # Although annotated, prefetching can still be useful if you access
        # the full lists elsewhere or in a detail view serializer later.
        # queryset = queryset.prefetch_related(
        #     Prefetch('assigned_students', queryset=User.objects.only('id')), # Only fetch IDs if that's enough
        #     Prefetch('submissions', queryset=AssessmentSubmission.objects.filter(status='EVALUATED', codeforces_verdict='OK').only('student_id'))
        # )

        return queryset.order_by('-deadline', '-created_at') # Keep ordering