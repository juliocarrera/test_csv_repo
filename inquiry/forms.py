from django import forms
from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from core.utils import BOOLEAN_CHOICES
from core.forms import AddressFormMixin, UseCaseFormMixin, WhenInterestedFormMixin
from custom_auth.forms import ClientUserCreationFormMixin
from inquiry.models import Inquiry


class WizardClientUserCreationForm(ClientUserCreationFormMixin):
    """
    Makes the email field inherited from UserCreationForm be non-required because it's entered
    in the first form.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = False


class InquiryFirstForm(AddressFormMixin, UseCaseFormMixin, forms.ModelForm):
    email = forms.EmailField(label=_('email address'), max_length=254)

    class Meta:
        model = Inquiry
        fields = UseCaseFormMixin.Meta.fields + [
            'street',
            'city',
            'state',
            'zip_code',
        ]
        labels = UseCaseFormMixin.Meta.labels

    def clean_email(self):
        # no need to strip because it's turned on by EmailField
        email = self.cleaned_data['email']
        Client = apps.get_model('custom_auth', 'Client')
        if Client.objects.filter(user__email__iexact=email).exists():
            raise ValidationError('User with this Email address already exists.')
        return email


class InquiryHomeForm(forms.ModelForm):
    primary_residence = forms.ChoiceField(
        choices=BOOLEAN_CHOICES,
        widget=forms.widgets.RadioSelect,
        label="Is this home your primary residence?"
    )
    property_type = forms.ChoiceField(
        choices=[("", "")] + list(Inquiry.PROPERTY_TYPES), label="Select Property Type"
    )
    rent_type = forms.ChoiceField(
        choices=[("", "")] + list(Inquiry.RENT_TYPES),
        label="Do you ever rent out all or part of your home?"
    )
    ten_year_duration_prediction = forms.ChoiceField(
        choices=[("", "")] + list(Inquiry.TEN_YEAR_DURATION_TYPES),
        label="Do you think you will live there for more than 10 years?"
    )

    class Meta:
        model = Inquiry
        fields = [
            'property_type',
            'primary_residence',
            'rent_type',
            'ten_year_duration_prediction',
            'home_value',
            'household_debt',
        ]
        labels = {
            'home_value': 'How much do you think your home is worth?',
            'household_debt': 'How much do you still owe on the home?',
        }


class InquiryHomeownerForm(WhenInterestedFormMixin, forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = WhenInterestedFormMixin.Meta.fields + [
            'first_name',
            'last_name',
            'referrer_name',
            'notes',
        ]
        labels = {
            'first_name': 'First Name',  # title case
            'last_name': 'Last Name',  # title case
            'referrer_name': 'Did you hear about us from someone? What is their name?',
            'notes': 'Any other notes for the reviewer?',
        }
        widgets = {
            'notes': forms.widgets.Textarea(attrs={
                'cols': 80,
                'rows': 5
            }),
        }
