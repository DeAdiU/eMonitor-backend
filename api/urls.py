from django.urls import path
from .views import (AddPlatformProfileView, VerifyPlatformView, StudentAnalyticsView, MentorStudentAnalyticsView, UserRegistrationView, 
    EmailVerificationView, 
    PasswordResetRequestView, 
    PasswordResetConfirmView)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user_registration'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # Login
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('platform/add/', AddPlatformProfileView.as_view(), name='add_platform'),
    path('platform/verify/', VerifyPlatformView.as_view(), name='verify_platform'),
    path('analytics/student/', StudentAnalyticsView.as_view(), name='student_analytics'),
    path('analytics/mentor/', MentorStudentAnalyticsView.as_view(), name='mentor_analytics'),
    path('verify-email/', EmailVerificationView.as_view(), name='email_verification'),
    # Password Reset
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm')
]