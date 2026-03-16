"""Logging configuration."""

import logging

# Configure the root logger so all log messages follow the same format and level.
# This only needs to run once (usually at app startup).
logging.basicConfig(
    level=logging.INFO,                              # Only messages at INFO and above (INFO, WARNING, ERROR, CRITICAL) are shown; DEBUG is hidden.
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"  # Include logger name for better production tracing.
)

# Create a logger for this module. __name__ becomes something like "app.logger", so you can see which module produced each log line.
logger = logging.getLogger(__name__)
