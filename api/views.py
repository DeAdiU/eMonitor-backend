from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .permissions import IsStudent, IsMentor
from .models import User, PlatformProfile, MentorStudentMapping
from .serializers import UserSerializer, PlatformProfileSerializer, MentorStudentMappingSerializer
import requests  # For fetching platform data
from rest_framework.permissions import AllowAny
from .codechef import *

class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

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