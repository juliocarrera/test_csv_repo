from django.template.loader import render_to_string
from django.conf import settings

from formtools.wizard.storage.session import SessionStorage

from core.emails import send_reviewer_email


def send_new_inquiry_email(first_name, last_name):
    subject = 'New Hometap Inquiry Submission'
    message = render_to_string(
        'inquiry/new_inquiry_email.html', {
            'domain': settings.DOMAIN,
            'first_name': first_name,
            'last_name': last_name
        }
    )
    send_reviewer_email(subject, message)


class CustomFormToolsSessionStorage(SessionStorage):
    """
    This is a formtools wizard SessionStorage subclass. It is used to fix a bug (EN-308) in which
    the same session wizard view is used for an unauthenticated user and then an authenticated user
    within the same session and results in a KeyError. The code below prevents a key error. The fix
    comes from another popular python package (django-two-factor-auth) and avoids queuing up
    temporary files for deletion when there is not a prefix. However, for each use, the file names
    will be the same, so the existing files will be overwritten and they do not need to be deleted.
    https://github.com/Bouke/django-two-factor-auth/pull/135
    """

    def reset(self):
        if self.prefix in self.request.session:
            # reset() queues up temporary files created by SessionStorage for deletion before
            # calling init_data()
            super().reset()
        else:
            # init_data() resets values of all SessionStorage class attributes
            self.init_data()


def get_zip_code_forecast():
    """
    returns the cached zip code forecast dataframe or None if not yet cached
    """
    return settings.ZIP_CODE_FORECAST


def get_desirable_zip_codes(df):
    """
    returns a list of desirable zip codes
    a zip code is desirable if its data science forecast value is greater or equal to the
    risk value
    """
    # select all rows where the zip forecast is greater or equal to the risk value, using
    # the default index
    df1 = df.loc[df[settings.ZIP_FORECAST_COL] >= settings.ZIP_RISK_VALUE]
    return [str(value).zfill(5) for value in df1[settings.ZIP_CODE_COL].values]


def undesirable_zip_code(zip_code):
    """
    return False if there's no data for the zip code
    returns True if there's data and the zip code is not a desirable one

    desirable zip codes are those with a zip forecast value greater or equal to the
    zip forecast hurdle value in the zip forecast spreadsheet

    zip_code is expected to be in ddddd format otherwise it will be treated as no data
    for the zip code
    """
    df = get_zip_code_forecast()

    try:
        zip_as_int = int(zip_code)
    except ValueError:
        # treat as no data for this zip code
        return False

    # select all rows where zip code equals the given zip code, using the default index
    if not len(df.loc[df[settings.ZIP_CODE_COL] == zip_as_int]):
        # no data for this zip code
        return False

    # there is data for this zip code
    desirable_zip_codes = get_desirable_zip_codes(df)
    return zip_code not in desirable_zip_codes
