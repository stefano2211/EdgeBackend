"""Global ContextVars for the application.

Note: Previously held chat_stream_queue and active_thread_id for browser automation.
Kept as a module for future application-wide context variables.
"""

from contextvars import ContextVar
