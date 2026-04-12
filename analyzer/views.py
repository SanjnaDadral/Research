
import logging
import os
import time
import re
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Avg
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.conf import settings
from .rag_utils import rag_pipeline
from groq import Groq

from .models import Document, AnalysisResult, PlagiarismCheck, AnalysisFeedback, ComparisonResult
from .plagiarism import local_library_similarity
from .forms import DocumentUploadForm, CustomRegistrationForm
from .ml_model import ml_processor
from .pdf_processor import pdf_processor
from .url_scraper import url_scraper
from .export_manager import export_manager

logger = logging.getLogger(__name__)

ANALYSIS_TEXT_MAX = int(os.getenv("ANALYSIS_TEXT_CAP", "50000"))
TITLE_SAMPLE_CHARS = int(os.getenv("TITLE_SAMPLE_CHARS", "12000"))
MAX_PDF_UPLOAD_BYTES = int(os.getenv("MAX_PDF_UPLOAD_MB", "45")) * 1024 * 1024
MAX_PDF_STORE_BYTES = int(os.getenv("MAX_STORE_PDF_MB", "16")) * 1024 * 1024


# =========================
# 🔥 GROQ AI FUNCTION
# =========================
def analyze_text_with_groq(text):
    client = Groq(api_key=settings.GROQ_API_KEY)

    prompt = f"""
    Analyze the following research paper and provide a comprehensive JSON extraction.
    Be extremely thorough in identifying all components.

    Provide:
    - summary: A clear, multi-sentence executive summary (80-120 words).
    - abstract: The original or reconstructed abstract.
    - keywords: Exhaustive list of 8-15 technical keywords.
    - methodology: Detailed list of mathematical models, algorithms, or experimental setups used.
    - technologies: Extensive list of software, libraries, hardware, and physical tools mentioned.
    - goal: The primary research objective or hypothesis.
    - impact: Potential contributions to the field and real-world applications.
    - research_gaps: A list of 3-5 limitations or future work areas mentioned.
    - conclusion: A summary of the final findings.
    - datasets: List of any public or private datasets mentioned.
    - authors: Full names of all identified authors.
    - publication_year: The year of publication (4 digits).

    TEXT:
    {text[:20000]}
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Return only valid JSON object, no markdown formatting."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
    )

    content = response.choices[0].message.content
    
    # Clean up JSON - remove markdown code blocks if present
    content = content.strip()
    if content.startswith('```'):
        content = content.split('```')[1]
        if content.startswith('json'):
            content = content[4:]
        content = content.strip()
    if content.endswith('```'):
        content = content[:-3].strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error: {e}, content: {content[:200]}")
        data = {
            "summary": content[:500] if content else "",
            "abstract": "",
            "keywords": [],
            "methodology": [],
            "technologies": [],
            "goal": "",
            "impact": "",
            "authors": [],
            "publication_year": ""
        }

    # Add required stats
    data["statistics"] = {
        "word_count": len(text.split()),
        "unique_words": len(set(text.split()))
    }

    return data


# =========================
# VALIDATE PDF
# =========================
def validate_pdf_file(file):
    if not file:
        return False, "No file provided"

    if not file.name.lower().endswith('.pdf'):
        return False, "Only PDF files allowed"

    if file.size > MAX_PDF_UPLOAD_BYTES:
        return False, "File too large"

    return True, None


# =========================
# HOME
# =========================
def home(request):
    form = DocumentUploadForm()
    docs = []
    if request.user.is_authenticated:
        docs = Document.objects.filter(user=request.user).order_by('-created_at')[:6]

    return render(request, 'analyzer/home.html', {'form': form, 'recent_docs': docs})


# =========================
# LOGIN
# =========================
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard')

    return render(request, 'analyzer/login.html', {'form': form})


# =========================
# REGISTER
# =========================
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = CustomRegistrationForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('dashboard')

    return render(request, 'analyzer/register.html', {'form': form})


# =========================
# LOGOUT
# =========================
@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect('home')


# =========================
# 🔥 MAIN ANALYSIS (UPDATED)
# =========================
# @require_http_methods(["POST"])
# def analyze_document(request):
#     if not request.user.is_authenticated:
#         return JsonResponse({'error': 'Login required'}, status=401)

#     try:
#         uploaded_file = request.FILES.get('pdf_file')

#         is_valid, error = validate_pdf_file(uploaded_file)
#         if not is_valid:
#             return JsonResponse({'error': error}, status=400)

#         # Extract text
#         result = pdf_processor.extract_text(uploaded_file)
#         if not result.get('success'):
#             return JsonResponse({'error': 'PDF extraction failed'}, status=400)

#         content = result.get('text', '')[:ANALYSIS_TEXT_MAX]

#         # Save document
#         document = Document.objects.create(
#             user=request.user,
#             title="Analyzed Document",
#             content=content,
#             word_count=len(content.split())
#         )

#         # =========================
#         # 🔥 GROQ + FALLBACK ML
#         # =========================
#         try:
#             analysis_data = analyze_text_with_groq(content)
#         except Exception as e:
#             logger.warning(f"Groq failed: {e}")
#             analysis_data = ml_processor.full_analysis(content)

#         # Plagiarism
#         plagiarism = local_library_similarity(document.id, content, user=request.user)

#         PlagiarismCheck.objects.create(
#             document=document,
#             similarity_score=plagiarism.get("similarity_percent", 0) / 100.0,
#         )

#         # Save analysis
#         analysis = AnalysisResult.objects.create(
#             document=document,
#             summary=analysis_data.get('summary', ''),
#             abstract=analysis_data.get('abstract', ''),
#             keywords=analysis_data.get('keywords', []),
#             methodology=analysis_data.get('methodology', []),
#             technologies=analysis_data.get('technologies', []),
#             goal=analysis_data.get('goal', ''),
#             impact=analysis_data.get('impact', ''),
#             publication_year=analysis_data.get('publication_year', ''),
#             authors=analysis_data.get('authors', []),
#             word_count=analysis_data.get('statistics', {}).get('word_count', 0),
#             unique_words=analysis_data.get('statistics', {}).get('unique_words', 0),
#         )

#         return JsonResponse({
#             'success': True,
#             'redirect_url': f'/result/{document.id}/'
#         })

#     except Exception as e:
#         logger.error(e, exc_info=True)
#         return JsonResponse({'error': str(e)}, status=500)
def analyze_document(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required'}, status=401)

    if request.method != "POST":
        return JsonResponse({'error': 'Invalid request'}, status=400)

def analyze_document(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required'}, status=401)

    try:
        input_type = request.POST.get('input_type', 'pdf')
        content = None
        title = "Analyzed Document"
        document_input_type = 'pdf'
        url_source = None

        # PDF INPUT
        if input_type == 'pdf':
            uploaded_file = request.FILES.get('pdf_file')
            is_valid, error = validate_pdf_file(uploaded_file)
            if not is_valid:
                return JsonResponse({'error': error}, status=400)
            result = pdf_processor.extract_text(uploaded_file)
            if not result.get('success'):
                return JsonResponse({'error': 'PDF extraction failed'}, status=400)
            content = result.get('text', '')[:ANALYSIS_TEXT_MAX]
            document_input_type = 'pdf'
            
            # Extract images from PDF for the visual assets
            try:
                uploaded_file.seek(0)
                extracted_images_data = pdf_processor.extract_images(uploaded_file, max_images=20)
            except Exception as e:
                logger.warning(f"Image extraction failed: {e}")
                extracted_images_data = []

        elif input_type == 'text':
            extracted_images_data = []
            content = request.POST.get('text_content', '').strip()[:ANALYSIS_TEXT_MAX]
            if not content:
                return JsonResponse({'error': 'No text content provided'}, status=400)
            document_input_type = 'text'

        elif input_type == 'url':
            extracted_images_data = []
            url_input = request.POST.get('url_input', '').strip()
            if not url_input:
                return JsonResponse({'error': 'No URL provided'}, status=400)
            try:
                result = url_scraper.scrape(url_input)
                if not result.get('success'):
                    return JsonResponse({'error': f'Failed to fetch URL: {result.get("error", "Unknown error")}'}, status=400)
                content = result.get('text', '')[:ANALYSIS_TEXT_MAX]
                url_source = url_input
                document_input_type = 'url'
            except Exception as e:
                logger.error(f"URL scraping error: {e}")
                return JsonResponse({'error': f'Failed to fetch URL content: {str(e)}'}, status=400)
        else:
            return JsonResponse({'error': 'Invalid input type'}, status=400)

        if not content or len(content.strip()) < 50:
            return JsonResponse({'error': 'Not enough text content for analysis'}, status=400)

        # EXTRACT TITLE
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 5 and len(line) < 200:
                title = line[:150]
                break
        if not title or title == "Analyzed Document":
            words = content.split()
            title = ' '.join(words[:10]) if words else "Analyzed Document"


        # SAVE DOCUMENT
        document = Document.objects.create(
            user=request.user,
            input_type=document_input_type,
            title=title,
            content=content,
            url=url_source,
            word_count=len(content.split())
        )
  
        # GROQ API ANALYSIS (Primary extraction)
        try:
            analysis_data = analyze_text_with_groq(content)
        except Exception as e:
            logger.warning(f"Groq API failed: {e}, falling back to local ML")
            analysis_data = ml_processor.full_analysis(content)

        # PLAGIARISM CHECK (Optimized)
        plagiarism = local_library_similarity(document.id, content, user=request.user)
        PlagiarismCheck.objects.create(
            document=document,
            similarity_score=plagiarism.get("similarity_percent", 0) / 100.0,
        )

        # EXTRACT ADDITIONAL DATA (Only if not provided by Groq)
        extracted_links = ml_processor.extract_links(content) if hasattr(ml_processor, 'extract_links') else []
        references = ml_processor.extract_references(content) if hasattr(ml_processor, 'extract_references') else []
        
        # Use Groq data as source of truth to avoid redundant processing
        keywords_detected = analysis_data.get('keywords', [])
        methodology_detected = analysis_data.get('methodology', [])
        technologies_detected = analysis_data.get('technologies', [])
        
        # Datasets (Groq usually misses these links)
        try:
            datasets = ml_processor.extract_datasets(content) if hasattr(ml_processor, 'extract_datasets') else {}
            dataset_names = datasets.get('names', []) or analysis_data.get('datasets', [])
            dataset_links = datasets.get('links', [])
        except:
            dataset_names, dataset_links = [], []

        # EXTRAS
        extras = {
            'plagiarism': plagiarism,
            'research_gaps': analysis_data.get('research_gaps', []) or (ml_processor.detect_research_gaps(content) if hasattr(ml_processor, 'detect_research_gaps') else []),
            'visual_assets': ml_processor.extract_visuals(content) if hasattr(ml_processor, 'extract_visuals') else {'counts': {}},
            'methodology_summary': analysis_data.get('summary', '')[:500],
            'conclusion': analysis_data.get('conclusion', ''),
            'extracted_images': extracted_images_data[:15], # Restored higher image count
        }

        # SAVE ANALYSIS
        analysis = AnalysisResult.objects.create(
            document=document,
            summary=analysis_data.get('summary', ''),
            abstract=analysis_data.get('abstract', ''),
            keywords=keywords_detected,
            methodology=methodology_detected,
            technologies=technologies_detected,
            goal=analysis_data.get('goal', ''),
            impact=analysis_data.get('impact', ''),
            publication_year=analysis_data.get('publication_year', ''),
            authors=analysis_data.get('authors', []),
            word_count=analysis_data.get('statistics', {}).get('word_count', 0),
            unique_words=analysis_data.get('statistics', {}).get('unique_words', 0),
            extracted_links=extracted_links,
            references=references,
            dataset_names=dataset_names,
            dataset_links=dataset_links,
            extras=extras,
        )

        return JsonResponse({
            'success': True,
            'redirect_url': f'/result/{document.id}/'
        })

    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


# =========================
# 📊 STUB FUNCTIONS (TODO)
# =========================

@login_required
def profile(request):
    """User profile page"""
    if request.method == 'POST':
        # TODO: Update profile logic
        pass
    return render(request, 'analyzer/profile.html')


# @login_required
# def dashboard(request):
#     documents = Document.objects.filter(user=user)
#     total_papers = documents.count()
#     """Dashboard page"""

#     print("USER:", request.user)
#     print("DOC COUNT:", Document.objects.filter(user=request.user).count())
#     print("ALL DOCS:", Document.objects.count())

#     from django.utils import timezone
#     from django.db.models import Count, Avg, Sum
#     from datetime  import timedelta
    
#     user = request.user
    
#     # Total papers
#     total_papers = Document.objects.filter(user=user).count()
    


@login_required
def dashboard(request):
    """Dashboard page"""

    user = request.user  # ✅ define FIRST

    print("USER:", user)
    print("DOC COUNT:", Document.objects.filter(user=user).count())
    print("ALL DOCS:", Document.objects.count())

    # Get user documents
    documents = Document.objects.filter(user=user)

    # Total papers
    total_papers = documents.count()

    return render(request, "dashboard.html", {
        "documents": documents,
        "total_papers": total_papers,
    })
    # Recent activity for sidebar
    recent_activity = Document.objects.filter(user=user).order_by('-created_at')[:5]
    documents = Document.objects.filter(user=user)
    
    # Total words
    total_words = documents.aggregate(Sum('word_count'))['word_count__sum'] or 0
    
    # Average words per paper
    avg_words = total_words / total_papers if total_papers > 0 else 0
    
    # This month papers
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = Document.objects.filter(user=user, created_at__gte=month_start).count()
    
    # Plagiarism stats
    from .models import PlagiarismCheck
    user_docs = Document.objects.filter(user=user)
    plagiarism_checks = PlagiarismCheck.objects.filter(document__in=user_docs)
    
    avg_plagiarism = plagiarism_checks.aggregate(Avg('similarity_score'))['similarity_score__avg']
    avg_plagiarism = round(avg_plagiarism * 100, 1) if avg_plagiarism else 0
    
    low_plag = plagiarism_checks.filter(similarity_score__lt=0.25).count()
    high_plag = plagiarism_checks.filter(similarity_score__gte=0.50).count()
    
    # Top keywords
    from .models import AnalysisResult
    analysis_results = AnalysisResult.objects.filter(document__user=user)
    all_keywords = []
    for a in analysis_results:
        all_keywords.extend(a.keywords or [])
    
    from collections import Counter
    keyword_counts = Counter(all_keywords)
    top_keywords = keyword_counts.most_common(10)
    
    # Unique keywords count
    unique_keywords = len(set(all_keywords))
    
    # Member since
    member_since = user.date_joined
    
    # User full name
    user_full_name = user.get_full_name() or user.username
    
    return render(request, 'analyzer/dashboard.html', {
        'total_papers': total_papers,
        'avg_plagiarism': avg_plagiarism,
        'unique_keywords': unique_keywords,
        'this_month': this_month,
        'recent_activity': recent_activity,
        'documents': documents,
        'total_words': total_words,
        'avg_words': round(avg_words),
        'low_plag': low_plag,
        'high_plag': high_plag,
        'top_keywords': top_keywords,
        'member_since': member_since,
        'user_full_name': user_full_name,
    })


@login_required
def upload_page(request):
    """Upload page"""
    return render(request, 'analyzer/upload.html')


@login_required
def compare(request):
    """Compare papers page"""
    documents = Document.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'analyzer/compare.html', {'documents': documents})


def contact(request):
    """Contact page - Save messages to database"""
    from .models import ContactMessage
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        if not all([name, email, message]):
            return JsonResponse({'success': False, 'message': 'Please fill out all required fields.'})
        
        try:
            # Save contact message to database
            contact_msg = ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject or 'No Subject',
                message=message,
                is_read=False
            )
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Contact message saved from {name} ({email}): {subject}")
            
            return JsonResponse({
                'success': True,
                'message': 'Thank you! Your message has been sent successfully. We will get back to you soon.'
            })
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving contact message: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'An error occurred. Please try again.'
            })
    return render(request, 'analyzer/contact.html')


def forgot_password(request):
    """Forgot password page - Send OTP"""
    from .otp_utils import create_and_send_otp
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        # Check if user exists
        try:
            User.objects.get(email=email)
            # Create and send OTP
            _, email_sent = create_and_send_otp(email)
            
            if email_sent:
                request.session['reset_email'] = email
                messages.success(request, f'OTP sent to {email}. Please check your inbox.')
                return redirect('verify_otp')
            else:
                messages.error(request, 'Failed to send OTP because of an email server error. Please try again.')
        except User.DoesNotExist:
            messages.error(request, 'Error: No account found with this email address.')
            return redirect('forgot_password')
    
    return render(request, 'analyzer/forgot_password.html')


def verify_otp(request):
    """Verify OTP page"""
    from .otp_utils import verify_otp as verify_otp_code, mark_otp_as_used
    
    email = request.session.get('reset_email')
    if not email:
        messages.error(request, 'Invalid request. Please start password reset again.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()
        
        # Verify OTP
        is_valid, reset_otp_obj = verify_otp_code(email, otp)
        
        if is_valid:
            # Mark OTP as used
            mark_otp_as_used(email, otp)
            request.session['otp_verified'] = True
            messages.success(request, 'OTP verified successfully. Please set your new password.')
            return redirect('reset_password')
        else:
            messages.error(request, 'Invalid or expired OTP. Please try again.')
    
    context = {'email': email}
    return render(request, 'analyzer/verify_otp.html', context)


def reset_password(request):
    """Reset password page"""
    from django.contrib.auth import authenticate, update_session_auth_hash
    
    email = request.session.get('reset_email')
    otp_verified = request.session.get('otp_verified')
    
    if not email or not otp_verified:
        messages.error(request, 'Invalid request. Please start password reset again.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validate passwords
        if not password:
            messages.error(request, 'Password cannot be empty.')
        elif len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        elif password != confirm_password:
            messages.error(request, 'Passwords do not match.')
        else:
            # Update user password
            try:
                user = User.objects.get(email=email)
                user.set_password(password)
                user.save()
                
                # Clear session
                request.session.pop('reset_email', None)
                request.session.pop('otp_verified', None)
                
                messages.success(request, 'Password reset successfully! Please log in with your new password.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
    
    context = {'email': email}
    return render(request, 'analyzer/reset_password.html', context)


@login_required
def result_detail(request, document_id):
    """Detailed result page for a document"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    analysis = getattr(document, 'analysis', None)
    return render(request, 'analyzer/result.html', {'document': document, 'analysis': analysis})


