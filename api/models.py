# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLES = (
        ('student', 'Student'),
        ('mentor', 'Mentor'),
    )
    role = models.CharField(max_length=10, choices=ROLES)
    enrollment_year = models.IntegerField(null=True, blank=True)  # For students
    graduation_year = models.IntegerField(null=True, blank=True)  # For students
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    is_verified = models.BooleanField(default=False)  # Verified by department

    def __str__(self):
        return self.username

class PlatformProfile(models.Model):
    PLATFORMS = (
        ('codeforces', 'Codeforces'),
        ('leetcode', 'LeetCode'),
        ('codechef', 'CodeChef'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='platforms')
    platform = models.CharField(max_length=20, choices=PLATFORMS, unique=True)
    profile_id = models.CharField(max_length=100)  # e.g., username on platform
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.platform}"

class MentorStudentMapping(models.Model):
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='students', limit_choices_to={'role': 'mentor'})
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentors', limit_choices_to={'role': 'student'})

    class Meta:
        unique_together = ('mentor', 'student')

    def __str__(self):
        return f"{self.mentor.username} -> {self.student.username}"