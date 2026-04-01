# providers/smartlead.py
#
# Smartlead provider integration.
# Delegates to SmartleadSink workflow interface.
#
# This module exists for backward compatibility. The canonical
# implementation is openkiln.skills.smartlead.workflow.SmartleadSink.

from openkiln.skills.smartlead.workflow import SmartleadSink

__all__ = ["SmartleadSink"]
