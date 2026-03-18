"""
Multi-Language Support (i18n)
==============================
Internationalization framework for MCP agents:

- Message translation with locale resolution
- RTL/LTR direction detection
- Number, date, and currency formatting
- Locale-aware agent persona adaptation
- Translation catalog with YAML/JSON loading
- Fallback chain (specific → language → default)
- Language detection heuristics
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Locale model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Locale:
    """Represents a locale with language, region, and formatting rules."""

    code: str  # e.g. "en-US", "ar-SA", "zh-Hans"
    language: str = ""  # ISO 639-1: "en", "ar", "zh"
    region: str = ""  # ISO 3166-1: "US", "SA", "CN"
    rtl: bool = False
    decimal_separator: str = "."
    thousands_separator: str = ","
    currency_symbol: str = "$"
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H:%M"

    def __post_init__(self) -> None:
        if not self.language:
            parts = self.code.split("-")
            self.language = parts[0].lower()
            self.region = parts[1].upper() if len(parts) > 1 else ""

    @property
    def fallback_chain(self) -> list[str]:
        """Resolution order: specific → language → default."""
        chain = [self.code]
        if self.region:
            chain.append(self.language)
        chain.append("en")
        return chain


# Built-in locale definitions
BUILT_IN_LOCALES: dict[str, Locale] = {
    "en": Locale(
        "en", language="en", decimal_separator=".", thousands_separator=",", date_format="%m/%d/%Y"
    ),
    "en-US": Locale(
        "en-US", language="en", region="US", decimal_separator=".", thousands_separator=","
    ),
    "en-GB": Locale(
        "en-GB",
        language="en",
        region="GB",
        decimal_separator=".",
        thousands_separator=",",
        date_format="%d/%m/%Y",
    ),
    "fr": Locale(
        "fr",
        language="fr",
        decimal_separator=",",
        thousands_separator=" ",
        currency_symbol="€",
        date_format="%d/%m/%Y",
    ),
    "de": Locale(
        "de",
        language="de",
        decimal_separator=",",
        thousands_separator=".",
        currency_symbol="€",
        date_format="%d.%m.%Y",
    ),
    "es": Locale(
        "es", language="es", decimal_separator=",", thousands_separator=".", currency_symbol="€"
    ),
    "pt": Locale(
        "pt", language="pt", decimal_separator=",", thousands_separator=".", currency_symbol="R$"
    ),
    "pt-BR": Locale(
        "pt-BR",
        language="pt",
        region="BR",
        decimal_separator=",",
        thousands_separator=".",
        currency_symbol="R$",
    ),
    "zh": Locale(
        "zh", language="zh", decimal_separator=".", thousands_separator=",", currency_symbol="¥"
    ),
    "zh-Hans": Locale("zh-Hans", language="zh", decimal_separator=".", currency_symbol="¥"),
    "ja": Locale(
        "ja", language="ja", decimal_separator=".", thousands_separator=",", currency_symbol="¥"
    ),
    "ko": Locale(
        "ko", language="ko", decimal_separator=".", thousands_separator=",", currency_symbol="₩"
    ),
    "ar": Locale("ar", language="ar", rtl=True, decimal_separator=".", currency_symbol="﷼"),
    "ar-SA": Locale("ar-SA", language="ar", region="SA", rtl=True, currency_symbol="﷼"),
    "he": Locale("he", language="he", rtl=True, currency_symbol="₪"),
    "fa": Locale("fa", language="fa", rtl=True, currency_symbol="﷼"),
    "ru": Locale(
        "ru", language="ru", decimal_separator=",", thousands_separator=" ", currency_symbol="₽"
    ),
    "hi": Locale(
        "hi", language="hi", decimal_separator=".", thousands_separator=",", currency_symbol="₹"
    ),
    "tr": Locale(
        "tr", language="tr", decimal_separator=",", thousands_separator=".", currency_symbol="₺"
    ),
    "nl": Locale(
        "nl", language="nl", decimal_separator=",", thousands_separator=".", currency_symbol="€"
    ),
    "pl": Locale(
        "pl", language="pl", decimal_separator=",", thousands_separator=" ", currency_symbol="zł"
    ),
    "it": Locale(
        "it", language="it", decimal_separator=",", thousands_separator=".", currency_symbol="€"
    ),
    "sv": Locale(
        "sv", language="sv", decimal_separator=",", thousands_separator=" ", currency_symbol="kr"
    ),
}

# Language detection word sets (sample)
LANGUAGE_WORD_HINTS: dict[str, list[str]] = {
    "fr": ["le", "la", "les", "un", "une", "des", "et", "vous", "nous", "est", "bonjour", "merci"],
    "de": [
        "der",
        "die",
        "das",
        "ein",
        "eine",
        "ist",
        "und",
        "hallo",
        "danke",
        "bitte",
        "ich",
        "sie",
    ],
    "es": ["el", "la", "los", "un", "una", "y", "es", "hola", "gracias", "por", "que", "como"],
    "pt": ["o", "a", "os", "as", "um", "uma", "e", "olá", "obrigado", "por", "que"],
    "ar": ["في", "من", "على", "هو", "هي", "مرحبا", "شكرا", "ما", "هذا"],
    "zh": ["是", "的", "我", "你", "他", "她", "们", "了", "在", "不"],
    "ja": ["は", "が", "を", "に", "で", "と", "の", "です", "ます", "ありがとう"],
    "ko": ["이", "가", "을", "을", "의", "은", "는", "합니다", "감사합니다"],
    "ru": ["и", "в", "не", "на", "я", "он", "с", "привет", "спасибо", "что"],
    "hi": ["है", "का", "के", "की", "और", "में", "नमस्ते", "धन्यवाद"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Translation Catalog
# ─────────────────────────────────────────────────────────────────────────────


class TranslationCatalog:
    """
    Holds translated strings organized as namespace → locale → key → value.

    Supports ICU-style variable interpolation: "Hello, {name}!"
    """

    def __init__(self) -> None:
        # namespace -> locale_code -> {key: value}
        self._data: dict[str, dict[str, dict[str, str]]] = {}

    def load_yaml(self, content: str, namespace: str = "default") -> int:
        """Load YAML translations. Returns number of strings loaded."""
        data = yaml.safe_load(content)
        count = 0
        for locale_code, strings in data.items():
            if isinstance(strings, dict):
                ns_data = self._data.setdefault(namespace, {}).setdefault(locale_code, {})
                ns_data.update(strings)
                count += len(strings)
        logger.debug("Translations loaded", namespace=namespace, count=count)
        return count

    def load_json(self, content: str, locale_code: str, namespace: str = "default") -> int:
        data = json.loads(content)
        ns_data = self._data.setdefault(namespace, {}).setdefault(locale_code, {})
        ns_data.update(data)
        return len(data)

    def add(self, locale_code: str, key: str, value: str, namespace: str = "default") -> None:
        self._data.setdefault(namespace, {}).setdefault(locale_code, {})[key] = value

    def get(
        self,
        key: str,
        locale: Locale,
        namespace: str = "default",
        variables: dict[str, Any] | None = None,
    ) -> str | None:
        """Resolve a translation key with locale fallback chain."""
        ns_data = self._data.get(namespace, {})
        for locale_code in locale.fallback_chain:
            locale_strings = ns_data.get(locale_code, {})
            if key in locale_strings:
                value = locale_strings[key]
                if variables:
                    with contextlib.suppress(KeyError):
                        value = value.format(**variables)
                return value
        return None

    def available_locales(self, namespace: str = "default") -> list[str]:
        return list(self._data.get(namespace, {}).keys())


# ─────────────────────────────────────────────────────────────────────────────
# Locale-aware formatter
# ─────────────────────────────────────────────────────────────────────────────


class LocaleFormatter:
    """Format numbers, dates, and currencies according to locale rules."""

    def __init__(self, locale: Locale) -> None:
        self.locale = locale

    def format_number(self, value: float, decimals: int = 2) -> str:
        formatted = f"{value:,.{decimals}f}"
        # Apply locale separators
        formatted = formatted.replace(",", "THOU").replace(".", "DEC")
        formatted = formatted.replace("THOU", self.locale.thousands_separator)
        formatted = formatted.replace("DEC", self.locale.decimal_separator)
        return formatted

    def format_currency(self, amount: float, decimals: int = 2) -> str:
        number = self.format_number(amount, decimals)
        return f"{self.locale.currency_symbol}{number}"

    def format_date(self, dt: Any) -> str:
        from datetime import datetime

        if isinstance(dt, datetime):
            return dt.strftime(self.locale.date_format)
        return str(dt)

    def format_time(self, dt: Any) -> str:
        from datetime import datetime

        if isinstance(dt, datetime):
            return dt.strftime(self.locale.time_format)
        return str(dt)

    def wrap_rtl(self, text: str) -> str:
        if self.locale.rtl:
            return f"\u200f{text}\u200f"  # Right-to-left marks
        return text


# ─────────────────────────────────────────────────────────────────────────────
# Language Detector
# ─────────────────────────────────────────────────────────────────────────────


class LanguageDetector:
    """Heuristic language detection based on script and word frequency."""

    # Unicode script ranges
    ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")
    CJK_RE = re.compile(r"[\u4E00-\u9FFF\u3000-\u303F]")
    HIRAGANA_RE = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")
    HANGUL_RE = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF]")
    CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
    DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
    HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
    LATIN_RE = re.compile(r"[a-zA-Z]")

    def detect(self, text: str) -> str:
        """Return detected ISO 639-1 language code. Returns 'en' as default."""
        if not text or len(text) < 3:
            return "en"

        # Script-based detection (most reliable)
        if self.ARABIC_RE.search(text):
            return "ar"
        if self.HIRAGANA_RE.search(text):
            return "ja"
        if self.HANGUL_RE.search(text):
            return "ko"
        if self.CJK_RE.search(text) and not self.HIRAGANA_RE.search(text):
            return "zh"
        if self.CYRILLIC_RE.search(text):
            return "ru"
        if self.DEVANAGARI_RE.search(text):
            return "hi"
        if self.HEBREW_RE.search(text):
            return "he"

        # Word-frequency based for Latin-script languages
        if self.LATIN_RE.search(text):
            words = set(text.lower().split())
            scores: dict[str, int] = {}
            for lang, hints in LANGUAGE_WORD_HINTS.items():
                scores[lang] = sum(1 for w in hints if w in words)
            if scores:
                best = max(scores, key=lambda k: scores[k])
                if scores[best] >= 2:
                    return best

        return "en"

    def detect_locale(self, text: str) -> Locale:
        lang = self.detect(text)
        return BUILT_IN_LOCALES.get(lang, BUILT_IN_LOCALES["en"])


# ─────────────────────────────────────────────────────────────────────────────
# Main i18n Manager
# ─────────────────────────────────────────────────────────────────────────────


class I18nManager:
    """
    Central internationalization manager for MCP agents.

    Example::

        i18n = I18nManager.with_defaults()
        i18n.catalog.add("fr", "greeting", "Bonjour, {name}!")
        i18n.catalog.add("es", "greeting", "¡Hola, {name}!")

        locale = i18n.get_locale("fr-FR")
        msg = i18n.translate("greeting", locale, variables={"name": "Alice"})
        # → "Bonjour, Alice!"

        detected = i18n.detect_and_translate("Bonjour!", "greeting")
        # Detects French → "Bonjour!"
    """

    def __init__(
        self,
        default_locale_code: str = "en",
        catalog: TranslationCatalog | None = None,
        detector: LanguageDetector | None = None,
    ) -> None:
        self.default_locale_code = default_locale_code
        self.catalog = catalog or TranslationCatalog()
        self.detector = detector or LanguageDetector()
        self._locale_cache: dict[str, Locale] = dict(BUILT_IN_LOCALES)

    def get_locale(self, code: str) -> Locale:
        if code in self._locale_cache:
            return self._locale_cache[code]
        locale = Locale(code)
        self._locale_cache[code] = locale
        return locale

    def detect_locale(self, text: str) -> Locale:
        return self.detector.detect_locale(text)

    def translate(
        self,
        key: str,
        locale: Locale | str,
        namespace: str = "default",
        variables: dict[str, Any] | None = None,
        fallback: str | None = None,
    ) -> str:
        if isinstance(locale, str):
            locale = self.get_locale(locale)
        result = self.catalog.get(key, locale, namespace=namespace, variables=variables)
        if result is not None:
            return result
        return fallback or key

    def detect_and_translate(
        self,
        text: str,
        key: str,
        namespace: str = "default",
        variables: dict[str, Any] | None = None,
    ) -> str:
        locale = self.detect_locale(text)
        return self.translate(key, locale, namespace=namespace, variables=variables, fallback=text)

    def get_formatter(self, locale: Locale | str) -> LocaleFormatter:
        if isinstance(locale, str):
            locale = self.get_locale(locale)
        return LocaleFormatter(locale)

    def is_rtl(self, locale_code: str) -> bool:
        locale = self.get_locale(locale_code)
        return locale.rtl

    @classmethod
    def with_defaults(cls) -> I18nManager:
        mgr = cls()
        # Load built-in translations
        builtin_yaml = """
