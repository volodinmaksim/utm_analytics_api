from enum import Enum


class ServiceType(str, Enum):
    RPP = "rpp"
    FARMA = "farma"
    SFBT = "sfbt"
    CBTBASE = "cbtbase"
    PSYGASTRO = "psygastro"


class PaymentEventType(str, Enum):
    PAYMENT_CLICK = "payment_click"
    PAYMENT_SUCCESS = "payment_success"


class SyncStatus(str, Enum):
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


class TelegramTemplateKind(str, Enum):
    SINGLE = "single"
    ALBUM = "album"


class TelegramTemplateStatus(str, Enum):
    COLLECTING = "collecting"
    READY = "ready"


class BroadcastRecipientStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class BroadcastStatus(str, Enum):
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]
