# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError

class User(AbstractUser):
    ROLES = (
        ('student', 'Student'),
        ('mentor', 'Mentor'),
    )
    role = models.CharField(max_length=10, choices=ROLES)
    # Allow blank/null for flexibility, ensure forms handle validation
    first_name = models.CharField(max_length=150, null=True, blank=True)
    last_name = models.CharField(max_length=150, null=True, blank=True)
    enrollment_year = models.IntegerField(null=True, blank=True)  # For students
    graduation_year = models.IntegerField(null=True, blank=True)  # For students
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    is_verified = models.BooleanField(default=False)  # Verified by department/admin

    def __str__(self):
        full_name = self.get_full_name()
        return f"Student: {full_name} , UserName: {self.username}, id: {self.id}"

class PlatformProfile(models.Model):
    PLATFORMS = (
        ('codeforces', 'Codeforces'),
        # ('leetcode', 'LeetCode'), # Keep if needed later
        # ('codechef', 'CodeChef'), # Keep if needed later
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='platforms')
    platform = models.CharField(max_length=20, choices=PLATFORMS, default='codeforces')
    profile_id = models.CharField(max_length=100, help_text="Your Codeforces handle (case-sensitive)") # e.g., username on platform
    is_verified = models.BooleanField(default=False, help_text="Indicates if the handle ownership is confirmed (future feature)")

    class Meta:
        unique_together = ('user', 'platform') # Ensure a user has only one profile per platform
        verbose_name = "Platform Profile"
        verbose_name_plural = "Platform Profiles"

    def __str__(self):
        return f"{self.user.username} - {self.get_platform_display()} ({self.profile_id})"

class MentorStudentMapping(models.Model):
    # This mapping might be useful for general dashboard views,
    # but Assessment.assigned_students handles assessment-specific assignment.
    mentor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='mentored_students_mapping',
        limit_choices_to={'role': 'mentor'}
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='mentor_mappings',
        limit_choices_to={'role': 'student'}
    )

    class Meta:
        unique_together = ('mentor', 'student')
        verbose_name = "Mentor-Student Mapping"
        verbose_name_plural = "Mentor-Student Mappings"

    def __str__(self):
        return f"Mentor: {self.mentor.username} -> Student: {self.student.username}"

# --- ASSESSMENT MODELS ---

