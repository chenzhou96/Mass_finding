from enum import Enum

class EventType(Enum):
    PAGE_SWITCH = "page_switch"
    STATUS_UPDATE = "status_update"
    LOG_MESSAGE = "log_message"
    ADD_FORMULA = "add_formula"
    ANALYSIS_FAILURE = "analysis_failure"
    VALIDATION_ERROR = "validation_error"
    FILE_LOAD_FAILURE = "file_load_failure"

class EventPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3