@login_required
def ask_question(request, document_id):
    """Answer a specific question about a document using RAG"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        question = data.get('question')
        
        if not question:
            return JsonResponse({'error': 'No question provided'}, status=400)
            
        document = get_object_or_404(Document, id=document_id, user=request.user)
        
        # Use the RAG pipeline to get an answer
        answer = rag_pipeline(document.content, question)
        
        return JsonResponse({
            'success': True,
            'question': question,
            'answer': answer
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Q&A Error for doc {document_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f"An error occurred: {str(e)}"}, status=500)



@login_required
def compare_papers(request, doc1_id, doc2_id):
    """Compare two papers - returns JSON data for comparison"""
    if doc1_id == doc2_id:
        return JsonResponse({'error': 'Cannot compare a paper with itself'}, status=400)
        
    doc1 = get_object_or_404(Document, id=doc1_id, user=request.user)
    doc2 = get_object_or_404(Document, id=doc2_id, user=request.user)
    
    # Get analysis data
    analysis1 = getattr(doc1, 'analysis', None)
    analysis2 = getattr(doc2, 'analysis', None)
    
    # Helper function to get keywords/methods as list
    def to_list(value):
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [value] if value else []
        return []
    
    # Helper function to calculate similarity
    def calculate_similarity(list1, list2):
        if not list1 or not list2:
            return 0
        common = len(set(str(x).lower() for x in list1) & set(str(x).lower() for x in list2))
        total = max(len(list1), len(list2))
        return int((common / total) * 100) if total > 0 else 0
    
    # Extract data with fallbacks
    p1_data = {
        'id': doc1.id,
        'title': doc1.title or 'Untitled',
        'authors': ', '.join(analysis1.authors) if analysis1 and analysis1.authors else 'Unknown',
        'publication_date': analysis1.publication_year if analysis1 else 'Unknown',
        'word_count': analysis1.word_count if analysis1 else doc1.word_count,
        'abstract': (analysis1.abstract or 'No abstract available') if analysis1 else 'No content',
        'keywords': to_list(analysis1.keywords) if analysis1 else [],
        'methodology': to_list(analysis1.methodology) if analysis1 else [],
        'technologies': to_list(analysis1.technologies) if analysis1 else [],
        'summary': analysis1.summary if analysis1 else ''
    }
    
    p2_data = {
        'id': doc2.id,
        'title': doc2.title or 'Untitled',
        'authors': ', '.join(analysis2.authors) if analysis2 and analysis2.authors else 'Unknown',
        'publication_date': analysis2.publication_year if analysis2 else 'Unknown',
        'word_count': analysis2.word_count if analysis2 else doc2.word_count,
        'abstract': (analysis2.abstract or 'No abstract available') if analysis2 else 'No content',
        'keywords': to_list(analysis2.keywords) if analysis2 else [],
        'methodology': to_list(analysis2.methodology) if analysis2 else [],
        'technologies': to_list(analysis2.technologies) if analysis2 else [],
        'summary': analysis2.summary if analysis2 else ''
    }
    
    # Calculate similarities
    keyword_sim = calculate_similarity(p1_data['keywords'], p2_data['keywords'])
    method_sim = calculate_similarity(p1_data['methodology'], p2_data['methodology'])
    tech_sim = calculate_similarity(p1_data['technologies'], p2_data['technologies'])
    overall_sim = int((keyword_sim + method_sim + tech_sim) / 3)
    
    # Find common elements
    common_keywords = list(set(str(x).lower() for x in p1_data['keywords']) & set(str(x).lower() for x in p2_data['keywords']))
    common_methods = list(set(str(x).lower() for x in p1_data['methodology']) & set(str(x).lower() for x in p2_data['methodology']))
    common_tech = list(set(str(x).lower() for x in p1_data['technologies']) & set(str(x).lower() for x in p2_data['technologies']))
    
    # Find unique elements
    unique_p1_kw = list(set(str(x).lower() for x in p1_data['keywords']) - set(str(x).lower() for x in p2_data['keywords']))
    unique_p2_kw = list(set(str(x).lower() for x in p2_data['keywords']) - set(str(x).lower() for x in p1_data['keywords']))
    
    comparison_result = {
        'overall_similarity': overall_sim,
        'keyword_similarity': keyword_sim,
        'method_similarity': method_sim,
        'tech_similarity': tech_sim,
        'common_keywords': common_keywords[:10],
        'common_methods': common_methods[:10],
        'common_tech': common_tech[:10],
        'unique_p1': unique_p1_kw[:10],
        'unique_p2': unique_p2_kw[:10]
    }
    
    # Save comparison result to database
    from .models import ComparisonResult
    try:
        ComparisonResult.objects.create(
            user=request.user,
            document1=doc1,
            document2=doc2,
            similarity_score=overall_sim,
            comparison_data=comparison_result
        )
    except Exception as e:
        logger.error(f"Error saving comparison result: {str(e)}")
    
    return JsonResponse({
        'paper1': p1_data,
        'paper2': p2_data,
        'comparison': comparison_result
    })

@login_required
def email_report(request, document_id):
    """Email analysis report to user or recipient"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    analysis = getattr(document, 'analysis', None)
    
    if request.method == 'POST':
        recipient = request.POST.get('email', request.user.email)
        export_format = request.POST.get('export_format', 'pdf')
        
        if not recipient:
            return JsonResponse({'success': False, 'error': 'No recipient email provided'})
            
        try:
            # Generate the biological attachment
            if export_format == 'pdf':
                response = export_as_pdf(request, document, analysis)
                filename = f"{document.title[:30]}_report.pdf"
                mimetype = 'application/pdf'
            else:
                response = export_as_txt(document, analysis)
                filename = f"{document.title[:30]}_report.txt"
                mimetype = 'text/plain'
            
            from django.core.mail import EmailMessage
            
            subject = f"PaperAIzer Report: {document.title}"
            body = f"Hello,\n\nPlease find attached the analysis report for '{document.title}' generated by PaperAIzer.\n\nBest regards,\nThe PaperAIzer Team"
            
            email = EmailMessage(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
            )
            email.attach(filename, response.content, mimetype)
            email.send()
            
            return JsonResponse({'success': True, 'message': f'Report sent successfully to {recipient}'})
        except Exception as e:
            logger.error(f"Email report error: {e}", exc_info=True)
            return JsonResponse({'success': False, 'error': f'Failed to send email: {str(e)}'})
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)



