import argparse
import asyncio

from analytics_app.app.integrations.google_sheets import get_google_sheets_client


async def _main() -> None:
    parser = argparse.ArgumentParser(description='Smoke test for Google Sheets reader')
    parser.add_argument('spreadsheet_id')
    parser.add_argument('sheet_name')
    parser.add_argument('--start-row', type=int, default=2)
    args = parser.parse_args()

    client = get_google_sheets_client()
    rows = await client.fetch_rows(
        spreadsheet_id=args.spreadsheet_id,
        sheet_name=args.sheet_name,
        start_row=args.start_row,
    )

    for row in rows:
        print(
            f'row={row.source_row_num} '
            f'empty={row.is_empty} '
            f'full_name={row.full_name!r} '
            f'email={row.email!r} '
            f'raw_payment_value={row.raw_payment_value!r} '
            f'nickname={row.nickname!r} '
            f'event_date_raw={row.event_date_raw!r} '
            f'platform_id_raw={row.platform_id_raw!r}'
        )


if __name__ == '__main__':
    asyncio.run(_main())
