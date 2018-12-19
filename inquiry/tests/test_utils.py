from math import nan

import pandas as pd

from django.conf import settings
from django.test import TestCase, override_settings

from inquiry.models import Inquiry
from inquiry.utils import get_desirable_zip_codes, undesirable_zip_code

INQUIRY_EXAMPLE_DATA = {
    # 'client': client,
    'ip_address': "127.0.0.1",
    'property_type': Inquiry.PROPERTY_TYPES[0][0],
    'rent_type': Inquiry.RENT_TYPES[0][0],
    # 'address': address,
    'primary_residence': True,
    'ten_year_duration_prediction': Inquiry.TEN_YEAR_DURATION_TYPES[0][0],
    'home_value': 550000,
    'first_name': 'John',
    'last_name': 'Doe',
    'referrer_name': 'Jane Smith',
    'household_debt': 30000,
    'use_case_debts': True,
    'use_case_diversify': True,
    'use_case_renovate': True,
    'use_case_education': False,
    'use_case_buy_home': True,
    'use_case_business': False,
    'use_case_emergency': False,
    'use_case_retirement': True,
    'use_case_other': 'party',
    'when_interested': '3_to_6_months',
    'notes': 'Hometap is pretty cool',
}

# example pandas dataframe used to test zip code forecast vetting
DF_DATA = pd.DataFrame([
    {
        settings.ZIP_CODE_COL: 2445,
        '1 year CAGR': 0.06,
        '2 year CAGR': 0.0569,
        '3 year CAGR': 0.0536,
        '1 year returns': 0.06,
        settings.ZIP_FORECAST_COL: 0.1171,
        '3 year returns': 0.1695
    },
    {
        settings.ZIP_CODE_COL: 2457,
        '1 year CAGR': nan,
        '2 year CAGR': nan,
        '3 year CAGR': nan,
        '1 year returns': nan,
        settings.ZIP_FORECAST_COL: nan,
        '3 year returns': nan
    },
    {
        settings.ZIP_CODE_COL: 2171,
        '1 year CAGR': 0.0603,
        '2 year CAGR': 0.0543,
        '3 year CAGR': 0.0494,
        '1 year returns': 0.0603,
        settings.ZIP_FORECAST_COL: 0.0500,
        '3 year returns': 0.1557
    },
    {
        settings.ZIP_CODE_COL: 2030,
        '1 year CAGR': 0.0369,
        '2 year CAGR': 0.0306,
        '3 year CAGR': 0.0252,
        '1 year returns': 0.0369,
        settings.ZIP_FORECAST_COL: 0.0499,
        '3 year returns': 0.0774
    },
    {
        settings.ZIP_CODE_COL: 2138,
        '1 year CAGR': 0.0459,
        '2 year CAGR': 0.0364,
        '3 year CAGR': 0.0284,
        '1 year returns': 0.0459,
        settings.ZIP_FORECAST_COL: 0.0742,
        '3 year returns': 0.0877
    },
])

# undesirable zip codes in the zip code forecast test file
UNDESIRABLE_ZIP_CODES = ['02072', '02467']
# includes zip code with no data and desirable zip codes in the zip code forecast test file
NON_UNDESIRABLE_ZIP_CODES = ['00000', '02445', '02138', '02171', '02138-1234', 'abcde-1234']


def _create_model_obj(model_class, **kwargs):
    obj = model_class(**kwargs)
    obj.full_clean()
    obj.save()
    return obj


def create_inquiry(**kwargs):
    return _create_model_obj(Inquiry, **kwargs)


def create_inquiry_example(client, address):
    # update the default friendly id generated from the state in create_client_example()
    client.friendly_id = client._generate_unique_friendly_id(address.state.upper())
    client.full_clean()
    client.save()

    return create_inquiry(
        client=client,
        address=address,
        **INQUIRY_EXAMPLE_DATA,
    )


class GetDesirableZipCodesTests(TestCase):
    """ tests the get_desirable_zip_codes() function """

    @override_settings(ZIP_CODE_FORECAST=DF_DATA)
    def test_get_desirable_zip_codes(self):
        zips = get_desirable_zip_codes(settings.ZIP_CODE_FORECAST)
        self.assertEqual(len(zips), 3)
        self.assertTrue('02445' in zips)
        self.assertTrue('02171' in zips)  # zip code forecast is equal to settings.ZIP_RISK_VALUE
        self.assertTrue('02138' in zips)


@override_settings(
    ZIP_CODE_FORECAST=pd.
    read_csv(settings.PROJECT_PATH + '/apps/inquiry/tests/test_data/test_zip_codes.csv')
)
class UndesirableZipCodeTests(TestCase):
    """ tests the undesirable_zip_code() function """

    def test_undesirable_zip_code_no_data(self):
        self.assertFalse(undesirable_zip_code('00000'))
        self.assertFalse(undesirable_zip_code('abcde-1234'))

    def test_undesirable_zip_code_undesirable(self):
        for zip_code in UNDESIRABLE_ZIP_CODES:
            self.assertTrue(undesirable_zip_code(zip_code))

    def test_undesirable_zip_code_desirable(self):
        for zip_code in NON_UNDESIRABLE_ZIP_CODES:
            self.assertFalse(undesirable_zip_code(zip_code))
