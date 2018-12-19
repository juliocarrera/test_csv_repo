from django.urls import path
from django.views.generic import RedirectView

from inquiry.views import InquiryApplyWizard, InquirySubmitted, InquiryOutcomeView

app_name = 'inquiry'

inquiry_wizard = InquiryApplyWizard.as_view(
    InquiryApplyWizard.form_list, url_name='inquiry:inquiry_step'
)

urlpatterns = [
    path('data/<step>/', inquiry_wizard, name='inquiry_step'),
    path('data/', inquiry_wizard, name='apply'),
    path('apply/', RedirectView.as_view(url='/inquiry/', permanent=True)),
    path('results/<slug:slug>/', InquiryOutcomeView.as_view(), name='outcome'),
    path('submitted/', InquirySubmitted.as_view(), name='submitted'),
    path('', RedirectView.as_view(url='/inquiry/data/', permanent=True)),
]
