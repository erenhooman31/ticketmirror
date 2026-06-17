from pathlib import Path


def test_coolify_startup_seeds_catalog_and_repairs_backlog_after_migrate():
    compose = Path("docker-compose.coolify.yml").read_text(encoding="utf-8")

    migrate_index = compose.index("python manage.py migrate --noinput")
    seed_index = compose.index("python manage.py seed_bookeo_products")
    repair_index = compose.index(
        "python manage.py repair_parsed_booking_display_fields"
    )
    reslot_index = compose.index("python manage.py reslot_bookings --quiet")
    stale_review_index = compose.index(
        "python manage.py resolve_stale_booking_reviews --quiet --limit 500"
    )
    collectstatic_index = compose.index("python manage.py collectstatic --noinput")

    assert (
        migrate_index
        < seed_index
        < repair_index
        < reslot_index
        < stale_review_index
        < collectstatic_index
    )


def test_removed_infra_references_do_not_return():
    haystack = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            Path("requirements.txt"),
            Path("config/settings.py"),
            Path("docker-compose.coolify.yml"),
            Path("docker-compose.prod.yml"),
            Path("docker-compose.yml"),
        ]
    ).lower()

    forbidden_tokens = [
        "cel" + "ery",
        "red" + "is",
        "gmail_" + "pub" + "sub",
        "gmail_" + "webhook",
        "setup_gmail_" + "watch",
        "renew_gmail_" + "watch",
    ]
    for token in forbidden_tokens:
        assert token not in haystack


def test_coolify_runs_dedicated_gmail_poller():
    compose = Path("docker-compose.coolify.yml").read_text(encoding="utf-8")

    assert "poller:" in compose
    assert "python manage.py poll_gmail --loop --interval 60" in compose