class Assessment(models.Model):
    mentor = models.ForeignKey(
        User,
        on_delete=models.CASCADE, # Or models.SET_NULL if assessment should remain
        related_name='created_assessments',
        limit_choices_to={'role': 'mentor'}
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    preferred_criteria = models.TextField(blank=True, null=True, help_text="Preferred criteria for AI evaluation.")
    # Deadline is crucial for the submission fetching window
    deadline = models.DateTimeField(help_text="The date and time by which the assessment must be completed.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_students = models.ManyToManyField(
        User,
        related_name='assigned_assessments',
        limit_choices_to={'role': 'student'},
        blank=True # Allow creating before assigning
    )
    # Optional: Add overall assessment criteria if needed for evaluation context
    # evaluation_criteria_prompt = models.TextField(
    #     blank=True, null=True,
    #     default="Focus on correctness (OK verdict) and efficiency (low time/memory). Prefer C++ or Python.",
    #     help_text="General guidelines for the AI evaluation (used if question-specific criteria are absent)."
    # )


    class Meta:
        ordering = ['-deadline', '-created_at'] # Order by deadline first, then creation

    def __str__(self):
        return f"Assessment: {self.title} (by {self.mentor.username})"

    @property
    def is_past_deadline(self):
        """Checks if the assessment deadline has passed."""
        return timezone.now() > self.deadline

    def clean(self):
        # Example validation: Deadline must be in the future on creation
        if not self.pk and self.deadline and self.deadline <= timezone.now():
             raise ValidationError({'deadline': 'Deadline must be set in the future.'})
        super().clean()


class Question(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    # Store Codeforces specific identifiers
    contest_id = models.IntegerField(help_text="Codeforces Contest ID (e.g., 1998)")
    problem_index = models.CharField(max_length=10, help_text="Codeforces Problem Index (e.g., 'B', 'A1')")

    # Optional: Store fetched metadata for display/filtering
    title = models.CharField(max_length=255, blank=True, null=True, help_text="Problem title (fetched from Codeforces)")
    link = models.URLField(max_length=500, blank=True, null=True, help_text="Direct link (auto-generated or fetched)")
    tags = models.CharField(max_length=500, blank=True, null=True, help_text="Comma-separated tags (fetched)")
    rating = models.IntegerField(null=True, blank=True, help_text="Problem rating (fetched)")

    points = models.PositiveIntegerField(default=100, help_text="Points awarded for a correct solution")
    # Optional: Add question-specific evaluation criteria override
    # evaluation_criteria_override = models.TextField(blank=True, null=True, help_text="Specific AI evaluation criteria for this question.")

    class Meta:
        ordering = ['assessment', 'id'] # Order by assessment, then creation order
        # Ensure unique problem within an assessment
        unique_together = ('assessment', 'contest_id', 'problem_index')
        verbose_name = "Assessment Question"
        verbose_name_plural = "Assessment Questions"

    def __str__(self):
        display_title = self.title if self.title else f"{self.contest_id}{self.problem_index}"
        return f"{display_title} (Assessment: {self.assessment.title})"

    def save(self, *args, **kwargs):
        # Auto-generate link if contest_id and index are present
        if self.contest_id and self.problem_index and not self.link:
            # Determine if it's a gym contest or regular contest based on ID range (approximation)
            if self.contest_id >= 100000: # Gym contests usually have high IDs
                 self.link = f"https://codeforces.com/gym/{self.contest_id}/problem/{self.problem_index}"
            else:
                 self.link = f"https://codeforces.com/problemset/problem/{self.contest_id}/{self.problem_index}"
                 # Or use /contest/ if it's specifically from a contest context:
                 # self.link = f"https://codeforces.com/contest/{self.contest_id}/problem/{self.problem_index}"
        super().save(*args, **kwargs)

    # TODO: Add a method/signal to fetch title, tags, rating from Codeforces API upon creation/saving
    # def fetch_codeforces_metadata(self): ...


class AssessmentSubmission(models.Model):
    """
    Tracks the status and evaluation result of a student's attempt on a specific
    question within an assessment, updated by the backend scheduler.
    """
    STATUS_CHOICES = (
        ('NOT_ATTEMPTED', 'Not Attempted'), # Initial state
        ('PENDING_EVALUATION', 'Pending Evaluation'), # Scheduler is checking or has triggered check
        ('EVALUATED', 'Evaluated'), # Evaluation complete (check verdict/score for outcome)
        ('ERROR', 'Evaluation Error'), # An error occurred during check/evaluation
    )

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assessment_submissions',
        limit_choices_to={'role': 'student'}
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='submissions' # Allows easy filtering: assessment.submissions.all()
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default='NOT_ATTEMPTED'
    )
    # Store evaluation results
    evaluation_score = models.FloatField(null=True, blank=True, help_text="Score (0-100) from AI/fallback evaluation")
    evaluation_feedback = models.TextField(blank=True, null=True, help_text="Feedback from AI/fallback evaluation")
    codeforces_verdict = models.CharField(max_length=50, blank=True, null=True, help_text="Verdict from Codeforces (e.g., OK, WRONG_ANSWER)")
    codeforces_submission_id = models.BigIntegerField(null=True, blank=True, help_text="ID of the evaluated Codeforces submission")
    codeforces_passed_test_count = models.IntegerField(null=True, blank=True, help_text="Number of tests passed for the evaluated submission")
    codeforces_time_consumed_millis = models.IntegerField(null=True, blank=True)
    codeforces_memory_consumed_bytes = models.BigIntegerField(null=True, blank=True)
    
    solved_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the question was successfully solved (verdict='OK')")
    last_checked_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the backend last checked/updated this status")

    class Meta:
        unique_together = ('student', 'question') # A student has one submission status per question
        ordering = ['assessment', 'student', 'question']
        verbose_name = "Assessment Submission Status"
        verbose_name_plural = "Assessment Submission Statuses"

    def __str__(self):
        return f"{self.student.username} - Q: {self.question.contest_id}{self.question.problem_index} (A: {self.assessment.title}) - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Ensure the question belongs to the assessment
        if self.question_id and self.assessment_id and self.question.assessment_id != self.assessment_id:
            raise ValidationError(f"Question '{self.question}' does not belong to Assessment '{self.assessment}'.")

        # Automatically set solved_at timestamp if status is EVALUATED and verdict is OK
        if self.status == 'EVALUATED' and self.codeforces_verdict == 'OK' and not self.solved_at:
            # Use last_checked_at or now() as an approximation if submission time isn't available
            self.solved_at = self.last_checked_at or timezone.now()

        # Update last_checked_at timestamp automatically on save
        self.last_checked_at = timezone.now()

        super().save(*args, **kwargs)