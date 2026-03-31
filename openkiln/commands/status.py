# status.py
#
# openkiln status
#
# Prints a summary of the current OpenKiln installation:
#   - core database connection status
#   - record counts by type
#   - installed skills and versions
#   - last workflow run (name, status, records in/out, time)
#
# Run at the start of every agent session to verify setup.
# If database connection fails, instructs user to run openkiln init.
# Supports --json flag for agent consumption.
