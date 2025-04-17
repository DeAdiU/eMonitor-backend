from django.urls import path, include
from .views import *
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'assessments', AssessmentViewSet, basename='assessment')
router.register(r'mentor-assessments', MentorAssessmentViewSet, basename='mentor-assessment')

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user_registration'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),  # Login
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('platform/add/', AddPlatformProfileView.as_view(), name='add_platform'),
    path('platform/verify/', VerifyPlatformView.as_view(), name='verify_platform'),
    path('analytics/student/', StudentAnalyticsView.as_view(), name='student_analytics'),
    path('analytics/mentor/', MentorStudentAnalyticsView.as_view(), name='mentor_analytics'),
    path('verify-email/', EmailVerificationView.as_view(), name='email_verification'),
    path('add-mentor/', MentorStudentMappingView.as_view(), name='add_mentor'),
    path('platform/verify/<int:id>/',PlatformProfileDeleteView.as_view(), name='delete_platform'),
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('analytics/mentor/<int:id>/', AnalyticsView.as_view(), name='mentor_analytics'),
    path('get-students/', StudentMentorMappingView.as_view(), name='student_analytics'),
    path('codeforces/random-problems/', SuggestCodeforcesProblemView.as_view(), name='codeforces-random-problems'),
    path('scheduler/check-submissions/', SchedulerCheckSubmissionsView.as_view(), name='scheduler-check-submissions'),
    path('', include(router.urls)),
]