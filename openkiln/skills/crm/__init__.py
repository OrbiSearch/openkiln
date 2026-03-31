# openkiln/skills/crm/
# CRM skill — owns contacts and companies data.

__version__ = "0.1.0"

# Columns accepted by record import for each type.
# Must match column names in schema/001_initial.sql exactly.
# Used by: openkiln record import, openkiln record inspect

CONTACT_COLUMNS = [
    "first_name", "last_name", "full_name", "email", "phone",
    "linkedin_url", "company_name", "job_title", "department",
    "seniority", "city", "country", "timezone",
    "tags", "lead_score", "source", "last_contacted_at",
    "lifecycle_stage", "lead_status",
    # deprecated: segment (kept for import backwards compatibility)
    "segment",
]

COMPANY_COLUMNS = [
    "name", "domain", "website_url", "linkedin_url", "industry",
    "employee_count", "employee_range", "hq_city", "hq_country",
    "description", "tags", "icp_score", "source",
    "lifecycle_stage", "icp_tier",
    # deprecated: segment (kept for import backwards compatibility)
    "segment",
]

# Valid values for enumerated fields.
# Used by CLI commands for validation and help text.
LIFECYCLE_STAGES = [
    "cold", "lead", "mql", "sql",
    "opportunity", "customer", "evangelist",
]

LEAD_STATUSES = [
    "new", "contacted", "replied", "interested",
    "not_interested", "unqualified", "bad_timing",
]

ICP_TIERS = ["tier_1", "tier_2", "tier_3"]

# Natural dedup key per record type.
# Import skips rows where this field already exists in the skill db.
DEDUP_KEYS = {
    "contact": "email",
    "company": "domain",
}

# Supported record types for this skill
SUPPORTED_TYPES = list(DEDUP_KEYS.keys())
