import copy
from unittest import mock, skipIf

import pandas as pd

from django.conf import settings
from django.test import TestCase, RequestFactory, Client as Browser, override_settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from core.models import Address
from core.tests.test_helpers import create_address_example
from core.utils import OPERATIONAL_STATES, EXPANSION_STATES, OTHER_STATES
from consent.models import SmsConsent
from custom_auth.models import Client
from custom_auth.tests.test_helpers import (
    create_client_example, CLIENT_EXAMPLE_DATA, create_reviewer_example
)
from fit_quiz.views import FIT_QUIZ_SESSION_DATA_PREFIX
from inquiry.forms import InquiryFirstForm, InquiryHomeForm, WizardClientUserCreationForm
from inquiry.models import Inquiry
from inquiry.outcomes import INQUIRY_OUTCOME_SLUG_MAP
from inquiry.tests.test_forms import FIRST_FORM_EXAMPLE_DATA, HOME_FORM_EXAMPLE_DATA
from inquiry.tests.test_utils import create_inquiry_example, UNDESIRABLE_ZIP_CODES
from inquiry.views import InquiryApplyWizard, InquirySubmitted, _get_inquiry_segment_event_data
from stages.models import InquiryInReview

FIRST_DATA = {
    "inquiry_apply_wizard-current_step": "first",
    "first-street": "20 University Rd",
    "first-unit": "Suite 100",
    "first-city": "Cambridge",
    "first-state": "MA",
    "first-zip_code": "02138",
    "first-use_case_debts": "on",
    "first-use_case_renovate": "on",
    "first-use_case_other": "",
    "first-email": "",
    "submit": "Next",
}
HOME_DATA = {
    "inquiry_apply_wizard-current_step": "home",
    "home-property_type": "sf",
    "home-rent_type": "no",
    "home-primary_residence": "True",
    "home-ten_year_duration_prediction": "over_10",
    "home-home_value": "1000000",
    "home-household_debt": "500000",
    "submit": "Next",
}
HOMEOWNER_DATA = {
    "inquiry_apply_wizard-current_step": "homeowner",
    "homeowner-first_name": "Bob",
    "homeowner-last_name": "Smith",
    "homeowner-referrer_name": "Sarah Dekin",
    "homeowner-notes": "I sure hope I get approved!",
    'homeowner-when_interested': '7_to_12_months',
    "submit": "Next",
}


def submit_inquiry_forms(
    browser,
    email,
    first_overrides=None,
    home_overrides=None,
    homeowner_overrides=None,
    signup_overrides=None
):
    first_data = copy.deepcopy(FIRST_DATA)

    # always override the email
    first_data.update({"first-email": email})

    if first_overrides is not None:
        first_data.update(first_overrides)
    response = browser.post('/inquiry/data/first/', first_data)
    if response.context is not None:
        return response

    home_data = copy.deepcopy(HOME_DATA)
    if home_overrides is not None:
        home_data.update(home_overrides)
    response = browser.post('/inquiry/data/home/', home_data)
    if response.context is not None:
        return response

    homeowner_data = copy.deepcopy(HOMEOWNER_DATA)
    if homeowner_overrides is not None:
        homeowner_data.update(homeowner_overrides)
    response = browser.post('/inquiry/data/homeowner/', homeowner_data)
    if response.context is not None:
        return response

    signup_data = {
        "inquiry_apply_wizard-current_step": "signup",
        "signup-phone_number": "617-399-0604",
        "signup-password1": "testpassword1",
        "signup-password2": "testpassword1",
        "signup-sms_opt_in": "on",
        "signup-agree_to_terms": "on",
        "submit": "Finish",
    }
    if signup_overrides is not None:
        signup_data.update(signup_overrides)
    response = browser.post('/inquiry/data/signup/', signup_data)
    if response.context is not None:
        return response

    return browser.get('/inquiry/data/done/')


