from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse
from .models import Course, Enrollment, Profile, Lesson, LessonProgress, Quiz, Question, Assignment, Submission, Certificate
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
import datetime
import re

def home(request):
    return render(request, 'home.html')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('lms:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')

def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        role = request.POST['role']
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            Profile.objects.create(user=user, role=role)
            login(request, user)
            return redirect('lms:dashboard')
    return render(request, 'register.html')

def user_logout(request):
    logout(request)
    return redirect('lms:home')

def check_course_completion(student, course):
    # Check lessons
    lessons = Lesson.objects.filter(course=course)
    total_lessons = lessons.count()
    viewed_lessons = LessonProgress.objects.filter(student=student, lesson__in=lessons, viewed=True).count()
    lessons_completed = total_lessons == viewed_lessons if total_lessons > 0 else True

    # Check assignments
    assignments = Assignment.objects.filter(course=course)
    total_assignments = assignments.count()
    submitted_assignments = Submission.objects.filter(student=student, assignment__in=assignments).count()
    assignments_completed = total_assignments == submitted_assignments if total_assignments > 0 else True

    # Check quizzes (at least one quiz must be passed with 70% or higher)
    quizzes = Quiz.objects.filter(course=course)
    quiz_passed = False
    for quiz in quizzes:
        score = 0
        total = quiz.questions.count()
        if total > 0:
            for question in quiz.questions.all():
                # Note: We don't store quiz answers, so we can't check past quiz scores.
                # For now, rely on the logic in quiz_take to set is_completed.
                pass
    # We'll rely on the existing certificate.is_completed for quiz completion

    certificate = Certificate.objects.get(student=student, course=course)
    quizzes_completed = certificate.is_completed  # Set by quiz_take

    # Course is completed if all conditions are met
    return lessons_completed and assignments_completed and quizzes_completed

@login_required
def dashboard(request):
    try:
        profile = Profile.objects.get(user=request.user)
        is_instructor = profile.role == 'instructor'
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    if is_instructor:
        courses = Course.objects.filter(instructor=request.user)
    else:
        courses = Course.objects.all()
        enrollments = Enrollment.objects.filter(student=request.user)
        enrolled_course_ids = enrollments.values_list('course_id', flat=True)
        certificates = Certificate.objects.filter(student=request.user)
        
        # Add quizzes, assignments, and lessons for each enrolled course
        enrolled_courses = Course.objects.filter(id__in=enrolled_course_ids)
        course_details = []
        for course in enrolled_courses:
            lessons = Lesson.objects.filter(course=course)
            quizzes = Quiz.objects.filter(course=course)
            assignments = Assignment.objects.filter(course=course)
            course_details.append({
                'course': course,
                'lessons': lessons,
                'quizzes': quizzes,
                'assignments': assignments,
            })
        
        # Update certificate completion status
        for certificate in certificates:
            if not certificate.is_completed:
                if check_course_completion(request.user, certificate.course):
                    certificate.is_completed = True
                    certificate.save()
        
        return render(request, 'dashboard.html', {
            'courses': courses,
            'enrollments': enrollments,
            'enrolled_course_ids': enrolled_course_ids,
            'is_instructor': False,
            'certificates': certificates,
            'course_details': course_details,
        })
    return render(request, 'dashboard.html', {
        'courses': courses,
        'is_instructor': True
    })

@login_required
def instructor_dashboard(request):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    if profile.role != 'instructor':
        messages.error(request, 'Only instructors can access this dashboard.')
        return redirect('lms:dashboard')
    
    courses = Course.objects.filter(instructor=request.user)
    course_progress = []
    for course in courses:
        enrollments = Enrollment.objects.filter(course=course)
        students = [e.student for e in enrollments]
        progress = []
        for student in students:
            lessons = Lesson.objects.filter(course=course)
            lesson_progress = LessonProgress.objects.filter(student=student, lesson__in=lessons)
            lessons_viewed = lesson_progress.filter(viewed=True).count()
            total_lessons = lessons.count()
            
            quizzes = Quiz.objects.filter(course=course)
            quiz_scores = []
            for quiz in quizzes:
                score = 0
                total = quiz.questions.count()
                if total > 0:
                    for question in quiz.questions.all():
                        pass
                    score_percent = (score / total * 100) if total > 0 else 0
                    quiz_scores.append({'title': quiz.title, 'score': score_percent})
            
            assignments = Assignment.objects.filter(course=course)
            submissions = Submission.objects.filter(student=student, assignment__in=assignments)
            submitted_assignments = submissions.count()
            total_assignments = assignments.count()
            
            progress.append({
                'student': student,
                'lessons_viewed': lessons_viewed,
                'total_lessons': total_lessons,
                'quiz_scores': quiz_scores,
                'submitted_assignments': submitted_assignments,
                'total_assignments': total_assignments,
            })
        
        course_progress.append({
            'course': course,
            'enrollment_count': enrollments.count(),
            'student_progress': progress,
        })
    
    return render(request, 'instructor_dashboard.html', {
        'course_progress': course_progress,
    })

