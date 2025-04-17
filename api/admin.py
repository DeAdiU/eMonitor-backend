from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(User)
admin.site.register(PlatformProfile)
admin.site.register(MentorStudentMapping) 
admin.site.register(Assessment)
admin.site.register(AssessmentSubmission)
admin.site.register(Question)