@skipIf(settings.REMOTE_ENVIRONMENT, "Remote environments require an IP address")
class InquiryTemplateTests(TestCase):
    def test_first_template(self):
        response = self.client.get('/inquiry/data/first/')
        self.assertTemplateUsed(response, 'inquiry/first.html')

    def test_home_template(self):
        response = self.client.get('/inquiry/data/home/')
        self.assertTemplateUsed(response, 'inquiry/home.html')

    def test_homeowner_template(self):
        response = self.client.get('/inquiry/data/homeowner/')
        self.assertTemplateUsed(response, 'inquiry/homeowner.html')

    def test_signup_template(self):
        response = self.client.get('/inquiry/data/signup/')
        self.assertTemplateUsed(response, 'inquiry/signup.html')

    def test_submitted_template(self):
        response = self.client.get('/inquiry/submitted/')
        self.assertRedirects(response, '/auth/login/')


@override_settings(
    SEGMENT_ENABLED=True,
    ZIP_CODE_FORECAST=pd.
    read_csv(settings.PROJECT_PATH + '/apps/inquiry/tests/test_data/test_zip_codes.csv')
)
class InquiryApplyWizardTests(TestCase):
    def _get_request(self):
        request = RequestFactory().get('/fake-path')
        SessionMiddleware().process_request(request)
        request.session.save()  # add session middleware to request
        return request

    def _check_created_objects(self, email):
        self.assertEqual(Client.objects.count(), 1)
        client = Client.objects.get()
        self.assertEqual(client.user.email, email)
        self.assertEqual(
            client.full_name_short, '{0} {1}'.format(
                HOMEOWNER_DATA['homeowner-first_name'], HOMEOWNER_DATA['homeowner-last_name']
            )
        )
        state = FIRST_DATA['first-state']
        self.assertEqual(client.friendly_id[:2], state)
        self.assertEqual(Address.objects.count(), 1)
        address = Address.objects.get()
        self.assertEqual(address.state, state)
        self.assertEqual(Inquiry.objects.count(), 1)
        inquiry = Inquiry.objects.get()
        self.assertEqual(client.inquiry, inquiry)
        self.assertEqual(inquiry.address, address)
        self.assertTrue(isinstance(client.current_stage, InquiryInReview))
        return client

    def test_vet_based_on_form_not_first_step(self):
        """ tests that only the first step vets based on state """
        view = InquiryApplyWizard()
        view.request = self._get_request()
        mocked_form = mock.Mock()
        for form in ['home', 'homeowner', 'signup']:
            with mock.patch.object(
                mocked_form, 'cleaned_data', {
                    'state': 'MT',
                    'zip_code': '01234'
                }
            ):
                (outcome_slug, url_name,
                 vetted_message) = view._vet_based_on_form(form, mocked_form)
            self.assertIsNone(outcome_slug)
            self.assertEqual(url_name, '')
            self.assertEqual(vetted_message, '')

    def test_vet_based_on_form_other_state(self):
        view = InquiryApplyWizard()
        view.request = self._get_request()
        mocked_form = mock.Mock()
        for state in OTHER_STATES:
            with mock.patch.object(
                mocked_form, 'cleaned_data', {
                    'state': state,
                    'zip_code': '01234'
                }
            ):
                (outcome_slug, url_name,
                 vetted_message) = view._vet_based_on_form('first', mocked_form)
            self.assertEqual(outcome_slug, INQUIRY_OUTCOME_SLUG_MAP['1_other_states'])
            self.assertEqual(url_name, 'inquiry:outcome')
            self.assertEqual(vetted_message, 'rejected other states')

    def test_vet_based_on_form_expansion_state(self):
        view = InquiryApplyWizard()
        view.request = self._get_request()
        mocked_form = mock.Mock()
        for state in EXPANSION_STATES:
            with mock.patch.object(
                mocked_form, 'cleaned_data', {
                    'state': state,
                    'zip_code': '01234'
                }
            ):
                (outcome_slug, url_name,
                 vetted_message) = view._vet_based_on_form('first', mocked_form)
            self.assertEqual(outcome_slug, INQUIRY_OUTCOME_SLUG_MAP['2_expansion_states'])
            self.assertEqual(url_name, 'inquiry:outcome')
            self.assertEqual(vetted_message, 'rejected expansion states')

    def test_vet_based_on_form_undesirable_zip_code(self):
        view = InquiryApplyWizard()
        view.request = self._get_request()
        mocked_form = mock.Mock()
        for undesirable_zip_code in UNDESIRABLE_ZIP_CODES:
            with mock.patch.object(
                mocked_form, 'cleaned_data', {
                    'state': 'MA',
                    'zip_code': undesirable_zip_code
                }
            ):
                (outcome_slug, url_name,
                 vetted_message) = view._vet_based_on_form('first', mocked_form)
            self.assertEqual(outcome_slug, INQUIRY_OUTCOME_SLUG_MAP['3_undesirable_zip_code'])
            self.assertEqual(url_name, 'inquiry:outcome')
            self.assertEqual(vetted_message, 'rejected undesirable zip code')

    def test_vet_based_on_form(self):
        view = InquiryApplyWizard()
        view.request = self._get_request()
        mocked_form = mock.Mock()
        with mock.patch.object(mocked_form, 'cleaned_data', {'state': 'MA', 'zip_code': '02138'}):
            (outcome_slug, url_name, vetted_message) = view._vet_based_on_form(
                'first', mocked_form
            )  # yapf: disable
        self.assertIsNone(outcome_slug)
        self.assertEqual(url_name, '')
        self.assertEqual(vetted_message, '')

    @mock.patch('inquiry.views.get_state_zip_code_outcome_key')
    def test_vet_based_on_form_calls_get_state_zip_code_outcome_key(
        self, mocked_get_state_zip_code_outcome_key
    ):
        view = InquiryApplyWizard()
        view.request = self._get_request()
        mocked_get_state_zip_code_outcome_key.return_value = (None, '')
        mocked_form = mock.Mock()
        with mock.patch.object(mocked_form, 'cleaned_data', {'state': 'MA', 'zip_code': '02138'}):
            (outcome_slug, url_name, vetted_message) = view._vet_based_on_form(
                'first', mocked_form
            )  # yapf: disable
            cleaned_data = mocked_form.cleaned_data
            mocked_get_state_zip_code_outcome_key.assert_called_once_with(
                cleaned_data['state'], cleaned_data['zip_code']
            )

    def test_first_form_other_state(self):
        browser = Browser()
        first_data = copy.deepcopy(FIRST_DATA)
        for state in OTHER_STATES:
            first_data.update({"first-email": 'test+client1@hometap.com', "first-state": state})
            response = browser.post('/inquiry/data/first/', first_data)
            self.assertRedirects(
                response,
                '/inquiry/results/rros/',
                status_code=302,
                target_status_code=200,
                fetch_redirect_response=False
            )

    def test_first_form_expansion_state(self):
        browser = Browser()
        first_data = copy.deepcopy(FIRST_DATA)
        for state in EXPANSION_STATES:
            first_data.update({"first-email": 'test+client1@hometap.com', "first-state": state})
            response = browser.post('/inquiry/data/first/', first_data)
            self.assertRedirects(
                response,
                '/inquiry/results/rres/',
                status_code=302,
                target_status_code=200,
                fetch_redirect_response=False
            )

    def test_first_form_operational_state(self):
        browser = Browser()
        first_data = copy.deepcopy(FIRST_DATA)
        for state in OPERATIONAL_STATES:
            first_data.update({"first-email": 'test+client1@hometap.com', "first-state": state})
            response = browser.post('/inquiry/data/first/', first_data)
            self.assertEqual(response.status_code, 302)

    def test_first_form_undesirable_zip_code(self):
        browser = Browser()
        first_data = copy.deepcopy(FIRST_DATA)
        for undesirable_zip_code in UNDESIRABLE_ZIP_CODES:
            first_data.update({
                "first-email": 'test+client1@hometap.com',
                'first-zip_code': undesirable_zip_code
            })
            response = browser.post('/inquiry/data/first/', first_data)
            self.assertEqual(response.status_code, 302)

    def test_first_form_ok(self):
        browser = Browser()
        first_data = copy.deepcopy(FIRST_DATA)
        first_data.update({"first-email": 'test+client1@hometap.com'})
        response = browser.post('/inquiry/data/first/', first_data)
        self.assertEqual(response.status_code, 302)

    def test_get_email_no_client_session_or_form(self):
        # no fit quiz and the user messed up on the first step
        view = InquiryApplyWizard()
        view.initial_dict = {}
        view.request = self._get_request()
        self.assertEqual(view._get_email({}, 'first'), '')

    def test_get_email_from_first_form(self):
        # no fit quiz but the user entered the email before messing up
        view = InquiryApplyWizard()
        email = 'fit_quiz@ht.com'
        # yapf: disable
        self.assertEqual(
            view._get_email({'email': email, 'password1': 'testpassword1'}, 'first'),
            email
        )
        # yapf: enable

    def test_get_email_from_first_form_not_fit_quiz(self):
        # user filled a fit quiz but changed the email in the first step
        view = InquiryApplyWizard()
        request = self._get_request()
        fit_quiz_email = 'fit_quiz@ht.com'
        request.session['fit_email'] = fit_quiz_email
        request.session.save()
        view.request = request
        first_email = 'test+client1@hometap.com'
        # yapf: disable
        self.assertEqual(
            view._get_email({'email': first_email, 'password1': 'testpassword1'}, 'first'),
            first_email
        )
        # yapf: enable

    def test_get_email_from_fit_quiz(self):
        # user filled a fit quiz
        view = InquiryApplyWizard()
        view.initial_dict = {}

        # add the fit quiz email cookie to the session
        email = 'fit_quiz@ht.com'
        request = self._get_request()
        request.session['fit_email'] = email
        request.session.save()
        view.request = request
        self.assertEqual(view._get_email({}, 'first'), email)

    def test_get_wizard_step_event_data_empty(self):
        data = InquiryApplyWizard._get_wizard_step_event_data({}, [], 'first', 'submitted')
        self.assertEqual(data, {'tracking_status': 'first screen submitted'})

    def test_get_wizard_step_event_data_first(self):
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
        data = InquiryApplyWizard._get_wizard_step_event_data({
            'street': 'One First Street'
        }, exported_fields, 'first', 'submitted')
        self.assertEqual(
            data, {
                'street': 'One First Street',
                'tracking_status': 'first screen submitted'
            }
        )

    def test_get_wizard_step_event_data_home(self):
        exported_fields = [
            'property_type', 'primary_residence', 'rent_type', 'ten_year_duration_prediction',
            'home_value', 'household_debt'
        ]
        data = InquiryApplyWizard._get_wizard_step_event_data({
            'fake': 'fake'
        }, exported_fields, 'home', 'submitted')
        self.assertEqual(data, {'tracking_status': 'home screen submitted'})

    def test_get_wizard_step_event_data_signup(self):
        """ should not include the passwords """
        cleaned_data = {
            'phone_number': '617-399-0604',
            'password1': 'testpassword1',
            'password2': 'testpassword1',
            'sms_opt_in': 'on',
            'agree_to_terms': 'on',
        }
        exported_fields = ['phone_number', 'sms_opt_in', 'agree_to_terms']
        data = InquiryApplyWizard._get_wizard_step_event_data(
            cleaned_data, exported_fields, 'signup', 'submitted'
        )
        cleaned_data.pop('password1')
        cleaned_data.pop('password2')
        cleaned_data.update({'tracking_status': 'signup screen submitted'})
        self.assertDictEqual(data, cleaned_data)

    @mock.patch('inquiry.views.InquiryApplyWizard._get_wizard_step_event_data')
    @mock.patch('inquiry.views.segment_event')
    @skipIf(settings.REMOTE_ENVIRONMENT, "Remote environments require an IP address")
    def test_send_wizard_step_segment_event_first(
        self, mocked_segment_event, mocked_get_wizard_step_event_data
    ):
        view = InquiryApplyWizard()
        form = InquiryFirstForm(data=FIRST_FORM_EXAMPLE_DATA)
        self.assertTrue(form.is_valid())

        data = dict(FIRST_FORM_EXAMPLE_DATA, **{'tracking_status': 'first screen submitted'})
        mocked_get_wizard_step_event_data.return_value = data
        view._send_wizard_step_segment_event(
            'first', form, form.cleaned_data['email'], 'submitted'
        )  # yapf: disable

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
        cleaned_data = form.cleaned_data
        mocked_get_wizard_step_event_data.assert_called_once_with(
            cleaned_data, exported_fields, 'first', 'submitted'
        )
        mocked_segment_event.assert_called_once_with(
            cleaned_data['email'], 'investment inquiry - first screen submitted', data
        )

    @skipIf(settings.REMOTE_ENVIRONMENT, "Remote environments require an IP address")
    def test_send_wizard_step_segment_event(self):
        view = InquiryApplyWizard()
        step_data = {
            'first': (InquiryFirstForm, FIRST_FORM_EXAMPLE_DATA),
            'home': (InquiryHomeForm, HOME_FORM_EXAMPLE_DATA),
        }
        email = FIRST_FORM_EXAMPLE_DATA['email']
        for step, (form_class, form_data) in step_data.items():
            form = form_class(data=form_data)
            self.assertTrue(form.is_valid())
            view._send_wizard_step_segment_event(step, form, email, 'submitted')

    def test_fill_form_initial_empty(self):
        session = {}
        initial = {}
        InquiryApplyWizard.fill_form_initial(session, initial)
        self.assertEqual(initial, {})

    def test_fill_form_initial(self):
        session = {
            'not_fit_test': 'not_fit_test',
            FIT_QUIZ_SESSION_DATA_PREFIX + 'test': 'fit_test',
        }
        initial = {}
        InquiryApplyWizard.fill_form_initial(session, initial)
        self.assertEqual(initial, {'test': 'fit_test'})

        initial = {'something': 'something'}
        InquiryApplyWizard.fill_form_initial(session, initial)
        self.assertEqual(initial, {
            'test': 'fit_test',
            'something': 'something',
        })

    def test_multiple_inquiry_submissions_same_email(self):
        create_client_example()
        data = copy.deepcopy(CLIENT_EXAMPLE_DATA)
        data.update({
            "password1": "testpassword1",
            "password2": "testpassword1",
            "agree_to_terms": "on",
        })
        form = WizardClientUserCreationForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertEqual(form.errors['email'][0], 'User with this Email address already exists.')

    @mock.patch('inquiry.views._get_inquiry_segment_event_data')
    @mock.patch('inquiry.views.segment_event')
    @skipIf(settings.REMOTE_ENVIRONMENT, "Remote environments require an IP address")
    def test_event_e69_sent(self, mocked_segment_event, mocked_get_inquiry_segment_event_data):
        mocked_get_inquiry_segment_event_data.return_value = {'foo': 'bar'}

        browser = Browser()
        submit_inquiry_forms(browser, 'test+client1@hometap.com')
        client = Client.objects.get(user__email='test+client1@hometap.com')

        mocked_get_inquiry_segment_event_data.assert_called_once_with(client)
        # first four calls are to send the wizard step events
        self.assertEqual(mocked_segment_event.call_count, 5)
        mocked_segment_event.assert_called_with(
            'test+client1@hometap.com', 'investment inquiry - created account - server',
            mocked_get_inquiry_segment_event_data.return_value
        )

    @mock.patch('inquiry.views.InquiryApplyWizard._create_address')
    def test_done_address_fails(self, mocked_create_address):
        mocked_create_address.side_effect = ValidationError({
            'state': ['This field cannot be blank.']
        })
        browser = Browser()
        email = 'test+client1@hometap.com'
        response = submit_inquiry_forms(browser, email)
        self.assertEqual(response.status_code, 500)
        for _class in [Client, Address, Inquiry, InquiryInReview, SmsConsent]:
            self.assertFalse(_class.objects.exists())

    @mock.patch('inquiry.views.InquiryApplyWizard._create_inquiry')
    def test_done_inquiry_fails(self, mocked_create_inquiry):
        mocked_create_inquiry.side_effect = ValidationError({
            'client': ['Inquiry with this Client already exists.']
        })
        browser = Browser()
        email = 'test+client1@hometap.com'
        response = submit_inquiry_forms(browser, email)
        self.assertEqual(response.status_code, 500)
        for _class in [Client, Address, Inquiry, InquiryInReview, SmsConsent]:
            self.assertFalse(_class.objects.exists())

    @mock.patch('inquiry.views.transitions.ClientSubmitInquiry')
    def test_done_submit_inquiry_fails(self, mocked_client_submit_inquiry):
        mocked_client_submit_inquiry.side_effect = ValueError(
            "Invalid init value 'client' for Transition object"
        )
        browser = Browser()
        email = 'test+client1@hometap.com'
        response = submit_inquiry_forms(browser, email)
        self.assertEqual(response.status_code, 500)
        for _class in [Client, Address, Inquiry, InquiryInReview, SmsConsent]:
            self.assertFalse(_class.objects.exists())

    def test_done_sms_consent_true(self):
        browser = Browser()
        email = 'test+client1@hometap.com'
        response = submit_inquiry_forms(browser, email)
        self.assertEqual(response.status_code, 302)
        client = self._check_created_objects(email)
        self.assertEqual(SmsConsent.objects.count(), 1)
        sms_consent = SmsConsent.objects.get()
        self.assertEqual(client.sms_consent, sms_consent)

    def test_done_sms_consent_false(self):
        browser = Browser()
        email = 'test+client1@hometap.com'
        response = submit_inquiry_forms(
            browser, email, signup_overrides={
                "signup-sms_opt_in": "",
            }
        )
        self.assertEqual(response.status_code, 302)
        self._check_created_objects(email)
        self.assertFalse(SmsConsent.objects.exists())


