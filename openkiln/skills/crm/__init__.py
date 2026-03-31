# openkiln/skills/crm/
# CRM skill — owns contacts and companies data.

__version__ = "0.1.0"

# Columns accepted by record import for each type.
# Must match column names in schema/001_initial.sql exactly.
# Used by: openkiln record import, openkiln record inspect

CONTACT_COLUMNS = [
    "first_name", "last_name", "full_name", "email", "phone",
    "linkedin_url", "company_name", "job_title", "department",
    "seniority", "city", "country", "timezone", "segment",
    "tags", "lead_score", "source", "last_contacted_at",
]

COMPANY_COLUMNS = [
    "name", "domain", "website_url", "linkedin_url", "industry",
    "employee_count", "employee_range", "hq_city", "hq_country",
    "description", "segment", "tags", "icp_score", "source",
]

# Natural dedup key per record type.
# Import skips rows where this field already exists in the skill db.
DEDUP_KEYS = {
    "contact": "email",
    "company": "domain",
}

# Supported record types for this skill
SUPPORTED_TYPES = list(DEDUP_KEYS.keys())
