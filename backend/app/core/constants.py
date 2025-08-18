"""
Application constants for role definitions, limits, and configuration.
"""

# Role constants
ROLE_LEADER = "LEADER"
ROLE_MEMBER = "MEMBER"

# Group limits
MAX_GROUP_MEMBERS = 20
MAX_POSTS_PER_ISSUE = 20

# Admin configuration
# TODO: Move to environment variables in production
ADMIN_EMAILS = [
    "admin@familynews.com"
]

# Status constants
GROUP_STATUS_ACTIVE = "ACTIVE"
GROUP_STATUS_INACTIVE = "INACTIVE"

ISSUE_STATUS_OPEN = "OPEN"
ISSUE_STATUS_CLOSED = "CLOSED"

DELIVERY_STATUS_PENDING = "pending"
DELIVERY_STATUS_PRINTING = "printing"
DELIVERY_STATUS_SHIPPING = "shipping"
DELIVERY_STATUS_DELIVERED = "delivered"

# Deadline types
DEADLINE_TYPE_SECOND_SUNDAY = "SECOND_SUNDAY"
DEADLINE_TYPE_FOURTH_SUNDAY = "FOURTH_SUNDAY"