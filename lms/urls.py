from django.urls import path
from . import views

app_name = 'lms'  # Added to match the namespace in django_lms/urls.py

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.user_login, name='user_login'),
    path('register/', views.register, name='register'),
    path('logout/', views.user_logout, name='user_logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('instructor_dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    path('courses/', views.course_list, name='course_list'),
    path('courses/create/', views.course_create, name='course_create'),
    path('enroll/<int:course_id>/', views.enroll, name='enroll'),
    path('courses/<int:course_id>/lessons/create/', views.lesson_create, name='lesson_create'),
    path('courses/<int:course_id>/lessons/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('courses/<int:course_id>/quizzes/create/', views.quiz_create, name='quiz_create'),
    path('courses/<int:course_id>/quizzes/<int:quiz_id>/', views.quiz_take, name='quiz_take'),
    path('courses/<int:course_id>/assignments/create/', views.assignment_create, name='assignment_create'),
    path('courses/<int:course_id>/assignments/<int:assignment_id>/submit/', views.assignment_submit, name='assignment_submit'),
    path('certificates/<int:certificate_id>/', views.certificate_view, name='certificate_view'),
]