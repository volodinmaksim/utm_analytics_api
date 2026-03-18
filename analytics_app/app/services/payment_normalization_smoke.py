from decimal import Decimal

from analytics_app.app.clients.google_sheets import GoogleSheetRow
from analytics_app.app.models.orm import PaymentEventType, ServiceType
from analytics_app.app.services.payment_normalization import normalize_payment_row

TEST_ROWS = (
    GoogleSheetRow(
        source_row_num=2,
        full_name='???? ??????',
        email='ivan@example.com',
        raw_payment_value='oplata',
        nickname='ivan',
        event_date_raw='18.03.2026 10:30',
        platform_id_raw='12345',
        raw_values=('???? ??????', 'ivan@example.com', 'oplata', 'ivan', '18.03.2026 10:30', '', '', '', '', '12345'),
    ),
    GoogleSheetRow(
        source_row_num=3,
        full_name='???? ??????',
        email='petr@example.com',
        raw_payment_value='1 500,50',
        nickname='petr',
        event_date_raw='2026-03-18',
        platform_id_raw='67890',
        raw_values=('???? ??????', 'petr@example.com', '1 500,50', 'petr', '2026-03-18', '', '', '', '', '67890'),
    ),
    GoogleSheetRow(
        source_row_num=4,
        full_name=None,
        email=None,
        raw_payment_value=None,
        nickname=None,
        event_date_raw=None,
        platform_id_raw=None,
        raw_values=('', '', '', '', '', '', '', '', '', ''),
    ),
    GoogleSheetRow(
        source_row_num=5,
        full_name='Bad Value',
        email='bad@example.com',
        raw_payment_value='unknown',
        nickname='bad',
        event_date_raw='18/03/2026',
        platform_id_raw='abc',
        raw_values=('Bad Value', 'bad@example.com', 'unknown', 'bad', '18/03/2026', '', '', '', '', 'abc'),
    ),
    GoogleSheetRow(
        source_row_num=6,
        full_name='No Platform',
        email='np@example.com',
        raw_payment_value='1500',
        nickname='nop',
        event_date_raw='18.03.2026',
        platform_id_raw=None,
        raw_values=('No Platform', 'np@example.com', '1500', 'nop', '18.03.2026', '', '', '', '', ''),
    ),
)

for row in TEST_ROWS:
    result = normalize_payment_row(
        row=row,
        service=ServiceType.RPP,
        spreadsheet_id='spreadsheet-id',
        sheet_name='????1',
        sheet_gid=111,
    )
    event_type = result.event.event_type if result.event else None
    amount = result.event.amount if result.event else None
    assert event_type in (None, PaymentEventType.PAYMENT_CLICK, PaymentEventType.PAYMENT_SUCCESS)
    assert amount is None or isinstance(amount, Decimal)
    print({
        'row_num': result.row_num,
        'status': result.status.value,
        'reason': result.reason,
        'event_type': event_type.value if event_type else None,
        'amount': str(amount) if amount is not None else None,
        'platform_id': result.event.platform_id if result.event else None,
        'event_date': result.event.event_date.isoformat() if result.event and result.event.event_date else None,
    })
