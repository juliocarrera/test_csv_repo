import copy

from django.test import TestCase

from core.tests.test_helpers import ADDRESS_EXAMPLE_DATA
from custom_auth.forms import ClientUserCreationForm
from custom_auth.tests.test_helpers import create_client_example
from inquiry.forms import InquiryHomeForm, InquiryFirstForm, WizardClientUserCreationForm
from inquiry.tests.test_utils import INQUIRY_EXAMPLE_DATA

FIRST_FORM_EXAMPLE_DATA = dict(
    ADDRESS_EXAMPLE_DATA, **{
        'use_case_debts': True,
        'use_case_diversify': True,
        'use_case_renovate': True,
        'use_case_education': False,
        'use_case_buy_home': True,
        'use_case_business': False,
        'use_case_emergency': False,
        'use_case_retirement': True,
        'use_case_other': 'party',
        "email": "test+client1@hometap.com",
    }
)
HOME_FORM_EXAMPLE_DATA = {
    'ten_year_duration_prediction': 'over_10',
    'home_value': 1000000,
    'primary_residence': 'True',
    'property_type': 'sf',
    'rent_type': 'no',
    'household_debt': 500000,
}


class WizardClientUserCreationFormTests(TestCase):
    def setUp(self):
        self.data = {
            "password1": "testpassword1",
            "password2": "testpassword1",
            "phone_number": "555-555-5555",
            "sms_opt_in": "on",
            "agree_to_terms": "on",
        }

    def test_is_valid_no_data(self):
        form = WizardClientUserCreationForm(data={})
        self.assertFalse(form.is_valid())
        # the wizard user creation form doesn't require the email -- it gets it from the first step
        for required_field in [f for f in ClientUserCreationForm.Meta.fields if f != 'email']:
            self.assertEqual(form.errors[required_field], ["This field is required."])

    def test_is_valid_valid_data(self):
        form = WizardClientUserCreationForm(data=self.data)
        self.assertTrue(form.is_valid())

    def test_is_valid_phone_missing(self):
        data = copy.deepcopy(self.data)
        data.pop('phone_number')
        form = WizardClientUserCreationForm(data=data)
        self.assertFalse(form.is_valid())


class InquiryHomeFormTests(TestCase):
    def test_is_valid_no_data(self):
        form = InquiryHomeForm(data={})
        self.assertFalse(form.is_valid())
        for required_field in InquiryHomeForm.Meta.fields:
            self.assertEqual(form.errors[required_field], ["This field is required."])

    def test_is_valid(self):
        form = InquiryHomeForm(data=INQUIRY_EXAMPLE_DATA)
        self.assertTrue(form.is_valid())

    def test_clean_true(self):
        form = InquiryHomeForm(HOME_FORM_EXAMPLE_DATA)
        self.assertTrue(form.is_valid())


class InquiryFirstFormTests(TestCase):
    def test_is_valid_no_data(self):
        form = InquiryFirstForm(data={})
        self.assertFalse(form.is_valid())
        for required_field in InquiryFirstForm.Meta.fields:
            # use cases have their own test
            if required_field in [
                'referrer_name', 'use_case_debts', 'use_case_education', 'use_case_diversify',
                'use_case_buy_home', 'use_case_renovate', 'use_case_business', 'use_case_emergency',
                'use_case_retirement', 'use_case_other', 'notes'
            ]:
                continue
            self.assertEqual(form.errors[required_field], ["This field is required."])

    def test_is_valid(self):
        form = InquiryFirstForm(data=FIRST_FORM_EXAMPLE_DATA)
        self.assertTrue(form.is_valid())

    def test_is_valid_no_email(self):
        data = copy.deepcopy(FIRST_FORM_EXAMPLE_DATA)
        data.pop('email')
        form = InquiryFirstForm(data=data)
        self.assertFalse(form.is_valid())

    def test_clean_email(self):
        form = InquiryFirstForm(data=FIRST_FORM_EXAMPLE_DATA)
        self.assertTrue(form.is_valid())

    def test_clean_email_existing_user(self):
        create_client_example()
        form = InquiryFirstForm(data=FIRST_FORM_EXAMPLE_DATA)
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 1)
        self.assertEqual(form.errors['email'], ['User with this Email address already exists.'])

    def test_no_use_case_selected(self):
        """ Tests error when no use case selected or input """
        data = copy.deepcopy(FIRST_FORM_EXAMPLE_DATA)
        form = InquiryFirstForm(data=data)
        self.assertTrue(form.is_valid())

        for use_case in (
            'use_case_debts',
            'use_case_education',
            'use_case_diversify',
            'use_case_buy_home',
            'use_case_renovate',
            'use_case_business',
            'use_case_emergency',
            'use_case_retirement',
        ):
            data[use_case] = False
        data['use_case_other'] = ''

        form = InquiryFirstForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['use_case_other'], [
                "This field is required if no other use cases are selected."
            ]
        )