en:
  greeting: "Hello, {name}!"
  farewell: "Goodbye, {name}!"
  error: "An error occurred: {message}"
  welcome: "Welcome to the MCP Agent Platform!"
  unknown_command: "I'm sorry, I didn't understand that. Could you rephrase?"

fr:
  greeting: "Bonjour, {name}!"
  farewell: "Au revoir, {name}!"
  error: "Une erreur s'est produite: {message}"
  welcome: "Bienvenue sur la plateforme d'agents MCP!"
  unknown_command: "Je suis désolé, je n'ai pas compris. Pouvez-vous reformuler?"

de:
  greeting: "Hallo, {name}!"
  farewell: "Auf Wiedersehen, {name}!"
  error: "Ein Fehler ist aufgetreten: {message}"
  welcome: "Willkommen auf der MCP-Agentenplattform!"
  unknown_command: "Entschuldigung, ich habe das nicht verstanden. Können Sie es wiederholen?"

es:
  greeting: "¡Hola, {name}!"
  farewell: "¡Adiós, {name}!"
  error: "Ocurrió un error: {message}"
  welcome: "¡Bienvenido a la plataforma de agentes MCP!"
  unknown_command: "Lo siento, no entendí eso. ¿Podría reformularlo?"

pt:
  greeting: "Olá, {name}!"
  farewell: "Adeus, {name}!"
  error: "Ocorreu um erro: {message}"
  welcome: "Bem-vindo à plataforma de agentes MCP!"
  unknown_command: "Desculpe, não entendi. Poderia reformular?"

