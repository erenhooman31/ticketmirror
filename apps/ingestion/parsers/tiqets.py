from .base import ProviderEmailParser


class TiqetsParser(ProviderEmailParser):
    provider_code = "tiqets"

    def parse(self, raw_email):
        raise NotImplementedError("Tiqets parser rules have not been configured yet.")
