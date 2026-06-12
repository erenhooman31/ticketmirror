from .base import ProviderEmailParser


class KlookParser(ProviderEmailParser):
    provider_code = "klook"

    def parse(self, raw_email):
        raise NotImplementedError("Klook parser rules have not been configured yet.")
