import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from analytics_app.app.db import settings
from analytics_app.app.clients.google_sheets import GoogleSheetRow
from analytics_app.app.models import PaymentEventType, ServiceType

_AMOUNT_SUFFIX_RE = re.compile(r"\s*(?:\u20bd|\u0440\u0443\u0431\.?|rub)?\s*$", re.IGNORECASE)
_DATE_FORMATS = (
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
)


class PaymentRowStatus(str, Enum):
    EMPTY = "empty"
    NORMALIZED = "normalized"
    INVALID = "invalid"


@dataclass(slots=True, frozen=True)
class SheetSourceContext:
    tracked_sheet_id: int
    service: ServiceType
    spreadsheet_id: str
    sheet_name: str
    sheet_gid: int | None = None


@dataclass(slots=True)
class PaymentEventPayload:
    tracked_sheet_id: int
    service: ServiceType
    source_sheet_name: str
    source_row_num: int
    source_fingerprint: str
    platform_id: int | None
    email: str | None
    full_name: str | None
    nickname: str | None
    event_date: datetime | None
    event_type: PaymentEventType
    amount: Decimal | None
    raw_payment_value: str
    user_id: int | None = None
    farma_user_id: int | None = None
    sfbt_user_id: int | None = None
    matched_user_tg_id: int | None = None

    @classmethod
    def from_sheet_row(
        cls,
        row: GoogleSheetRow,
        context: SheetSourceContext,
        *,
        fingerprint: str,
        platform_id: int | None,
        event_date: datetime | None,
        event_type: PaymentEventType,
        amount: Decimal | None,
        raw_payment_value: str,
    ) -> "PaymentEventPayload":
        return cls(
            tracked_sheet_id=context.tracked_sheet_id,
            service=context.service,
            source_sheet_name=context.sheet_name,
            source_row_num=row.source_row_num,
            source_fingerprint=fingerprint,
            platform_id=platform_id,
            email=_clean_text(row.email),
            full_name=_clean_text(row.full_name),
            nickname=_clean_text(row.nickname),
            event_date=event_date,
            event_type=event_type,
            amount=amount,
            raw_payment_value=raw_payment_value,
        )


@dataclass(slots=True, frozen=True)
class PaymentRowResult:
    status: PaymentRowStatus
    row_num: int
    payload: PaymentEventPayload | None = None
    reason: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.payload is not None


def normalize_payment_row(row: GoogleSheetRow, context: SheetSourceContext) -> PaymentRowResult:
    if row.is_empty:
        return PaymentRowResult(
            status=PaymentRowStatus.EMPTY,
            row_num=row.source_row_num,
            reason="empty_row",
        )

    raw_payment_value = _clean_text(row.raw_payment_value)
    if raw_payment_value is None:
        return PaymentRowResult(
            status=PaymentRowStatus.INVALID,
            row_num=row.source_row_num,
            reason="missing_raw_payment_value",
        )

    event_type, amount = _classify_payment_value(raw_payment_value)
    if event_type is None:
        return PaymentRowResult(
            status=PaymentRowStatus.INVALID,
            row_num=row.source_row_num,
            reason="unsupported_payment_value",
        )

    platform_id = _parse_platform_id(row.platform_id_raw)
    event_date = _parse_event_date(row.event_date_raw)
    fingerprint = _build_source_fingerprint(
        context=context,
        row_num=row.source_row_num,
        platform_id=platform_id,
        raw_payment_value=raw_payment_value,
        event_date=event_date,
        event_date_raw=row.event_date_raw,
    )

    return PaymentRowResult(
        status=PaymentRowStatus.NORMALIZED,
        row_num=row.source_row_num,
        payload=PaymentEventPayload.from_sheet_row(
            row,
            context,
            fingerprint=fingerprint,
            platform_id=platform_id,
            event_date=event_date,
            event_type=event_type,
            amount=amount,
            raw_payment_value=raw_payment_value,
        ),
    )


def _build_source_fingerprint(
    *,
    context: SheetSourceContext,
    row_num: int,
    platform_id: int | None,
    raw_payment_value: str,
    event_date: datetime | None,
    event_date_raw: str | None,
) -> str:
    source_sheet_key = str(context.sheet_gid) if context.sheet_gid is not None else context.sheet_name
    event_date_part = event_date.isoformat() if event_date is not None else (event_date_raw or "")
    raw = "|".join(
        (
            context.spreadsheet_id.strip(),
            source_sheet_key.strip(),
            str(row_num),
            "" if platform_id is None else str(platform_id),
            raw_payment_value.strip().lower(),
            event_date_part.strip(),
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _classify_payment_value(raw_payment_value: str) -> tuple[PaymentEventType | None, Decimal | None]:
    if raw_payment_value.strip().lower() == "oplata":
        return PaymentEventType.PAYMENT_CLICK, None

    amount = _parse_amount(raw_payment_value)
    if amount is None:
        return None, None
    return PaymentEventType.PAYMENT_SUCCESS, amount


def _parse_amount(raw_payment_value: str) -> Decimal | None:
    normalized = raw_payment_value.strip().replace("\xa0", " ")
    normalized = _AMOUNT_SUFFIX_RE.sub("", normalized)
    normalized = normalized.replace(" ", "")

    if not normalized:
        return None

    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")

    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", normalized):
        return None

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _parse_platform_id(raw_platform_id: str | None) -> int | None:
    value = _clean_text(raw_platform_id)
    if value is None:
        return None

    normalized = value.replace(" ", "")
    if normalized.isdigit() or (normalized.startswith("-") and normalized[1:].isdigit()):
        return int(normalized)

    try:
        decimal_value = Decimal(normalized.replace(",", "."))
    except InvalidOperation:
        return None

    if decimal_value == decimal_value.to_integral_value():
        return int(decimal_value)
    return None


def _parse_event_date(raw_event_date: str | None) -> datetime | None:
    value = _clean_text(raw_event_date)
    if value is None:
        return None

    normalized_tz = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized_tz)
    except ValueError:
        parsed = None

    if parsed is not None:
        return _apply_default_timezone(parsed)

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            return _apply_default_timezone(parsed)
        except ValueError:
            continue

    return None


def _apply_default_timezone(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value

    try:
        tzinfo = ZoneInfo(settings.PAYMENTS_SOURCE_TIMEZONE)
    except ZoneInfoNotFoundError:
        tzinfo = timezone.utc
    return value.replace(tzinfo=tzinfo)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
