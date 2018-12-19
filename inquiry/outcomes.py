"""
Contains logic for determining what vetting response to give to an inquiry (an 'outcome'), if any.
Contains template context passed to view when displaying an outcome.

Logic and outcome key IDs are from Google Drive Doc 'inquiry outcomes':
https://docs.google.com/spreadsheets/d/1rF7kAiadlgMiBuRFug3vUWGJzENqWz91CA_z_Oq1Moc/edit#gid=0
"""
import logging as logging_

from core.utils import EXPANSION_STATES, OTHER_STATES
from inquiry.utils import undesirable_zip_code

logger = logging_.getLogger(__name__)

# Map of outcome keys to outcome slugs. Outcome keys are used internally. Outcome slugs are used
# externally in outcome URLs. Outcome slugs are created using the first letter of each word in the
# outcome key. If the slug is less than 4 characters long, it is left-padded with r's. Using a
# slug avoids revealing our internal outcome keys as well as someone being able to easily
# iterate all possible outcome pages. Integer in outcome key name refers to outcome ID in the
# Drive Document.
INQUIRY_OUTCOME_SLUG_MAP = {
    "1_other_states": "rros",
    "2_expansion_states": "rres",
    "3_undesirable_zip_code": "ruzc",
}

# Map of outcome slugs to outcome context for template
INQUIRY_OUTCOME_CONTEXTS = {
    "rros": {
        "message": "TBD -- sorry other state",
    },
    "rres": {
        "message": "TBD -- sorry expansion state",
    },
    "ruzc": {
        "message": "TBD -- sorry undesirable zip code",
    },
}


def get_outcome_context(outcome_slug):
    return INQUIRY_OUTCOME_CONTEXTS[outcome_slug]


def get_state_outcome_key(state):
    """ returns the rejection outcome key corresponding to the given state or None """
    if state in OTHER_STATES:
        return '1_other_states'
    if state in EXPANSION_STATES:
        return '2_expansion_states'
    return None


def get_zip_code_outcome_key(zip_code):
    """ returns the rejection outcome key corresponding to the given zip code or None """
    if undesirable_zip_code(zip_code):
        return '3_undesirable_zip_code'
    return None


def get_state_zip_code_outcome_key(state, zip_code):
    """
    returns the rejection outcome key corresponding to a non-operational state, or if it's an
    operational state, the rejection outcome key corresponding to an undesirable zip code
    or None """
    outcome_key = get_state_outcome_key(state)
    if outcome_key is None:
        # state is operational -- check the zip code
        outcome_key = get_zip_code_outcome_key(zip_code)
    if outcome_key is not None:
        return (outcome_key, 'rejected ' + ' '.join(outcome_key.split('_')[1:]))
    return (None, '')