@skipIf(settings.REMOTE_ENVIRONMENT, "Remote environments require an IP address")
class SubmitInquiryFormsTests(TestCase):
    """ tests the submit_inquiry_forms() helper function """

    def _verify_form_error(self, override_data, missing_field):
        browser = Browser()
        response = submit_inquiry_forms(browser, "test+client1@hometap.com", **override_data)
        self.assertIsNotNone(response.context)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', missing_field, 'This field is required.')

    def test_incomplete_first(self):
        self._verify_form_error({'first_overrides': {'first-street': ''}}, 'street')

    def test_incomplete_home(self):
        self._verify_form_error({'home_overrides': {'home-rent_type': ''}}, 'rent_type')

    def test_incomplete_homeowner(self):
        self._verify_form_error(
            {'homeowner_overrides': {'homeowner-first_name': ''}}, 'first_name'
        )  # yapf:disable

    def test_incomplete_signup(self):
        self._verify_form_error({'first_overrides': {'first-email': ''}}, 'email')

    def test_agree_to_terms_off(self):
        self._verify_form_error({
            'signup_overrides': {
                'signup-agree_to_terms': ''
            }
        }, 'agree_to_terms')

    def test_ok(self):
        browser = Browser()
        response = submit_inquiry_forms(browser, "test+client1@hometap.com")
        self.assertRedirects(
            response,
            '/inquiry/submitted/',
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=False
        )
        client = Client.objects.get(user__email="test+client1@hometap.com")
        self.assertFalse(client.email_confirmed)


