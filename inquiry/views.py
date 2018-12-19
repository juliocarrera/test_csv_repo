import logging as logging_

from django.db import transaction
from django.urls import reverse
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib.auth import login
from django.contrib import messages
from django.http import HttpResponseServerError, Http404

from formtools.wizard.views import NamedUrlSessionWizardView

from utils import get_request_ip
from custom_auth.models import User
from core.models import Address, UseCaseModel
from core.views import DataLayerViewMixin, WizardSegmentMixin
from core.utils import segment_event
from stages import transitions
from fit_quiz.views import FIT_QUIZ_SESSION_DATA_PREFIX
from inquiry.forms import (
    InquiryFirstForm, InquiryHomeForm, InquiryHomeownerForm, WizardClientUserCreationForm
)
from inquiry.models import Inquiry
from inquiry.outcomes import (
    INQUIRY_OUTCOME_SLUG_MAP, INQUIRY_OUTCOME_CONTEXTS, get_outcome_context,
    get_state_zip_code_outcome_key
)

logger = logging_.getLogger('portals.apps.' + __name__)


def _get_inquiry_segment_event_data(client):
    """ Returns dict of inquiry and client data for use in segment events E25 and E69 """
    return {
        'tracking_status': 'investment inquiry submitted',
        'email': client.email,
        'phone': client.phone_number,
        'email_confirmed': client.email_confirmed,  # always False
        'friendly_id': client.friendly_id,
        'first_name': client.user.first_name,
        'last_name': client.user.last_name,
        'use_case_debts': client.inquiry.use_case_debts,
        'use_case_diversify': client.inquiry.use_case_diversify,
        'use_case_renovate': client.inquiry.use_case_renovate,
        'use_case_education': client.inquiry.use_case_education,
        'use_case_buy_home': client.inquiry.use_case_buy_home,
        'use_case_business': client.inquiry.use_case_business,
        'use_case_emergency': client.inquiry.use_case_emergency,
        'use_case_retirement': client.inquiry.use_case_retirement,
        'when_interested': client.inquiry.when_interested,
        'household_debt': client.inquiry.household_debt,
        'referrer_name': client.inquiry.referrer_name,
        'property_type': client.inquiry.property_type,
        'primary_residence': client.inquiry.primary_residence,
        'home_value': client.inquiry.home_value,
        'ten_year_duration_prediction': client.inquiry.ten_year_duration_prediction,
        'street': client.inquiry.address.street,
        'unit': client.inquiry.address.unit,
        'city': client.inquiry.address.city,
        'state': client.inquiry.address.state,
        'zip_code': client.inquiry.address.zip_code,
        'sms_allowed': True if hasattr(client, 'sms_consent') else False,
    }


