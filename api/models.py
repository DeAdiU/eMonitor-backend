# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, UniqueConstraint # Import Q and UniqueConstraint
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
        ('leetcode', 'LeetCode'), # Keep if needed later
        ('codechef', 'CodeChef'), # Keep if needed later
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
        'Assessment',
        on_delete=models.CASCADE,
        related_name='questions'
    )
    PLATFORM_CHOICES = (
        ('codeforces', 'Codeforces'),
        ('codechef', 'CodeChef'),
        # Add other platforms here if needed
    )
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        default='codeforces', # Set a default if desired
        help_text="The platform hosting this question."
    )
    # Store Codeforces-specific identifiers, nullable for CodeChef
    contest_id = models.IntegerField(
        null=True,
        blank=True, # Allow blank for non-Codeforces platforms
        help_text="Codeforces Contest ID (e.g., 1998). Leave blank for CodeChef."
    )
    problem_index = models.CharField(
        max_length=10, # Keep reasonably short
        help_text="Platform-specific Problem Index/Code (e.g., 'B', 'A1', 'START01')."
    )

    # Optional metadata (remains the same)
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Problem title (fetched from platform)"
    )
    link = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Direct link (auto-generated or fetched)"
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Comma-separated tags (fetched)"
    )
    rating = models.IntegerField(
        null=True,
        blank=True,
        help_text="Problem rating (fetched)"
    )

    points = models.PositiveIntegerField(
        default=100,
        help_text="Points awarded for a correct solution"
    )

    def clean(self):
        """Add basic platform-specific validation."""
        super().clean() # Call parent clean method
        if self.platform == 'codeforces':
            # Ensure contest_id is provided for Codeforces
            if self.contest_id is None:
                raise ValidationError({'contest_id': "Contest ID is required for Codeforces questions."})
        elif self.platform == 'codechef':
            # Optionally ensure contest_id is *not* provided for CodeChef
            if self.contest_id is not None:
                 # Decide: raise error or just nullify it? Nullifying might be friendlier.
                 # raise ValidationError({'contest_id': "Contest ID should be blank for CodeChef questions."})
                 self.contest_id = None # Silently correct it

    def save(self, *args, **kwargs):
        """Auto-generate link based on platform if not already set."""
        # Run clean() before saving if desired (optional, depends on workflow)
        # self.full_clean() # Uncomment if you want validation on every save
        if not self.link: # Only generate if link is not manually set
            if self.platform == 'codeforces' and self.contest_id and self.problem_index:
                # Codeforces link generation
                contest_id_str = str(self.contest_id)
                # Check if it looks like a gym contest ID (typically >= 100000)
                if len(contest_id_str) >= 6 and contest_id_str.startswith('10'): # Simple heuristic for gym
                     self.link = f"https://codeforces.com/gym/{self.contest_id}/problem/{self.problem_index.upper()}"
                else: # Regular contest
                     self.link = f"https://codeforces.com/problemset/problem/{self.contest_id}/{self.problem_index.upper()}"
            elif self.platform == 'codechef' and self.problem_index:
                # CodeChef link generation (uses problem code directly)
                # Example: https://www.codechef.com/problems/FLOW001
                # Example: https://www.codechef.com/submit/START120A (for contest problems during contest)
                # Using the general /problems/ link is usually safer for persistence
                self.link = f"https://www.codechef.com/problems/{self.problem_index.upper()}"
            # Add elif blocks for other platforms if needed

        super().save(*args, **kwargs) # Call the "real" save() method.

    class Meta:
        ordering = ['assessment', 'id']
        verbose_name = "Assessment Question"
        verbose_name_plural = "Assessment Questions"
        constraints = [
            # Unique constraint for Codeforces: (assessment, platform, contest_id, problem_index)
            UniqueConstraint(
                fields=['assessment', 'platform', 'contest_id', 'problem_index'],
                condition=Q(platform='codeforces'), # Apply only when platform is 'codeforces'
                name='unique_assessment_codeforces_question'
            ),
            # Unique constraint for CodeChef: (assessment, platform, problem_index)
            # contest_id should be NULL for CodeChef, so it won't conflict with the CF constraint
            UniqueConstraint(
                fields=['assessment', 'platform', 'problem_index'],
                condition=Q(platform='codechef'), # Apply only when platform is 'codechef'
                name='unique_assessment_codechef_question'
            ),
            # Add constraints for other platforms if needed
        ]

    def __str__(self):
        platform_name = self.get_platform_display()
        identifier = f"{self.contest_id}{self.problem_index}" if self.platform == 'codeforces' else self.problem_index
        display_title = self.title if self.title else f"Problem {identifier}"
        return f"{display_title} ({platform_name}, Assessment: {self.assessment.title})"

