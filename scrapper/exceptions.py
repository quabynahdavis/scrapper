"""
Custom exceptions for the scraper module.
"""


class ScraperException(Exception):
    """Base exception for all scraper errors."""


class SourceError(ScraperException):
    """Raised when a specific source adapter fails."""


class DownloadError(ScraperException):
    """Raised when all download attempts for a result fail."""


class ConfigurationError(ScraperException):
    """Raised when the configuration is invalid or missing."""
