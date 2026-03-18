"""i18n / Multi-language support package."""

from mcp_sdk.plugins.i18n.manager import (
    BUILT_IN_LOCALES,
    I18nManager,
    LanguageDetector,
    Locale,
    LocaleFormatter,
    TranslationCatalog,
)

__all__ = [
    "I18nManager",
    "TranslationCatalog",
    "LanguageDetector",
    "LocaleFormatter",
    "Locale",
    "BUILT_IN_LOCALES",
]
