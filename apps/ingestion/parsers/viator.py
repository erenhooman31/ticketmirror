from .base import ProviderEmailParser


class ViatorParser(ProviderEmailParser):
    provider_code = "viator"

    def parse(self, raw_email):
        raise NotImplementedError("Viator parser rules have not been configured yet.")