@skipIf(settings.REMOTE_ENVIRONMENT, "Remote environments require an IP address")
class InquiryViewTests(TestCase):
    def test_multiple_inquiry_submissions_same_session(self):
        """
        This tests submitting multiple inquiry submissions during the same session. This is
        possible if someone submits one, does not confirm their email, and submits another. (After
        confirming, clients are unable to access the inquiry page). CustomFormToolsSessionStorage
        is used to fix bug EN-308 which would normally cause a KeyError in this same scenario
        (two inquiry wizard session view submissions in the same session). This test makes sure
        that that bug no longer occurs.
        """
        browser = Browser()
        response = submit_inquiry_forms(browser, "test+client1@hometap.com")
        self.assertRedirects(
            response,
            '/inquiry/submitted/',
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=False
        )
        response = submit_inquiry_forms(browser, "test+client2@hometap.com")
        self.assertRedirects(
            response,
            '/inquiry/submitted/',
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=False
        )

    def test_inquiry_submissions_same_email(self):
        """
        This tests submitting two inquiry submissions with the same email. This is possible
        if someone submits one, does not confirm their email, and submits another.
        """
        browser = Browser()
        response = submit_inquiry_forms(browser, "test+client1@hometap.com")
        self.assertRedirects(
            response,
            '/inquiry/submitted/',
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=False
        )
        response = submit_inquiry_forms(browser, "test+client1@hometap.com")
        self.assertEqual(response.status_code, 200)

    def test_event_25_in_context(self):
        """
        Test that the datalayer event dict for event 25 is in the context of the inquiry submitted
        view when appropriate
        """
        browser = Browser()
        response = submit_inquiry_forms(browser, "test+client1@hometap.com")
        self.assertEqual(response.status_code, 302)
        # Note: do not use assertRedirects because it does a GET which would conflict with
        # how DataLayerViewMixing.send_event_once_per_session works
        self.assertEqual(response.url, '/inquiry/submitted/')

        event_partial_string = (
            "[{\\u0022city\\u0022: \\u0022Cambridge\\u0022,"
            " \\u0022email\\u0022: \\u0022test+client1@hometap.com\\u0022"
        )

        # test that the event is in the html on the first load to be sent via datalayer to GTM
        response = browser.get('/inquiry/submitted/')
        self.assertContains(response, event_partial_string)

        # TODO(Charlie): restore after completing EN-331
        # # test that the event is not in the html on a second load of the page
        # response = browser.get('/inquiry/submitted/')
        # self.assertNotContains(response, event_partial_string)


