"""Tests for i18n / Multi-Language Manager."""

import pytest

from mcp_sdk.plugins.i18n.manager import (
    BUILT_IN_LOCALES,
    I18nManager,
    LanguageDetector,
    Locale,
    LocaleFormatter,
    TranslationCatalog,
)


class TestLocale:
    def test_fallback_chain_with_region(self) -> None:
        locale = Locale("fr-CA")
        chain = locale.fallback_chain
        assert "fr-CA" in chain
        assert "fr" in chain
        assert "en" in chain

    def test_fallback_chain_without_region(self) -> None:
        locale = Locale("fr")
        chain = locale.fallback_chain
        assert "fr" in chain
        assert "en" in chain

    def test_rtl_arabic(self) -> None:
        locale = BUILT_IN_LOCALES["ar"]
        assert locale.rtl is True

    def test_rtl_english_is_false(self) -> None:
        locale = BUILT_IN_LOCALES["en"]
        assert locale.rtl is False


class TestTranslationCatalog:
    @pytest.fixture
    def catalog(self):
        c = TranslationCatalog()
        c.add("en", "greeting", "Hello, {name}!")
        c.add("fr", "greeting", "Bonjour, {name}!")
        c.add("de", "greeting", "Hallo, {name}!")
        c.add("en", "farewell", "Goodbye!")
        return c

    def test_get_exact_locale(self, catalog) -> None:
        locale = Locale("fr")
        result = catalog.get("greeting", locale, variables={"name": "Alice"})
        assert result == "Bonjour, Alice!"

    def test_get_fallback_to_language(self, catalog) -> None:
        locale = Locale("fr-CA")
        result = catalog.get("greeting", locale, variables={"name": "Bob"})
        assert result == "Bonjour, Bob!"

    def test_get_fallback_to_english(self, catalog) -> None:
        locale = Locale("es")  # Spanish not in catalog
        result = catalog.get("greeting", locale, variables={"name": "Carlos"})
        assert result == "Hello, Carlos!"

    def test_missing_key_returns_none(self, catalog) -> None:
        locale = Locale("en")
        result = catalog.get("nonexistent_key", locale)
        assert result is None

    def test_load_yaml(self, catalog) -> None:
        yaml_content = """
test_locale:
  hello: "Test Hello!"
  bye: "Test Bye!"
"""
        count = catalog.load_yaml(yaml_content, namespace="test")
        assert count == 2
        locale = Locale("test_locale")
        result = catalog.get("hello", locale, namespace="test")
        assert result == "Test Hello!"

    def test_variable_interpolation(self, catalog) -> None:
        locale = Locale("en")
        result = catalog.get("greeting", locale, variables={"name": "World"})
        assert result == "Hello, World!"


class TestLanguageDetector:
    @pytest.fixture
    def detector(self):
        return LanguageDetector()

    def test_detect_english(self, detector) -> None:
        lang = detector.detect("Hello, how are you doing today?")
        assert lang == "en"

    def test_detect_french(self, detector) -> None:
        lang = detector.detect("Bonjour, comment vous allez vous?")
        assert lang == "fr"

    def test_detect_arabic_script(self, detector) -> None:
        lang = detector.detect("مرحبا، كيف حالك؟")
        assert lang == "ar"

    def test_detect_chinese_script(self, detector) -> None:
        lang = detector.detect("你好，今天怎么样？")
        assert lang == "zh"

    def test_detect_japanese_script(self, detector) -> None:
        lang = detector.detect("こんにちは、お元気ですか？")
        assert lang == "ja"

    def test_detect_korean_script(self, detector) -> None:
        lang = detector.detect("안녕하세요, 잘 지내세요?")
        assert lang == "ko"

    def test_detect_cyrillic_russian(self, detector) -> None:
        lang = detector.detect("Привет, как ты?")
        assert lang == "ru"

    def test_detect_german(self, detector) -> None:
        lang = detector.detect("Hallo, wie geht es Ihnen?")
        assert lang == "de"

    def test_detect_empty_defaults_english(self, detector) -> None:
        lang = detector.detect("")
        assert lang == "en"

    def test_detect_locale_returns_locale_object(self, detector) -> None:
        locale = detector.detect_locale("Bonjour!")
        assert locale.language == "fr"
        assert locale.rtl is False


