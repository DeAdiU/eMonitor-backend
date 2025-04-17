from rest_framework import permissions

class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'student'

class IsMentor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'mentor'
    
class IsAssessmentMentorOwner(permissions.BasePermission):
    """Allows access only to the mentor who created the assessment."""
    def has_object_permission(self, request, view, obj):
        # Instance must have an attribute named `mentor`.
        return obj.mentor == request.user

class IsAssignedStudentOrMentorOwnerReadOnly(permissions.BasePermission):
    """
    Allows mentor owner full access.
    Allows assigned students read-only access.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to mentor owner or assigned students
        if request.method in permissions.SAFE_METHODS:
            is_owner = obj.mentor == request.user
            is_assigned = request.user in obj.assigned_students.all()
            return is_owner or is_assigned
        # Write permissions are only allowed to the mentor owner.
        return obj.mentor == request.user

class IsSubmissionStudentOwnerOrMentorOwnerReadOnly(permissions.BasePermission):
    """
    Allows student owner or assessment mentor owner read-only access.
    No direct write access via API (updated by scheduler).
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            is_student_owner = obj.student == request.user
            is_mentor_owner = obj.assessment.mentor == request.user
            return is_student_owner or is_mentor_owner
        # Deny write access through this permission
        return False

# Permission for the scheduler endpoint (use API Key or other secure method)
class HasSchedulerAPIKey(permissions.BasePermission):
    def has_permission(self, request, view):
        # Example: Check for a specific header or query parameter
        # IMPORTANT: Use a secure, environment-variable-stored key
        scheduler_key = request.headers.get('X-Scheduler-API-Key')
        # Replace 'YOUR_SECRET_SCHEDULER_KEY' with your actual key from settings/env
        return scheduler_key == 'YOUR_SECRET_SCHEDULER_KEY'