class InquiryApplyWizard(WizardSegmentMixin, NamedUrlSessionWizardView):
    # Use CustomFormToolsSessionStorage to fix bug EN-308 (described further in its docstring)
    storage_name = 'inquiry.utils.CustomFormToolsSessionStorage'
    form_list = [
        # Form for Address obj
        ("first", InquiryFirstForm),
        # Forms for Inquiry obj
        ("home", InquiryHomeForm),
        ("homeowner", InquiryHomeownerForm),
        # Form for Client account creation
        ("signup", WizardClientUserCreationForm),
    ]
    # Templates for Forms. Must have same key as tuple[0] in form_list.
    templates = {
        "first": "inquiry/first.html",
        "home": "inquiry/home.html",
        "homeowner": "inquiry/homeowner.html",
        "signup": "inquiry/signup.html"
    }

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    def get_step_url(self, step):
        return reverse(self.url_name, kwargs={'step': step})

    @staticmethod
    def fill_form_initial(session, initial):
        """
        fills initial with the items in session starting with FIT_QUIZ_SESSION_DATA_PREFIX
        """
        for key in session.keys():
            if key.startswith(FIT_QUIZ_SESSION_DATA_PREFIX):
                remaining = key[len(FIT_QUIZ_SESSION_DATA_PREFIX):]
                initial.update({remaining: session.get(key)})

    def get_form_initial(self, step):
        # If fit quiz data is in session, use it to pre-populate some inquiry first form fields
        initial = self.initial_dict.get(step, {})
        InquiryApplyWizard.fill_form_initial(self.request.session, initial)
        return initial

    def _get_email(self, form_data, form_current_step):
        """
        returns the email from:
        + the email in form_data if the current step is the first step
        + the email from the first step if this is not the first step
        + the fit quiz if the user filled a fit quiz
        """
        email = ''
        # the signup form also has an email field so make sure this is the first form
        if form_current_step == 'first' and 'email' in form_data:
            # this is the first step
            return form_data['email']

        # if this is not the first step then get the email from the first step because the user
        # may have typed in a different email than that from the fit quiz
        if form_current_step != 'first':
            # self.storage.get_step_data('first') should not be None at this point
            return self.storage.get_step_data('first').getlist('first-email')[0]

        # this is the first step so pre-populate the email from a fit quiz
        initial = self.get_form_initial(form_current_step)
        if 'email' in initial:
            email = initial['email']
        return email

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.email_confirmed:
                return redirect(request.user.homepage)
            messages.info(
                request, (
                    "It looks like you've already submitted an investment estimate form but have "
                    "not yet confirmed your email address."
                )
            )
        return super().get(request, *args, **kwargs)

    def _create_address(self, address_data):
        address = Address(**address_data)
        address.full_clean()
        address.save()
        return address

    def _create_inquiry(self, inquiry_data, client, ip_address, address):
        inquiry_data['client'] = client
        inquiry_data['ip_address'] = ip_address
        inquiry = Inquiry(**inquiry_data)
        inquiry.address = address
        inquiry.full_clean()
        inquiry.save()
        return inquiry

    def done(self, form_list, form_dict, **kwargs):
        error_s = (
            'Sorry, there was an error creating your account. Please contact support@hometap.com'
        )
        ip_address = get_request_ip(self.request)

        # separate Inquiry data and Client signup data
        signup_data = form_dict['signup'].cleaned_data
        inquiry_data = {}
        for form_name, form in form_dict.items():
            if form_name == 'home' or form_name == 'homeowner':
                inquiry_data.update(form.cleaned_data)

        # add the email from the first step to signup_data
        first_data = form_dict['first'].cleaned_data
        signup_data['email'] = first_data.pop('email')

        # add the use case from the first step to the inquiry_data
        for field in UseCaseModel._meta.fields:
            inquiry_data[field.name] = first_data.pop(field.name)

        # we can't wrap the creation of all objects in a with transaction.atomic context because
        # create_client() is decorated with transaction.atomic, so create the client first
        try:
            client = User.objects.create_client(
                email=signup_data['email'],
                password=signup_data['password1'],
                first_name=inquiry_data['first_name'],
                last_name=inquiry_data['last_name'],
                phone_number=signup_data['phone_number'],
                state=first_data['state'],
                ip_address=ip_address,
                sms_opt_in=signup_data['sms_opt_in'],
                agree_to_terms=signup_data['agree_to_terms'],
                email_confirmed=False
            )
            user = client.user
        except Exception as e:
            logger.error('User+Client save failed {0}'.format(e))
            return HttpResponseServerError(error_s)

        try:
            with transaction.atomic():
                # create Address obj
                logger_error_s = 'Address save failed'
                address = self._create_address(first_data)

                # create Inquiry obj
                logger_error_s = 'Inquiry save failed'
                inquiry = self._create_inquiry(inquiry_data, client, ip_address, address)
        except Exception as e:
            user.delete()
            logger.error('{0} {1}'.format(logger_error_s, e))
            return HttpResponseServerError(error_s)

        # can't transition to the stage inside the transaction.atomic context because
        # Transition.execute() has a transaction.atomic decorator
        try:
            logger_error_s = 'Client submit inquiry failed'
            transitions.ClientSubmitInquiry(client=client).execute(inquiry=inquiry)
        except Exception as e:
            user.delete()
            address.delete()
            inquiry.delete()
            logger.error('{0} {1}'.format(logger_error_s, e))
            return HttpResponseServerError(error_s)

        # Log in the client, but they won't actually be able to do anything (will
        # not pass our custom auth middleware) until their email is confirmed.
        # 'Secretly' logging them in allows them to be 'fully' logged in
        # after clicking a confirmation link if they do it soon after
        # signing up
        login(self.request, user)

        # Segment Event E69 -- Note, we also send a similar datalayer event E25 on page load
        event_d = _get_inquiry_segment_event_data(client)
        segment_event(client.email, 'investment inquiry - created account - server', event_d)

        return redirect(reverse('inquiry:submitted'))

    @staticmethod
    def _get_wizard_step_event_data(cleaned_data, exported_fields, form_current_step, outcome):
        tracking_status = '{0} screen {1}'.format(form_current_step, outcome)
        segment_data = {'tracking_status': tracking_status}
        for field in exported_fields:
            if field in cleaned_data:
                segment_data.update({field: cleaned_data[field]})
        return segment_data

    def _send_wizard_step_segment_event(self, form_current_step, form, email, outcome):
        """ sends a Segment event corresponding to the given wizard step """
        if form_current_step == 'first':
            exported_fields = [
                'street',
                'unit',
                'city',
                'state',
                'zip_code',
                'use_case_debts',
                'use_case_education',
                'use_case_diversify',
                'use_case_buy_home',
                'use_case_renovate',
                'use_case_other',
                'use_case_business',
                'use_case_emergency',
                'use_case_retirement',
                'email',
            ]
        elif form_current_step == 'home':
            exported_fields = [
                'property_type',
                'primary_residence',
                'rent_type',
                'ten_year_duration_prediction',
                'home_value',
                'household_debt',
            ]
        elif form_current_step == 'homeowner':
            exported_fields = ['first_name', 'last_name', 'referrer_name', 'notes']
        elif form_current_step == 'signup':
            exported_fields = ['phone_number', 'sms_opt_in', 'agree_to_terms']

        # Segment Event E22, E23, E74, E77 -- inquiry screen submitted
        cleaned_data = form.cleaned_data
        event_data = self._get_wizard_step_event_data(
            cleaned_data, exported_fields, form_current_step, outcome
        )
        event_name = 'investment inquiry - {0} screen submitted'.format(form_current_step)
        segment_event(email, event_name, event_data)

    def _vet_based_on_form(self, form_current_step, form):
        """
        runs vetting on the given step
        redirects using a slug if the step is vetted
        """
        if form_current_step != 'first':
            # currently, we only validate the first step
            return (None, '', '')

        # vet first step if not a good inquiry based on state or zip code
        cleaned_data = form.cleaned_data
        outcome_key, vetted_message = get_state_zip_code_outcome_key(
            cleaned_data['state'], cleaned_data['zip_code']
        )
        if outcome_key is not None:
            return (INQUIRY_OUTCOME_SLUG_MAP[outcome_key], 'inquiry:outcome', vetted_message)

        # passed tests
        return (None, '', '')


