from .base import ProviderEmailParser


class GetYourGuideParser(ProviderEmailParser):
    provider_code = "getyourguide"

    def parse(self, raw_email):
        raise NotImplementedError(
            "GetYourGuide parser rules have not been configured yet."
        )
