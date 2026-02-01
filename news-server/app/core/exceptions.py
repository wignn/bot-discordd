from typing import Any


class NewsAPIException(Exception):

    def __init__(self, message: str, details: Any = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class DatabaseException(NewsAPIException):
    pass


class ScraperException(NewsAPIException):
    pass


class AIProviderException(NewsAPIException):
    pass


class RateLimitException(NewsAPIException):
    pass


class ValidationException(NewsAPIException):
    pass


class NotFoundException(NewsAPIException):
    pass


class DuplicateException(NewsAPIException):
    pass


class ConfigurationException(NewsAPIException):
    pass