class InquirySubmittedMethodTests(TestCase):
    def setUp(self):
        self.client = create_client_example()
        address = create_address_example()
        self.inquiry = create_inquiry_example(self.client, address)

        request = RequestFactory().get('/fake-path')
        request.user = self.client.user
        self.view = InquirySubmitted()
        self.view.request = request

    @mock.patch('inquiry.views._get_inquiry_segment_event_data')
    def test_get_event(self, mocked_get_inquiry_segment_event_data):
        mocked_get_inquiry_segment_event_data.return_value = {"foo": "bar"}
        event_data = self.view.get_event()
        mocked_get_inquiry_segment_event_data.assert_called_once_with(self.client)
        self.assertDictEqual(
            event_data, {
                "event": "investment inquiry - created account",
                "foo": "bar"
            }
        )


class GetInquirySegmentEventDataTests(TestCase):
    """ Tests for the _get_inquiry_segment_event_data function """

    def setUp(self):
        self.client = create_client_example()
        address = create_address_example()
        self.inquiry = create_inquiry_example(self.client, address)
        self.expected_event_data = {
            'tracking_status': 'investment inquiry submitted',
            'email': self.client.email,
            'phone': self.client.phone_number,
            'email_confirmed': self.client.email_confirmed,
            'friendly_id': self.client.friendly_id,
            'first_name': self.client.user.first_name,
            'last_name': self.client.user.last_name,
            'use_case_debts': self.inquiry.use_case_debts,
            'use_case_diversify': self.inquiry.use_case_diversify,
            'use_case_renovate': self.inquiry.use_case_renovate,
            'use_case_education': self.inquiry.use_case_education,
            'use_case_buy_home': self.inquiry.use_case_buy_home,
            'use_case_business': self.inquiry.use_case_business,
            'use_case_emergency': self.inquiry.use_case_emergency,
            'use_case_retirement': self.inquiry.use_case_retirement,
            'when_interested': self.inquiry.when_interested,
            'household_debt': self.inquiry.household_debt,
            'referrer_name': self.inquiry.referrer_name,
            'property_type': self.inquiry.property_type,
            'primary_residence': self.inquiry.primary_residence,
            'home_value': self.inquiry.home_value,
            'ten_year_duration_prediction': self.inquiry.ten_year_duration_prediction,
            'street': self.inquiry.address.street,
            'unit': self.inquiry.address.unit,
            'city': self.inquiry.address.city,
            'state': self.inquiry.address.state,
            'zip_code': self.inquiry.address.zip_code,
            'sms_allowed': True,
        }

    def test_success_sms_allowed_true(self):
        event_data = _get_inquiry_segment_event_data(self.client)
        self.assertDictEqual(event_data, self.expected_event_data)

    def test_success_sms_allowed_false(self):
        self.client.sms_consent = None
        self.client.save()
        expected_event_data = copy.deepcopy(self.expected_event_data)
        expected_event_data['sms_allowed'] = False
        event_data = _get_inquiry_segment_event_data(self.client)
        self.assertDictEqual(event_data, expected_event_data)

    def test_no_inquiry(self):
        client_2 = create_client_example(overrides={"email": "test+client2@hometap.com"})
        with self.assertRaises(ObjectDoesNotExist):
            _get_inquiry_segment_event_data(client_2)

    def test_not_client(self):
        reviewer = create_reviewer_example()
        with self.assertRaises(AttributeError):
            _get_inquiry_segment_event_data(reviewer)
