from django.urls import path
from . import views

app_name = 'verification'

urlpatterns = [
    path('verify/agency', views.verify_agency_api, name='verify_agency_api'),
    path('verify/consultancy', views.verify_consultancy_api, name='verify_consultancy_api'),
    path('verify/university', views.verify_university_api, name='verify_university_api'),
    path('verify/offer-letter', views.verify_offer_letter_api, name='verify_offer_letter_api'),
    path('verify/scholarship-letter', views.verify_scholarship_letter_api, name='verify_scholarship_letter_api'),
]