class AssessmentSubmission(models.Model):
    # ... (Existing fields: student, question, assessment, status) ...
    STATUS_CHOICES = (
        ('NOT_ATTEMPTED', 'Not Attempted'),
        ('PENDING_EVALUATION', 'Pending Evaluation'),
        ('EVALUATED', 'Evaluated'),
        ('ERROR', 'Evaluation Error'),
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
        related_name='submissions'
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default='NOT_ATTEMPTED'
    )

    # --- Evaluation Results ---
    evaluation_score = models.FloatField(null=True, blank=True, help_text="Score (0-100) based on verdict/tests/AI")
    evaluation_feedback = models.TextField(blank=True, null=True, help_text="Feedback from evaluation")

    # --- Platform-Specific Data ---
    # Renaming these might be good long-term if supporting multiple platforms,
    # but functionally they work for storing CodeChef data too.
    codeforces_verdict = models.CharField(max_length=50, blank=True, null=True, help_text="Verdict from Platform (e.g., AC, WA, TLE)")
    codeforces_submission_id = models.BigIntegerField(null=True, blank=True, help_text="ID of the evaluated platform submission")
    codeforces_passed_test_count = models.IntegerField(null=True, blank=True, help_text="Number of tests passed")
    codeforces_time_consumed_millis = models.IntegerField(null=True, blank=True)
    codeforces_memory_consumed_bytes = models.BigIntegerField(null=True, blank=True)

    # --- NEW: Submitted Code ---
    submitted_code = models.TextField(
        blank=True,
        null=True,
        help_text="The source code submitted by the student."
    )

    # --- NEW: Plagiarism Score ---
    # Using PositiveIntegerField assuming a score like 0-100. Use FloatField if it's 0.0-1.0.
    plagiarism_score = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Calculated plagiarism score (e.g., 0-100), if available."
        # Add validators=[MinValueValidator(0), MaxValueValidator(100)] if desired
    )
    # Optional: Add a field for plagiarism report details/link if needed later
    # plagiarism_details = models.TextField(blank=True, null=True)

    # --- Timestamps ---
    solved_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the question was successfully solved (verdict='AC')")
    last_checked_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the backend last checked/updated this status")


    class Meta:
        unique_together = ('student', 'question')
        ordering = ['assessment', 'student', 'question']
        verbose_name = "Assessment Submission Status"
        verbose_name_plural = "Assessment Submission Statuses"

    def __str__(self):
        q = self.question
        identifier = f"{q.contest_id}{q.problem_index}" if q.platform == 'codeforces' else q.problem_index
        return f"{self.student.username} - Q: {identifier} ({q.get_platform_display()}) (A: {self.assessment.title}) - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # --- Platform Enforcement (CodeChef Only) ---
        if self.question_id and self.question.platform != 'codechef':
            raise ValidationError(
                f"Submissions are only allowed for CodeChef questions. "
                f"Question '{self.question}' is on platform '{self.question.platform}'."
            )

        # --- Other Validations/Logic ---
        if self.question_id and self.assessment_id and self.question.assessment_id != self.assessment_id:
            raise ValidationError(f"Question '{self.question}' does not belong to Assessment '{self.assessment}'.")

        # Set solved_at based on verdict (Assuming 'AC' for Accepted on CodeChef)
        # Adjust 'OK' to 'AC' or whatever CodeChef's accepted verdict string is.
        accepted_verdict = 'AC' # Or 'OK', check CodeChef's actual verdict string
        if self.status == 'EVALUATED' and self.codeforces_verdict == accepted_verdict and not self.solved_at:
            self.solved_at = self.last_checked_at or timezone.now()
        # If verdict changes away from accepted, maybe clear solved_at? Optional.
        # elif self.status == 'EVALUATED' and self.codeforces_verdict != accepted_verdict and self.solved_at:
        #     self.solved_at = None

        self.last_checked_at = timezone.now()

        super().save(*args, **kwargs)