class InquiryOutcomeView(TemplateView):
    template_name = 'inquiry/inquiry_outcome.html'

    def dispatch(self, request, *args, **kwargs):
        if self.kwargs['slug'] not in INQUIRY_OUTCOME_CONTEXTS:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        outcome_context = get_outcome_context(self.kwargs['slug'])
        context.update(outcome_context)
        return context


class InquirySubmitted(DataLayerViewMixin, TemplateView):
    """
    Render the email_confirm_awaiting page, passing in an event dict in context
    for the tracking event E25 for the tag manager javascript code to send.

    Note: If the user refreshes this page, E25 will send again
    """
    template_name = 'custom_auth/email_confirm_awaiting.html'
    event_id = 'E25'

    # TODO(Charlie): restore after completing EN-331
    # send_event_once_per_session = True

    def dispatch(self, request, *args, **kwargs):
        """
        Ensure user is an authenticated client and has not yet confirmed their
        email, else redirect them. This is similar to the functionality of the
        authorization_decorators, but they rely on all client URLs requiring
        the user to have confirmed their email; this view is an exception.
        """
        if not request.user.is_authenticated:
            return redirect(reverse('custom_auth:login_client'))
        if request.user.email_confirmed or not request.user.is_client:
            return redirect(request.user.homepage)
        return super().dispatch(request, *args, **kwargs)

    def get_event(self, **kwargs):
        # Segment Event E25 -- Note, we also send a similar serverside event E69
        event_d = _get_inquiry_segment_event_data(self.request.user.client)
        event_d['event'] = 'investment inquiry - created account'
        return event_d
