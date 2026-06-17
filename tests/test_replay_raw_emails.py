from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.bookings.models import Provider
from apps.ingestion.models import RawEmail


def make_raw_email(*, status, message_id, provider=None, subject="Provider booking"):
    return RawEmail.objects.create(
        gmail_message_id=message_id,
        gmail_outer_sender="owner@gmail.com",
        original_forwarded_sender="operator@klook.com",
        subject=subject,
        received_at=timezone.now(),
        body_text="Synthetic body",
        parse_status=status,
        provider_detected=provider,
    )


@pytest.mark.django_db
def test_replay_raw_emails_dry_run_does_not_process(monkeypatch):
    make_raw_email(
        status=RawEmail.ParseStatus.NEEDS_REVIEW,
        message_id="dry-run-1",
    )

    def fail(_raw_email_id):
        raise AssertionError("dry run should not process")

    monkeypatch.setattr(
        "apps.ingestion.management.commands.replay_raw_emails.process_raw_email",
        fail,
    )
    output = StringIO()

    call_command("replay_raw_emails", stdout=output)

    assert "Dry run: 1 of 1 matching raw emails would be replayed" in output.getvalue()
    assert RawEmail.objects.get(gmail_message_id="dry-run-1").parse_status == (
        RawEmail.ParseStatus.NEEDS_REVIEW
    )


@pytest.mark.django_db
def test_replay_raw_emails_apply_replays_default_repair_statuses(monkeypatch):
    provider = Provider.objects.create(name="Klook", code="klook", parser_key="klook")
    needs_review = make_raw_email(
        status=RawEmail.ParseStatus.NEEDS_REVIEW,
        message_id="needs-review-1",
        provider=provider,
    )
    parsed = make_raw_email(
        status=RawEmail.ParseStatus.PARSED,
        message_id="parsed-1",
        provider=provider,
    )
    processed_ids = []

    def mark_parsed(raw_email_id):
        processed_ids.append(raw_email_id)
        RawEmail.objects.filter(id=raw_email_id).update(
            parse_status=RawEmail.ParseStatus.PARSED,
        )

    monkeypatch.setattr(
        "apps.ingestion.management.commands.replay_raw_emails.process_raw_email",
        mark_parsed,
    )
    output = StringIO()

    call_command("replay_raw_emails", "--apply", "--provider", "klook", stdout=output)

    assert processed_ids == [needs_review.id]
    assert RawEmail.objects.get(id=needs_review.id).parse_status == (
        RawEmail.ParseStatus.PARSED
    )
    assert (
        RawEmail.objects.get(id=parsed.id).parse_status == RawEmail.ParseStatus.PARSED
    )
    assert "Replayed 1 raw emails" in output.getvalue()


@pytest.mark.django_db
def test_replay_raw_emails_include_parsed_is_explicit(monkeypatch):
    raw_email = make_raw_email(
        status=RawEmail.ParseStatus.PARSED,
        message_id="parsed-explicit-1",
    )
    processed_ids = []

    monkeypatch.setattr(
        "apps.ingestion.management.commands.replay_raw_emails.process_raw_email",
        lambda raw_email_id: processed_ids.append(raw_email_id),
    )

    call_command("replay_raw_emails", "--apply")
    assert processed_ids == []

    call_command("replay_raw_emails", "--apply", "--include-parsed")
    assert processed_ids == [raw_email.id]
