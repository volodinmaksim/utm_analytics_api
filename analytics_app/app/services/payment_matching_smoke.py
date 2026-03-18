from datetime import datetime, timezone
from decimal import Decimal

from analytics_app.app.models.orm import PaymentEventType, ServiceType
from analytics_app.app.services.payment_matching import enrich_payment_event
from analytics_app.app.services.payment_normalization import NormalizedPaymentEvent


def build_event(service: ServiceType, platform_id: int | None) -> NormalizedPaymentEvent:
    return NormalizedPaymentEvent(
        service=service,
        source_sheet_name='????1',
        source_row_num=2,
        source_fingerprint='fingerprint',
        platform_id=platform_id,
        email='user@example.com',
        full_name='Test User',
        nickname='tester',
        event_date=datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc),
        event_type=PaymentEventType.PAYMENT_SUCCESS,
        amount=Decimal('1500.00'),
        raw_payment_value='1500',
    )


matched_rpp = enrich_payment_event(
    build_event(ServiceType.RPP, 12345),
    user_id=10,
    farma_user_id=None,
    matched_user_tg_id=12345,
)
print({
    'case': 'matched_rpp',
    'user_id': matched_rpp.user_id,
    'farma_user_id': matched_rpp.farma_user_id,
    'matched_user_tg_id': matched_rpp.matched_user_tg_id,
})

matched_farma = enrich_payment_event(
    build_event(ServiceType.FARMA, 67890),
    user_id=None,
    farma_user_id=20,
    matched_user_tg_id=67890,
)
print({
    'case': 'matched_farma',
    'user_id': matched_farma.user_id,
    'farma_user_id': matched_farma.farma_user_id,
    'matched_user_tg_id': matched_farma.matched_user_tg_id,
})

unmatched = enrich_payment_event(
    build_event(ServiceType.RPP, None),
    user_id=None,
    farma_user_id=None,
    matched_user_tg_id=None,
)
print({
    'case': 'unmatched',
    'user_id': unmatched.user_id,
    'farma_user_id': unmatched.farma_user_id,
    'matched_user_tg_id': unmatched.matched_user_tg_id,
})
