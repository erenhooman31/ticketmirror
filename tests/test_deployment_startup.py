from pathlib import Path


def test_coolify_startup_seeds_catalog_and_repairs_backlog_after_migrate():
    compose = Path("docker-compose.coolify.yml").read_text(encoding="utf-8")

    migrate_index = compose.index("python manage.py migrate --noinput")
    seed_index = compose.index("python manage.py seed_bookeo_products")
    repair_index = compose.index(
        "python manage.py repair_parsed_booking_display_fields"
    )
    collectstatic_index = compose.index("python manage.py collectstatic --noinput")

    assert migrate_index < seed_index < repair_index < collectstatic_index
