import argparse
import asyncio
import logging

from analytics_app.app.payments.sync import run_payments_worker, sync_payments_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Payments sync worker')
    parser.add_argument('--once', action='store_true', help='Run one sync iteration and exit')
    parser.add_argument('--sleep-seconds', type=int, default=5, help='Delay between polling iterations')
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')

    if args.once:
        results = await sync_payments_once()
        for result in results:
            logging.info('Sync result: %s', result)
        return

    await run_payments_worker(sleep_seconds=args.sleep_seconds)


if __name__ == '__main__':
    asyncio.run(_main())
