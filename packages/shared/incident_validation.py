STATUSES = {"open", "in_progress", "resolved", "discarded"}

VALID_STATUS_TRANSITIONS = {
    "open": {"in_progress", "discarded"},
    "in_progress": {"resolved", "discarded"},
    "resolved": set(),
    "discarded": set(),
}


class ValidationError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)


def validate_status_transition(current_status, next_status):
    if next_status not in STATUSES:
        raise ValidationError("status", "Invalid status")

    if next_status not in VALID_STATUS_TRANSITIONS.get(current_status, set()):
        raise ValidationError(
            "status",
            f"Cannot transition from {current_status} to {next_status}",
        )

    return True
