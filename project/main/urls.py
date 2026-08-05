from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    # Dashboard & Home
    path('', views.home_dashboard, name='dashboard'),
    path('home/', views.home_dashboard, name='home'),

    # Auth Routes
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Verification Workflows
    path('verify/agency/', views.verify_agency, name='verify_agency'),
    path('verify/university/', views.verify_university, name='verify_university'),
    path('verify/offer-letter/', views.verify_offer_letter, name='verify_offer_letter'),
    path('verify/scholarship-letter/', views.verify_scholarship_letter, name='verify_scholarship_letter'),

    # Report & Verdict Card & Chatbot
    path('report-scam/', views.report_scam, name='report_scam'),
    path('verdict/<uuid:record_uuid>/', views.shareable_verdict_card, name='verdict_card'),
    path('api/chatbot/', views.chatbot_api, name='chatbot_api'),
]
