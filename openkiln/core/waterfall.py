# core/waterfall.py
#
# Waterfall transform.
# Tries multiple providers in order for a given field
# (e.g. email validation). Falls through to the next
# provider if the current one returns no result.
