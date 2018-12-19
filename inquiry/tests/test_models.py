from django.core.exceptions import ValidationError
from django.test import TestCase

from core.tests.test_helpers import create_address_example
from custom_auth.tests.test_helpers import create_client_example
from fit_quiz.tests.test_models import create_fit_quiz_example
from inquiry.tests.test_utils import create_inquiry_example, INQUIRY_EXAMPLE_DATA


class InquiryTests(TestCase):
    def setUp(self):
        self.address = create_address_example()
        self.client = create_client_example()

    def test_inquiry_from_fit_quiz(self):
        fit_quiz = create_fit_quiz_example(self.client, self.address)
        inquiry = create_inquiry_example(fit_quiz.client, self.address)
        self.assertEqual(fit_quiz.client, inquiry.client)

    def test_inquiry_same_client(self):
        create_inquiry_example(self.client, self.address)
        with self.assertRaises(ValidationError):
            create_inquiry_example(self.client, self.address)

    def test_inquiry(self):
        inquiry = create_inquiry_example(self.client, self.address)
        for key, val in INQUIRY_EXAMPLE_DATA.items():
            self.assertEqual(getattr(inquiry, key), val)

    def test_as_dict_verbose(self):
        """ Test that inquiry.as_dict_verbose does not raise an exception """
        inquiry = create_inquiry_example(self.client, self.address)
        inquiry.as_dict_verbose

    def test_full_name_short(self):
        inquiry = create_inquiry_example(self.client, self.address)
        self.assertEqual(inquiry.full_name_short, inquiry.first_name + ' ' + inquiry.last_name)
