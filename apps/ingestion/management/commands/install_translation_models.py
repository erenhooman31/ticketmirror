from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Install offline Argos Translate language packages."

    def add_arguments(self, parser):
        parser.add_argument("--from-code", default="ru")
        parser.add_argument("--to-code", default="en")

    def handle(self, *args, **options):
        from_code = options["from_code"]
        to_code = options["to_code"]
        try:
            import argostranslate.package
            import argostranslate.translate
        except ImportError as exc:
            raise CommandError("argostranslate is not installed.") from exc

        if _installed(argostranslate.translate, from_code, to_code):
            self.stdout.write(
                self.style.SUCCESS(f"Argos {from_code}->{to_code} already installed.")
            )
            return

        self.stdout.write(f"Downloading Argos {from_code}->{to_code} package index.")
        argostranslate.package.update_package_index()
        packages = argostranslate.package.get_available_packages()
        package = next(
            (
                item
                for item in packages
                if item.from_code == from_code and item.to_code == to_code
            ),
            None,
        )
        if package is None:
            raise CommandError(f"No Argos package found for {from_code}->{to_code}.")

        self.stdout.write(f"Downloading Argos {from_code}->{to_code} package.")
        package_path = package.download()
        argostranslate.package.install_from_path(package_path)
        self.stdout.write(
            self.style.SUCCESS(f"Installed Argos {from_code}->{to_code} package.")
        )


def _installed(translate_module, from_code: str, to_code: str) -> bool:
    from_language = None
    to_language = None
    for language in translate_module.get_installed_languages():
        if language.code == from_code:
            from_language = language
        elif language.code == to_code:
            to_language = language
    return bool(
        from_language and to_language and from_language.get_translation(to_language)
    )
