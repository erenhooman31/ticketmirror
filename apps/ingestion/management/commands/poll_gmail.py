from django.core.management.base import BaseCommand

from apps.ingestion.polling import poll_gmail_loop, poll_gmail_once


class Command(BaseCommand):
    help = "Poll Gmail once or continuously and process newly stored raw emails."

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Run continuously instead of a single polling cycle.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Seconds between polling cycles when --loop is used.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Maximum Gmail messages to fetch during fallback/list cycles.",
        )
        parser.add_argument(
            "--fallback-days",
            type=int,
            default=7,
            help=(
                "Legacy option retained for compatibility. Recent-message fallback "
                "uses GMAIL_SYNC_QUERY."
            ),
        )
        parser.add_argument(
            "--no-process",
            action="store_true",
            help="Store raw emails but leave parsing for process_pending_emails.",
        )

    def handle(self, *args, **options):
        kwargs = {
            "limit": max(options["limit"], 0),
            "fallback_days": max(options["fallback_days"], 1),
            "process": not options["no_process"],
        }
        if options["loop"]:
            for result in poll_gmail_loop(
                interval=max(options["interval"], 1),
                **kwargs,
            ):
                self.stdout.write(str(result.as_dict()))
            return

        result = poll_gmail_once(**kwargs)
        self.stdout.write(str(result.as_dict()))
