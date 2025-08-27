from django.contrib import admin
from .models import Course, Enrollment, Profile, Lesson, LessonProgress, Quiz, Question, Assignment, Submission, Certificate

admin.site.register(Course)
admin.site.register(Enrollment)
admin.site.register(Profile)
admin.site.register(Lesson)
admin.site.register(LessonProgress)
admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(Assignment)
admin.site.register(Submission)
admin.site.register(Certificate)