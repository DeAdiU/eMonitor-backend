from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .permissions import IsStudent, IsMentor
from .models import User, PlatformProfile, MentorStudentMapping
from .serializers import UserSerializer, PlatformProfileSerializer, MentorStudentMappingSerializer
import requests  # For fetching platform data
from rest_framework.permissions import AllowAny
from .codechef import *
from rest_framework import status
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from .utils import account_activation_token
from django.contrib.auth.tokens import default_token_generator
from .serializers import PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenRefreshView
import logging
from django.http import HttpResponseRedirect

logger = logging.getLogger(__name__)

User = get_user_model()

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
                return HttpResponseRedirect("http://127.0.0.1:8000/")
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
        serializer = PlatformProfileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class VerifyPlatformView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        platform = request.data.get('platform')
        profile_id = request.data.get('profile_id')
        random_string = request.data.get('random_string')

        profile = PlatformProfile.objects.get(user=request.user, platform=platform, profile_id=profile_id)

        # Fetch platform data (pseudo-code; replace with actual API calls)
        if platform == 'codechef':
            response = get_name_display(profile_id)
            if response == random_string:
                profile.is_verified = True
                profile.save()
                return Response({"message": "Verified the profile of Codechef"}, status=200)
        elif platform == 'leetcode':
            response = requests.get(f"https://leetcode.com/{profile_id}/")
            if random_string in response.text:  # Check "about me" section
                profile.is_verified = True
                profile.save()
                return Response({"message": "Verified"}, status=200)

        return Response({"message": "Not verified"}, status=400)

class StudentAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        profiles = PlatformProfile.objects.filter(user=request.user, is_verified=True)
        analytics = {}
        for profile in profiles:
            # Fetch real-time data (pseudo-code)
            if profile.platform == 'codeforces':
                response = requests.get(f"https://codeforces.com/api/user.info?handles={profile.profile_id}")
                analytics[profile.platform] = response.json()
            elif profile.platform == 'leetcode':
                analytics[profile.platform] = {"solved": 100}  # Replace with actual API
        return Response(analytics)

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