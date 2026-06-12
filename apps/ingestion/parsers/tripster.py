from .base import ProviderEmailParser


class TripsterParser(ProviderEmailParser):
    provider_code = "tripster"

    def parse(self, raw_email):
        raise NotImplementedError("Tripster parser rules have not been configured yet.")
