from datetime import datetime, timezone
from decimal import Decimal

from analytics_app.app.models.orm import PaymentEventType, ServiceType
from analytics_app.app.services.payment_ingest import PaymentIngestBatch
from analytics_app.app.services.payment_matching import MatchedPaymentEvent

batch = PaymentIngestBatch(
    tracked_sheet_id=1,
    rows_read=5,
    processed_row_num=6,
    processed_fingerprint='last-fingerprint',
    events=(
        MatchedPaymentEvent(
            service=ServiceType.RPP,
            source_sheet_name='????1',
            source_row_num=2,
            source_fingerprint='fp-click',
            platform_id=123,
            email='user@example.com',
            full_name='Test User',
            nickname='tester',
            event_date=datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc),
            event_type=PaymentEventType.PAYMENT_CLICK,
            amount=None,
            raw_payment_value='oplata',
            user_id=10,
            farma_user_id=None,
            matched_user_tg_id=123,
        ),
        MatchedPaymentEvent(
            service=ServiceType.RPP,
            source_sheet_name='????1',
            source_row_num=3,
            source_fingerprint='fp-success',
            platform_id=123,
            email='user@example.com',
            full_name='Test User',
            nickname='tester',
            event_date=datetime(2026, 3, 18, 12, 5, tzinfo=timezone.utc),
            event_type=PaymentEventType.PAYMENT_SUCCESS,
            amount=Decimal('1500.00'),
            raw_payment_value='1500',
            user_id=10,
            farma_user_id=None,
            matched_user_tg_id=123,
        ),
    ),
)

print({
    'tracked_sheet_id': batch.tracked_sheet_id,
    'rows_read': batch.rows_read,
    'processed_row_num': batch.processed_row_num,
    'processed_fingerprint': batch.processed_fingerprint,
    'events_count': len(batch.events),
    'event_types': [event.event_type.value for event in batch.events],
})