@login_required
def library(request):
    """Library page - list of all user documents"""
    documents = Document.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'analyzer/library.html', {'documents': documents})


@login_required
def delete_document(request, document_id):
    """Delete a document"""
    try:
        document = get_object_or_404(Document, id=document_id, user=request.user)
        if request.method == 'POST':
            document.delete()
            return JsonResponse({'success': True, 'message': 'Document deleted successfully'})
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def export_document(request, document_id, export_format):
    """Export document in specified format"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    analysis = getattr(document, 'analysis', None)
    
    if export_format == 'pdf':
        return export_as_pdf(request, document, analysis)
    elif export_format == 'txt':
        return export_as_txt(document, analysis)
    elif export_format == 'csv':
        return export_as_csv(document, analysis)
    elif export_format == 'json':
        return export_as_json(document, analysis)
    
    return JsonResponse({'error': 'Export format not implemented'}, status=400)


def export_as_pdf(request, document, analysis):
    """Export analysis as PDF"""
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, spaceAfter=20)
    story.append(Paragraph(document.title or "Untitled", title_style))
    
    # Metadata
    if analysis:
        meta_data = f"Words: {analysis.word_count} | Keywords: {len(analysis.keywords or [])}"
        if analysis.publication_year:
            meta_data += f" | Year: {analysis.publication_year}"
        story.append(Paragraph(f"<i>{meta_data}</i>", styles['Italic']))
        story.append(Spacer(1, 20))
    
    # Abstract
    if analysis and analysis.abstract:
        story.append(Paragraph("Abstract", styles['Heading2']))
        story.append(Paragraph(analysis.abstract, styles['Normal']))
        story.append(Spacer(1, 15))
    
    # Summary
    if analysis and analysis.summary:
        story.append(Paragraph("Summary", styles['Heading2']))
        story.append(Paragraph(analysis.summary, styles['Normal']))
        story.append(Spacer(1, 15))
    
    # Keywords
    if analysis and analysis.keywords:
        story.append(Paragraph("Keywords", styles['Heading2']))
        story.append(Paragraph(", ".join(analysis.keywords), styles['Normal']))
        story.append(Spacer(1, 15))
    
    # Methodology
    if analysis and analysis.methodology:
        story.append(Paragraph("Methodology", styles['Heading2']))
        for method in analysis.methodology:
            story.append(Paragraph(f"• {method}", styles['Normal']))
        story.append(Spacer(1, 15))
    
    # Technologies
    if analysis and analysis.technologies:
        story.append(Paragraph("Technologies", styles['Heading2']))
        story.append(Paragraph(", ".join(analysis.technologies), styles['Normal']))
        story.append(Spacer(1, 15))
    
    # Impact
    if analysis and analysis.impact:
        story.append(Paragraph("Impact & Contributions", styles['Heading2']))
        story.append(Paragraph(analysis.impact, styles['Normal']))
        story.append(Spacer(1, 15))
    
    doc.build(story)
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type='application/pdf')


def export_as_txt(document, analysis):
    """Export analysis as text file"""
    lines = []
    lines.append("=" * 60)
    lines.append(document.title or "Untitled Document")
    lines.append("=" * 60)
    lines.append("")
    
    if analysis:
        if analysis.authors:
            lines.append(f"Authors: {', '.join(analysis.authors)}")
        if analysis.publication_year:
            lines.append(f"Publication Year: {analysis.publication_year}")
        lines.append(f"Word Count: {analysis.word_count}")
        lines.append("")
        
        if analysis.abstract:
            lines.append("ABSTRACT")
            lines.append("-" * 40)
            lines.append(analysis.abstract)
            lines.append("")
        
        if analysis.summary:
            lines.append("SUMMARY")
            lines.append("-" * 40)
            lines.append(analysis.summary)
            lines.append("")
        
        if analysis.keywords:
            lines.append("KEYWORDS")
            lines.append("-" * 40)
            lines.append(", ".join(analysis.keywords))
            lines.append("")
        
        if analysis.methodology:
            lines.append("METHODOLOGY")
            lines.append("-" * 40)
            for method in analysis.methodology:
                lines.append(f"• {method}")
            lines.append("")
        
        if analysis.technologies:
            lines.append("TECHNOLOGIES")
            lines.append("-" * 40)
            lines.append(", ".join(analysis.technologies))
            lines.append("")
        
        if analysis.impact:
            lines.append("IMPACT & CONTRIBUTIONS")
            lines.append("-" * 40)
            lines.append(analysis.impact)
            lines.append("")
        
        if analysis.goal:
            lines.append("RESEARCH GOAL")
            lines.append("-" * 40)
            lines.append(analysis.goal)
            lines.append("")
    
    content = "\n".join(lines)
    return HttpResponse(content, content_type='text/plain')


def export_as_csv(document, analysis):
    """Export analysis as CSV"""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Field', 'Value'])
    writer.writerow(['Title', document.title or ''])
    
    if analysis:
        writer.writerow(['Authors', ', '.join(analysis.authors or [])])
        writer.writerow(['Publication Year', analysis.publication_year or ''])
        writer.writerow(['Word Count', analysis.word_count or 0])
        writer.writerow(['Abstract', analysis.abstract or ''])
        writer.writerow(['Summary', analysis.summary or ''])
        writer.writerow(['Keywords', ', '.join(analysis.keywords or [])])
        writer.writerow(['Methodology', ', '.join(analysis.methodology or [])])
        writer.writerow(['Technologies', ', '.join(analysis.technologies or [])])
        writer.writerow(['Goal', analysis.goal or ''])
        writer.writerow(['Impact', analysis.impact or ''])
    
    return HttpResponse(output.getvalue(), content_type='text/csv')


def export_as_json(document, analysis):
    """Export analysis as JSON"""
    import json
    
    data = {
        'title': document.title,
        'created_at': document.created_at.isoformat() if document.created_at else None,
    }
    
    if analysis:
        data.update({
            'authors': analysis.authors or [],
            'publication_year': analysis.publication_year,
            'abstract': analysis.abstract,
            'summary': analysis.summary,
            'keywords': analysis.keywords or [],
            'methodology': analysis.methodology or [],
            'technologies': analysis.technologies or [],
            'goal': analysis.goal,
            'impact': analysis.impact,
            'word_count': analysis.word_count,
            'references': analysis.references or [],
            'extracted_links': analysis.extracted_links or [],
        })
    
    return JsonResponse(data, json_dumps_params={'indent': 2})


@login_required
def submit_feedback(request, document_id):
    """Submit feedback on analysis"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    
    if request.method == 'POST':
        # TODO: Save feedback
        pass
    
    return JsonResponse({'success': True})


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({'status': 'ok', 'version': '1.0'})