@login_required
def course_list(request):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    courses = Course.objects.all()
    enrollments = Enrollment.objects.filter(student=request.user)
    enrolled_course_ids = enrollments.values_list('course_id', flat=True)
    return render(request, 'course_list.html', {
        'courses': courses,
        'enrolled_course_ids': enrolled_course_ids,
        'is_instructor': profile.role == 'instructor'
    })

@login_required
def course_create(request):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    if profile.role != 'instructor':
        messages.error(request, 'Only instructors can create courses.')
        return redirect('lms:course_list')
    if request.method == 'POST':
        title = request.POST['title']
        description = request.POST['description']
        Course.objects.create(title=title, description=description, instructor=request.user)
        messages.success(request, 'Course created successfully.')
        return redirect('lms:course_list')
    return render(request, 'course_create.html')

@login_required
def enroll(request, course_id):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    course = get_object_or_404(Course, id=course_id)
    if profile.role == 'instructor':
        messages.error(request, 'Instructors cannot enroll in courses.')
        return redirect('lms:course_list')
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        Enrollment.objects.create(student=request.user, course=course)
        Certificate.objects.create(student=request.user, course=course)
        messages.success(request, f'Enrolled in {course.title} successfully.')
    else:
        messages.info(request, 'You are already enrolled in this course.')
    return redirect('lms:course_list')

@login_required
def lesson_create(request, course_id):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    course = get_object_or_404(Course, id=course_id)
    if profile.role != 'instructor' or course.instructor != request.user:
        messages.error(request, 'Only the course instructor can add lessons.')
        return redirect('lms:course_list')
    if request.method == 'POST':
        if 'title' not in request.POST or not request.POST['title']:
            messages.error(request, 'Lesson title is required.')
            return render(request, 'lesson_create.html', {'course': course})
        if 'video_url' not in request.POST or not request.POST['video_url']:
            messages.error(request, 'Video URL is required.')
            return render(request, 'lesson_create.html', {'course': course})
        title = request.POST['title']
        video_url = request.POST['video_url']
        Lesson.objects.create(course=course, title=title, video_url=video_url)
        messages.success(request, 'Lesson created successfully.')
        return redirect('lms:course_list')
    return render(request, 'lesson_create.html', {'course': course})

@login_required
def lesson_detail(request, course_id, lesson_id):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    lesson = get_object_or_404(Lesson, id=lesson_id, course_id=course_id)
    if profile.role == 'student' and not Enrollment.objects.filter(student=request.user, course=lesson.course).exists():
        messages.error(request, 'You must enroll in the course to view lessons.')
        return redirect('lms:course_list')
    
    if profile.role == 'student':
        LessonProgress.objects.update_or_create(
            student=request.user,
            lesson=lesson,
            defaults={'viewed': True}
        )
        # Check course completion after viewing a lesson
        certificate = Certificate.objects.get(student=request.user, course=lesson.course)
        if not certificate.is_completed:
            if check_course_completion(request.user, lesson.course):
                certificate.is_completed = True
                certificate.save()
    
    embed_url = lesson.video_url
    youtube_regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)'
    match = re.match(youtube_regex, lesson.video_url)
    if match:
        video_id = match.group(1)
        embed_url = f"https://www.youtube.com/embed/{video_id}"
    else:
        messages.warning(request, 'Invalid YouTube URL. Please ensure the video is embeddable.')
    
    return render(request, 'lesson_detail.html', {'lesson': lesson, 'embed_url': embed_url})

@login_required
def quiz_create(request, course_id):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    course = get_object_or_404(Course, id=course_id)
    if profile.role != 'instructor' or course.instructor != request.user:
        messages.error(request, 'Only the course instructor can create quizzes.')
        return redirect('lms:course_list')
    if request.method == 'POST':
        quiz_title = request.POST['title']
        quiz = Quiz.objects.create(course=course, title=quiz_title)
        for i in range(1, int(request.POST.get('question_count', 0)) + 1):
            if f'question_text_{i}' in request.POST:
                Question.objects.create(
                    quiz=quiz,
                    text=request.POST[f'question_text_{i}'],
                    option1=request.POST[f'option1_{i}'],
                    option2=request.POST[f'option2_{i}'],
                    option3=request.POST[f'option3_{i}'],
                    option4=request.POST[f'option4_{i}'],
                    correct_option=int(request.POST[f'correct_option_{i}'])
                )
        messages.success(request, 'Quiz created successfully.')
        return redirect('lms:course_list')
    return render(request, 'quiz_create.html', {'course': course})

@login_required
def quiz_take(request, course_id, quiz_id):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    quiz = get_object_or_404(Quiz, id=quiz_id, course_id=course_id)
    if profile.role == 'instructor':
        messages.error(request, 'Instructors cannot take quizzes.')
        return redirect('lms:course_list')
    if not Enrollment.objects.filter(student=request.user, course=quiz.course).exists():
        messages.error(request, 'You must enroll in the course to take quizzes.')
        return redirect('lms:course_list')
    
    if request.method == 'POST':
        score = 0
        total = quiz.questions.count()
        for question in quiz.questions.all():
            selected = int(request.POST.get(f'question_{question.id}', 0))
            if selected == question.correct_option:
                score += 1
        certificate = Certificate.objects.get(student=request.user, course=quiz.course)
        if score / total >= 0.7:
            certificate.is_completed = True  # Temporarily set to True for quiz passing
            certificate.save()
            # Re-check overall completion
            if check_course_completion(request.user, quiz.course):
                certificate.is_completed = True
            else:
                certificate.is_completed = False
            certificate.save()
        messages.success(request, f'Your score: {score}/{total}.')
        return redirect('lms:dashboard')  # Redirect to dashboard to see updated certificate status
    return render(request, 'quiz_take.html', {'quiz': quiz})