zh:
  greeting: "你好, {name}!"
  farewell: "再见, {name}!"
  error: "发生了错误: {message}"
  welcome: "欢迎使用MCP智能体平台！"
  unknown_command: "对不起，我没有理解。请重新表达？"

ar:
  greeting: "مرحباً، {name}!"
  farewell: "وداعاً، {name}!"
  error: "حدث خطأ: {message}"
  welcome: "مرحباً بك في منصة وكلاء MCP!"
  unknown_command: "آسف، لم أفهم ذلك. هل يمكنك إعادة الصياغة؟"

ja:
  greeting: "こんにちは、{name}さん！"
  farewell: "さようなら、{name}さん！"
  error: "エラーが発生しました: {message}"
  welcome: "MCPエージェントプラットフォームへようこそ！"
  unknown_command: "申し訳ありませんが、理解できませんでした。言い換えていただけますか？"

ru:
  greeting: "Привет, {name}!"
  farewell: "До свидания, {name}!"
  error: "Произошла ошибка: {message}"
  welcome: "Добро пожаловать на платформу агентов MCP!"
  unknown_command: "Извините, я не понял. Не могли бы вы перефразировать?"

hi:
  greeting: "नमस्ते, {name}!"
  farewell: "अलविदा, {name}!"
  error: "एक त्रुटि हुई: {message}"
  welcome: "MCP एजेंट प्लेटफ़ॉर्म में आपका स्वागत है!"
  unknown_command: "माफ़ करें, मैं समझ नहीं पाया। क्या आप दोबारा कह सकते हैं?"

ko:
  greeting: "안녕하세요, {name}님!"
  farewell: "안녕히 계세요, {name}님!"
  error: "오류가 발생했습니다: {message}"
  welcome: "MCP 에이전트 플랫폼에 오신 것을 환영합니다!"
  unknown_command: "죄송합니다, 이해하지 못했습니다. 다시 말씀해 주시겠어요?"

tr:
  greeting: "Merhaba, {name}!"
  farewell: "Hoşça kalın, {name}!"
  error: "Bir hata oluştu: {message}"
  welcome: "MCP Ajan Platformuna hoş geldiniz!"
  unknown_command: "Üzgünüm, anlamadım. Tekrar ifade edebilir misiniz?"
"""
        mgr.catalog.load_yaml(builtin_yaml, namespace="default")
        return mgr

    _global: I18nManager | None = None

    @classmethod
    def global_manager(cls) -> I18nManager:
        if cls._global is None:
            cls._global = cls.with_defaults()
        return cls._global
