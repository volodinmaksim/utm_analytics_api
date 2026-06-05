class BroadcastError(Exception):
    """Base exception for broadcast domain errors."""


class TemplateSendError(BroadcastError):
    """Broadcast/template configuration is invalid."""


class TelegramRecipientSkipped(BroadcastError):
    """Recipient cannot receive this message anymore."""


class TelegramTemporaryError(BroadcastError):
    """Temporary Telegram/API error, can be retried."""