class TestLocaleFormatter:
    def test_format_number_en(self) -> None:
        formatter = LocaleFormatter(BUILT_IN_LOCALES["en"])
        assert formatter.format_number(1234567.89) == "1,234,567.89"

    def test_format_number_de(self) -> None:
        formatter = LocaleFormatter(BUILT_IN_LOCALES["de"])
        result = formatter.format_number(1234567.89)
        assert "." in result  # thousands separator
        assert "," in result  # decimal separator

    def test_format_currency(self) -> None:
        formatter = LocaleFormatter(BUILT_IN_LOCALES["en-US"])
        result = formatter.format_currency(99.99)
        assert "$" in result
        assert "99.99" in result

    def test_wrap_rtl(self) -> None:
        formatter = LocaleFormatter(BUILT_IN_LOCALES["ar"])
        wrapped = formatter.wrap_rtl("مرحبا")
        assert "\u200f" in wrapped

    def test_no_rtl_wrap_for_ltr(self) -> None:
        formatter = LocaleFormatter(BUILT_IN_LOCALES["en"])
        wrapped = formatter.wrap_rtl("Hello")
        assert "\u200f" not in wrapped


class TestI18nManager:
    @pytest.fixture
    def i18n(self):
        return I18nManager.with_defaults()

    def test_translate_english(self, i18n) -> None:
        locale = i18n.get_locale("en")
        msg = i18n.translate("greeting", locale, variables={"name": "Alice"})
        assert "Alice" in msg
        assert "Hello" in msg

    def test_translate_french(self, i18n) -> None:
        locale = i18n.get_locale("fr")
        msg = i18n.translate("greeting", locale, variables={"name": "Alice"})
        assert "Bonjour" in msg

    def test_translate_arabic(self, i18n) -> None:
        locale = i18n.get_locale("ar")
        msg = i18n.translate("greeting", locale, variables={"name": "Ahmed"})
        assert "Ahmed" in msg

    def test_translate_japanese(self, i18n) -> None:
        locale = i18n.get_locale("ja")
        msg = i18n.translate("greeting", locale, variables={"name": "Tanaka"})
        assert "Tanaka" in msg

    def test_translate_missing_key_returns_key(self, i18n) -> None:
        locale = i18n.get_locale("en")
        msg = i18n.translate("completely_missing_key", locale)
        assert msg == "completely_missing_key"

    def test_translate_with_fallback(self, i18n) -> None:
        locale = i18n.get_locale("en")
        msg = i18n.translate("missing", locale, fallback="Default message")
        assert msg == "Default message"

    def test_detect_and_translate(self, i18n) -> None:
        msg = i18n.detect_and_translate(
            "Bonjour tout le monde", "greeting", variables={"name": "Alice"}
        )
        assert "Bonjour" in msg

    def test_is_rtl_arabic(self, i18n) -> None:
        assert i18n.is_rtl("ar") is True

    def test_is_rtl_english(self, i18n) -> None:
        assert i18n.is_rtl("en") is False

    def test_get_formatter(self, i18n) -> None:
        formatter = i18n.get_formatter("en-US")
        assert isinstance(formatter, LocaleFormatter)

    def test_all_builtin_locales_loaded(self) -> None:
        assert "en" in BUILT_IN_LOCALES
        assert "ar" in BUILT_IN_LOCALES
        assert "zh" in BUILT_IN_LOCALES
        assert "ja" in BUILT_IN_LOCALES
        assert "ko" in BUILT_IN_LOCALES
        assert "ru" in BUILT_IN_LOCALES
        assert "hi" in BUILT_IN_LOCALES