@login_required
def assignment_create(request, course_id):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    course = get_object_or_404(Course, id=course_id)
    if profile.role != 'instructor' or course.instructor != request.user:
        messages.error(request, 'Only the course instructor can create assignments.')
        return redirect('lms:course_list')
    if request.method == 'POST':
        title = request.POST['title']
        description = request.POST['description']
        Assignment.objects.create(course=course, title=title, description=description)
        messages.success(request, 'Assignment created successfully.')
        return redirect('lms:course_list')
    return render(request, 'assignment_create.html', {'course': course})

@login_required
def assignment_submit(request, course_id, assignment_id):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    assignment = get_object_or_404(Assignment, id=assignment_id, course_id=course_id)
    if profile.role == 'instructor':
        messages.error(request, 'Instructors cannot submit assignments.')
        return redirect('lms:course_list')
    if not Enrollment.objects.filter(student=request.user, course=assignment.course).exists():
        messages.error(request, 'You must enroll in the course to submit assignments.')
        return redirect('lms:course_list')
    
    if request.method == 'POST':
        if 'file' in request.FILES:
            Submission.objects.create(
                assignment=assignment,
                student=request.user,
                file=request.FILES['file']
            )
            messages.success(request, 'Assignment submitted successfully.')
            # Check course completion after submission
            certificate = Certificate.objects.get(student=request.user, course=assignment.course)
            if not certificate.is_completed:
                if check_course_completion(request.user, assignment.course):
                    certificate.is_completed = True
                    certificate.save()
        else:
            messages.error(request, 'Please upload a file.')
        return redirect('lms:dashboard')  # Redirect to dashboard to see updated certificate status
    return render(request, 'assignment_submit.html', {'assignment': assignment})

@login_required
def certificate_view(request, certificate_id):
    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        messages.error(request, 'User profile not found. Please re-register.')
        return redirect('lms:register')
    
    certificate = get_object_or_404(Certificate, id=certificate_id, student=request.user)
    if not certificate.is_completed:
        messages.error(request, 'Course not completed yet.')
        return redirect('lms:dashboard')
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Custom styles
    header_style = ParagraphStyle(
        name='Header',
        fontName='Helvetica-Bold',
        fontSize=30,
        alignment=1,  # Center
        spaceAfter=20,
        textColor=colors.darkblue
    )
    title_style = ParagraphStyle(
        name='Title',
        fontName='Helvetica-Bold',
        fontSize=24,
        alignment=1,
        spaceAfter=20
    )
    normal_style = ParagraphStyle(
        name='Normal',
        fontName='Helvetica',
        fontSize=14,
        alignment=1,
        spaceAfter=10
    )
    small_style = ParagraphStyle(
        name='Small',
        fontName='Helvetica',
        fontSize=10,
        alignment=1,
        spaceAfter=10
    )
    signature_style = ParagraphStyle(
        name='Signature',
        fontName='Helvetica-Oblique',
        fontSize=14,
        alignment=1,
        spaceBefore=20,
        textColor=colors.black
    )

    # Custom page layout with borders
    doc.leftMargin = doc.rightMargin = doc.topMargin = doc.bottomMargin = 0.75 * inch
    def draw_page_frame(canvas, doc):
        # Outer border
        canvas.setLineWidth(3)
        canvas.setStrokeColor(colors.black)
        canvas.rect(0.5 * inch, 0.5 * inch, letter[0] - 1 * inch, letter[1] - 1 * inch)
        # Inner border (decorative)
        canvas.setLineWidth(1)
        canvas.setStrokeColor(colors.grey)
        canvas.rect(0.75 * inch, 0.75 * inch, letter[0] - 1.5 * inch, letter[1] - 1.5 * inch)

    # Content
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph("Docebo", header_style))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph("Certificate of Completion", title_style))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph("This is to certify that", normal_style))
    elements.append(Paragraph(f"{request.user.username}", normal_style))
    elements.append(Paragraph("has successfully completed the course", normal_style))
    elements.append(Paragraph(f"{certificate.course.title}", normal_style))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Instructor: {certificate.course.instructor.username}", normal_style))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Date of Issue: {certificate.issued_at.strftime('%Y-%m-%d')}", small_style))
    elements.append(Paragraph(f"Certificate ID: {certificate.id}", small_style))
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(f"{certificate.course.instructor.username}", signature_style))
    elements.append(Paragraph("Instructor", small_style))

    # Build PDF
    doc.build(elements, onFirstPage=draw_page_frame, onLaterPages=draw_page_frame)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="certificate_{certificate_id}.pdf"'
    return response