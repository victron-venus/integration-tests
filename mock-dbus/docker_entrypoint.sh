#!/bin/bash
set -e
# Run as non-root user for security
# Note: This requires the mock_dbus.py to work with user permissions
exec "$@"
