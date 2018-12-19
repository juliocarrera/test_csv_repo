import pandas as pd

from django.conf import settings
from django.test import TestCase, override_settings

from core.utils import OPERATIONAL_STATES, EXPANSION_STATES, OTHER_STATES
from inquiry.outcomes import (
    INQUIRY_OUTCOME_SLUG_MAP, INQUIRY_OUTCOME_CONTEXTS, get_state_outcome_key,
    get_zip_code_outcome_key, get_state_zip_code_outcome_key
)
from inquiry.tests.test_utils import UNDESIRABLE_ZIP_CODES, NON_UNDESIRABLE_ZIP_CODES


@override_settings(
    ZIP_CODE_FORECAST=pd.
    read_csv(settings.PROJECT_PATH + '/apps/inquiry/tests/test_data/test_zip_codes.csv')
)
class InquiryOutcomesTests(TestCase):
    def test_inquiry_outcome_dicts(self):
        """ Tests that slugs in both outcome dicts are the same """
        self.assertEqual(
            set(INQUIRY_OUTCOME_SLUG_MAP.values()) ^ set(INQUIRY_OUTCOME_CONTEXTS.keys()), set()
        )

    def test_outcome_contexts(self):
        for slug in INQUIRY_OUTCOME_SLUG_MAP.values():
            self.assertTrue('message' in INQUIRY_OUTCOME_CONTEXTS[slug])

    def test_get_state_outcome_key(self):
        for state in OTHER_STATES:
            self.assertEqual(get_state_outcome_key(state), '1_other_states')
        for state in EXPANSION_STATES:
            self.assertEqual(get_state_outcome_key(state), '2_expansion_states')
        for state in OPERATIONAL_STATES:
            self.assertIsNone(get_state_outcome_key(state))

    def test_get_zip_code_outcome_key_no_data(self):
        self.assertIsNone(get_zip_code_outcome_key('00000'))

    def test_get_zip_code_outcome_key(self):
        for undesirable_zip_code in UNDESIRABLE_ZIP_CODES:
            self.assertEqual(
                get_zip_code_outcome_key(undesirable_zip_code), '3_undesirable_zip_code'
            )
        for zip_code in NON_UNDESIRABLE_ZIP_CODES:
            self.assertIsNone(get_zip_code_outcome_key(zip_code))

    def test_get_state_zip_code_outcome_key_other_states(self):
        for state in OTHER_STATES:
            for zip_code in UNDESIRABLE_ZIP_CODES + NON_UNDESIRABLE_ZIP_CODES:
                outcome_key, vetted_message = get_state_zip_code_outcome_key(state, zip_code)
                self.assertEqual(outcome_key, '1_other_states')
                self.assertEqual(vetted_message, 'rejected other states')

    def test_get_state_zip_code_outcome_key_expansion_states(self):
        for state in EXPANSION_STATES:
            for zip_code in UNDESIRABLE_ZIP_CODES + NON_UNDESIRABLE_ZIP_CODES:
                outcome_key, vetted_message = get_state_zip_code_outcome_key(state, zip_code)
                self.assertEqual(outcome_key, '2_expansion_states')
                self.assertEqual(vetted_message, 'rejected expansion states')

    def test_get_state_zip_code_outcome_key_operational_states(self):
        for state in OPERATIONAL_STATES:
            for undesirable_zip_code in UNDESIRABLE_ZIP_CODES:
                outcome_key, vetted_message = get_state_zip_code_outcome_key(
                    state, undesirable_zip_code
                )
                self.assertEqual(outcome_key, '3_undesirable_zip_code')
                self.assertEqual(vetted_message, 'rejected undesirable zip code')
            for zip_code in NON_UNDESIRABLE_ZIP_CODES:
                outcome_key, vetted_message = get_state_zip_code_outcome_key(state, zip_code)
                self.assertIsNone(outcome_key)
                self.assertEqual(vetted_message, '')
