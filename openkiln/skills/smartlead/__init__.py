# openkiln/skills/smartlead/
# Smartlead skill — campaign management and lead push via Smartlead API.
# API: https://server.smartlead.ai/api/v1

__version__ = "0.1.0"

# Smartlead lead fields accepted when pushing contacts.
# Maps to Smartlead's lead_list item schema.
LEAD_COLUMNS = [
    "email", "first_name", "last_name", "company_name",
    "phone_number", "website", "location", "linkedin_profile",
    "company_url",
]

# Contact field -> Smartlead lead field mapping.
# Used when pushing contacts to a Smartlead campaign.
CONTACT_TO_SMARTLEAD = {
    "email": "email",
    "first_name": "first_name",
    "last_name": "last_name",
    "company_name": "company_name",
    "phone": "phone_number",
    "linkedin_url": "linkedin_profile",
    "city": "location",
}

# Smartlead campaign statuses
CAMPAIGN_STATUSES = ["DRAFTED", "ACTIVE", "PAUSED", "STOPPED", "ARCHIVED"]

# Supported record types for this skill (for workflow sink)
SUPPORTED_TYPES = ["contact"]

# Natural dedup key — when pushing contacts, email is the unique identifier
DEDUP_KEYS = {
    "contact": "email",
}
