from django.urls import path
from .views import RegisterView, AddPlatformProfileView, VerifyPlatformView, StudentAnalyticsView, MentorStudentAnalyticsView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # Login
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('platform/add/', AddPlatformProfileView.as_view(), name='add_platform'),
    path('platform/verify/', VerifyPlatformView.as_view(), name='verify_platform'),
    path('analytics/student/', StudentAnalyticsView.as_view(), name='student_analytics'),
    path('analytics/mentor/', MentorStudentAnalyticsView.as_view(), name='mentor_analytics'),
]