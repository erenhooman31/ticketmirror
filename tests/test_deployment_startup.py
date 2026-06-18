from pathlib import Path


def test_coolify_web_startup_reaches_gunicorn_before_backlog_repair():
    compose = Path("docker-compose.coolify.yml").read_text(encoding="utf-8")

    migrate_index = compose.index("python manage.py migrate --noinput")
    seed_index = compose.index("python manage.py seed_bookeo_products")
    collectstatic_index = compose.index("python manage.py collectstatic --noinput")
    admin_index = compose.index("python manage.py create_initial_admin")
    gunicorn_index = compose.index("exec gunicorn config.wsgi:application")

    assert (
        migrate_index < seed_index < collectstatic_index < admin_index < gunicorn_index
    )
    web_section = compose.split("  poller:", 1)[0]
    assert "python manage.py replay_raw_emails --apply" not in web_section
    assert "python manage.py repair_parsed_booking_display_fields" not in web_section
    assert "python manage.py reslot_bookings --quiet" not in web_section


def test_coolify_replays_cyrillic_backlog_without_provider_filter():
    compose = Path("docker-compose.coolify.yml").read_text(encoding="utf-8")

    assert "echo '--- replaying Cyrillic raw email backlog ---'" in compose
    assert "--contains-cyrillic" in compose


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


def test_translation_dependencies_are_not_in_base_image_by_default():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    translation_requirements = Path("requirements-translation.txt").read_text(
        encoding="utf-8"
    )
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    coolify_compose = Path("docker-compose.coolify.yml").read_text(encoding="utf-8")

    assert "argostranslate" not in requirements
    assert "argostranslate" in translation_requirements
    assert "torch==2.12.1+cpu" in translation_requirements
    assert "ARG INSTALL_TRANSLATION_MODELS=false" in dockerfile
    assert "INSTALL_TRANSLATION_MODELS: ${INSTALL_TRANSLATION_MODELS:-false}" in (
        coolify_compose
    )
    assert "TRANSLATE_ENABLED: ${TRANSLATE_ENABLED:-false}" in coolify_compose


def test_coolify_poller_repairs_backlog_before_polling():
    compose = Path("docker-compose.coolify.yml").read_text(encoding="utf-8")
    poller_section = compose.split("  poller:", 1)[1].split("  postgres:", 1)[0]

    replay_index = poller_section.index("python manage.py replay_raw_emails --apply")
    cyrillic_replay_index = poller_section.index("--contains-cyrillic")
    repair_index = poller_section.index(
        "python manage.py repair_parsed_booking_display_fields"
    )
    reslot_index = poller_section.index("python manage.py reslot_bookings --quiet")
    stale_review_index = poller_section.index(
        "python manage.py resolve_stale_booking_reviews --quiet"
    )
    poll_index = poller_section.index(
        "exec python manage.py poll_gmail --loop --interval 60"
    )

    assert (
        replay_index
        < cyrillic_replay_index
        < repair_index
        < reslot_index
        < stale_review_index
        < poll_index
    )
