"""Тексти магазину /luts. EN — основа; інші мови додаються в TEXT[lang], відсутні ключі беруться з EN.

Правило: тут немає цін у $ (поки немає оплати карткою — див. luts.CARD_ENABLED) і жодних обіцянок, яких не має каталог.
"""
import json
import os

LUT_LANGS = ("en", "uk", "ru", "ar", "fa", "es", "fr", "id")
RTL = {"ar", "fa"}
NAMES = {"en": "English", "uk": "Українська", "ru": "Русский", "ar": "العربية", "fa": "فارسی", "es": "Español",
         "fr": "Français", "id": "Bahasa Indonesia"}
I18N_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "luts_i18n")

EN = {
    "brand": "@blackmagicamera LUTs",
    "nav_free": "Free Starter",
    "nav_guides": "Guides",
    "prod_title": "{title} LUT for Blackmagic Camera ({versions})",
    "free_page_title": "Free Starter pack: free LUTs for iPhone and Blackmagic Camera",
    "lang_label": "Language",
    "title_home": "LUTs for iPhone and Blackmagic Camera: Rec.709 and Apple Log",
    "desc_home": "Cinematic LUTs I grade with every day. Made for Blackmagic Camera on iPhone, in Rec.709 and Apple Log. Free Starter pack included.",
    "h1": "Cinematic color for iPhone. One tap in Blackmagic Camera.",
    "sub": "LUTs I grade with every day. Rec.709 and Apple Log, built for Blackmagic Camera.",
    "cta_all": "See all looks",
    "cta_free": "Get free Starter",
    "drag": "Drag",
    "before": "LUT OFF",
    "after": "LUT ON",
    "kicker": "iPhone · Blackmagic Camera",
    "work_title": "Shot on iPhone",
    "work_sub": "Real clips from my own shoots, graded with these LUTs. No stock footage.",
    "work_tag": "Shot on iPhone",
    "work_alt": "Sample clip shot on iPhone and graded with LUTs",
    "slider_label": "Compare before and after",
    "strip_1": "Apple Log · Rec.709",
    "strip_2": "For the Blackmagic Camera app",
    "strip_3": ".cube files open on iPhone",
    "strip_4": "Free updates for packs",
    "packs": "Packs",
    "packs_sub": "The more you take, the less each look costs.",
    "singles": "Single looks",
    "singles_sub": "One look, one .cube file.",
    "looks_n": "{n} looks",
    "look_1": "1 look",
    "best_value": "Best value",
    "only_in_pack": "Only in this pack",
    "buy_tg": "Buy in Telegram",
    "buy_tg_stars": "Buy in Telegram · {stars} ⭐",
    "buy_short": "Buy · {stars} ⭐",
    "view": "View",
    "versions": "Versions",
    "what_inside": "What's inside",
    "sold_alone": "Also sold on its own",
    "pack_only": "These looks are not sold separately.",
    "how_title": "Install in 30 seconds",
    "how_steps": [
        "Save the zip to Files.",
        "Blackmagic Camera → LUTs Manager → Import LUT.",
        "Open the LUTs folder, Select All, tap Open.",
        "Tap the LUT button and pick your look.",
    ],
    "how_more": "Full guide with screenshots",
    "who_title": "Who makes these",
    "who_text": "I run @blackmagicamera. I shoot on iPhone in Blackmagic Camera, and these are the LUTs I use on my own footage. I grade by eye on the phone screen, so what you see while filming is what you keep.",
    "who_link": "Follow the channel",
    "cmp_title": "Rec.709 or Apple Log?",
    "cmp_709_h": "Rec.709",
    "cmp_709_p": "Normal iPhone video. Pick this if you film in the default mode. The look is ready the moment you apply it.",
    "cmp_log_h": "Apple Log",
    "cmp_log_p": "Flat footage with more room to grade. Pick this on iPhone 15 Pro and newer when you record in Apple Log.",
    "cmp_more": "Which one should I use?",
    "free_title": "Free Starter pack",
    "free_text": "{n} free LUTs to try the workflow. Get them in the Telegram bot, no payment.",
    "free_cta": "Get free Starter",
    "free_credit": "Starter looks are CC0 works of their authors and are credited in the pack.",
    "faq_title": "Questions",
    "faq": [
        ("Which apps does it work in?", "The .cube files are made for Blackmagic Camera on iPhone and Android. They also load in CapCut, VN, LumaFusion and DaVinci Resolve."),
        ("How do I get the files after buying?", "Tap Buy in Telegram, pay with Stars in the bot, and the .cube files arrive in the chat right away. You can send them again any time from /my."),
        ("Does it work on Android?", "Yes. Blackmagic Camera has an Android version and reads the same .cube files."),
        ("Can I use the LUTs in commercial work?", "Yes, in your own photos and videos, including paid client work. You can't share or resell the files."),
        ("What if a file doesn't work?", "Write to /paysupport in the bot. You get another version or a refund."),
        ("Are updates free?", "Yes. If I add looks to a pack you own, they arrive for free."),
    ],
    "footer_disclaimer": "Not affiliated with Blackmagic Design. Blackmagic Camera is a trademark of its owner; the name is used only to say which app the files are made for.",
    "terms": "Terms", "privacy": "Privacy", "refund": "Refunds", "license": "License",
    "free_look": "Free",
    "inapp": "Open this page in Safari or Chrome for the smoothest checkout.",
    "back_all": "All looks",
    "stars_note": "Payment is made in Telegram Stars inside the bot.",
    "not_found": "This look is not in the shop right now.",
    "guide_h": "How to install",
    "guides": "Guides",
    "updated": "Updated",
}

_cache: dict = {}


def load(lang: str) -> dict:
    """Переклад мови з luts_i18n/<lang>.json (порожньо, якщо файла немає)."""
    if lang not in _cache:
        try:
            with open(os.path.join(I18N_DIR, f"{lang}.json"), encoding="utf-8") as handle:
                _cache[lang] = json.load(handle)
        except OSError:
            _cache[lang] = {}
    return _cache[lang]


def text(lang: str) -> dict:
    """Словник інтерфейсу для мови: ключі, яких немає в перекладі, беруться з англійської."""
    return {**EN, **load(lang).get("ui", {})}


def translated() -> list[str]:
    """Мови з готовим перекладом (англійська завжди): лише їх віддаємо в hreflang і sitemap."""
    return [code for code in LUT_LANGS if code == "en" or load(code).get("ui")]
