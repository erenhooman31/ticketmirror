from .base import ProviderEmailParser


class Sputnik8Parser(ProviderEmailParser):
    provider_code = "sputnik8"

    def parse(self, raw_email):
        raise NotImplementedError("Sputnik8 parser rules have not been configured yet.")
