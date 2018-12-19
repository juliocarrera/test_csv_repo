from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.forms.models import model_to_dict

from core.utils import model_to_dict_verbose
from core.models import TimestampedModel, Address, UUIDModel, UseCaseModel, WhenInterestedModel
from core.pricing import MIN_HOME_VALUE, MAX_HOME_VALUE
from custom_auth.models import Client
from .utils import send_new_inquiry_email


class Inquiry(UseCaseModel, UUIDModel, WhenInterestedModel, TimestampedModel):
    class Meta:
        verbose_name_plural = 'inquiries'

    # META DATA
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='inquiry')
    ip_address = models.GenericIPAddressField(null=True)
    # there are also `created_at` and `modified_at` fields from the TimestampedModel
    # abstract base class

    # HOME DATA
    PROPERTY_TYPES = (
        ('sf', 'Single-Family Home'),
        ('mf', 'Multi-Family Home'),
        ('co', 'Condo, Townhouse or Apartment'),
        ('va', 'Vacation or Rental Property'),
    )
    property_type = models.CharField(max_length=2, choices=PROPERTY_TYPES)

    RENT_TYPES = (
        ('no', 'No'),
        ('under_14', 'Yes, 14 days or fewer per year'),
        ('over_14', 'Yes, more than 14 days per year'),
    )
    rent_type = models.CharField(max_length=8, choices=RENT_TYPES)

    address = models.ForeignKey(Address, null=True, on_delete=models.SET_NULL)
    primary_residence = models.BooleanField()

    TEN_YEAR_DURATION_TYPES = (
        ('over_10', 'Yes, more than 10 years'),
        ('10_or_less', 'No, 10 years or fewer'),
        ('dont_know', "Don't know"),
    )
    ten_year_duration_prediction = models.CharField(
        max_length=10, choices=TEN_YEAR_DURATION_TYPES, default='10_or_less'
    )

    home_value = models.PositiveIntegerField(
        validators=[MinValueValidator(MIN_HOME_VALUE),
                    MaxValueValidator(MAX_HOME_VALUE)]
    )

    # HOMEOWNER DATA
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    referrer_name = models.CharField(max_length=60, blank=True)
    household_debt = models.PositiveIntegerField(validators=[MaxValueValidator(99999999)])

    notes = models.CharField(max_length=1000, blank=True)

    def __str__(self):
        return "Inquiry submission by {0} {1} for {2}".format(
            self.first_name, self.last_name, self.address
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # notify staff that there is a new Inquiry
        send_new_inquiry_email(self.first_name, self.last_name)

    @property
    def full_name_short(self):
        return self.first_name + ' ' + self.last_name

    @property
    def as_dict(self):
        return model_to_dict(self)

    @property
    def as_dict_verbose(self):
        return model_to_dict_verbose(self)
