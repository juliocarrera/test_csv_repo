import unittest

from django.conf import settings
from django.test import TestCase


@unittest.skipIf(settings.REMOTE_ENVIRONMENT, "Remote environments require an IP address")
class InquiryURLTests(TestCase):
    def test_base_url(self):
        response = self.client.get('/inquiry/data/')
        self.assertEqual(response.status_code, 302)

    def test_address_url(self):
        response = self.client.get('/inquiry/data/0/')
        self.assertEqual(response.status_code, 302)

    def test_home_url(self):
        response = self.client.get('/inquiry/data/1/')
        self.assertEqual(response.status_code, 302)

    def test_homeowner_url(self):
        response = self.client.get('/inquiry/data/2/')
        self.assertEqual(response.status_code, 302)

    def test_signup_url(self):
        response = self.client.get('/inquiry/data/3/')
        self.assertEqual(response.status_code, 302)

    def test_apply_url(self):
        response = self.client.get('/inquiry/apply/')
        self.assertEqual(response.status_code, 301)

    def test_submitted_url(self):
        response = self.client.get('/inquiry/submitted/')
        self.assertEqual(response.status_code, 302)
