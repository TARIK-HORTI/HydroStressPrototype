import string
from datetime import date

from i18n import GLOSSARY_TEXT, IMAGERY_TEXT, LANGS, UI, set_lang, t
from imagery import LAYERS, glossary, interpret_change, layer_text, theme_label, THEMES
from i18n_pages import PAGES
from imagery_text import INTERP, LAYER_TEXT, THEME_TEXT


def placeholders(text):
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def all_tables():
    yield from UI.items()
    yield from IMAGERY_TEXT.items()
    yield from INTERP.items()
    yield from THEME_TEXT.items()
    yield from PAGES.items()
    for k, fields in GLOSSARY_TEXT.items():
        for f, entry in fields.items():
            yield f"{k}.{f}", entry


def test_every_text_has_three_languages_with_same_placeholders():
    for key, entry in all_tables():
        for lang in LANGS:
            assert lang in entry, (key, lang)
        ref = placeholders(entry["fr"])
        for lang in LANGS:
            assert entry[lang] or not entry["fr"], (key, lang)
            assert placeholders(entry[lang]) == ref, (key, lang)


def test_layer_texts_translated():
    for layer in LAYERS:
        for field in ("label", "description"):
            for lang in ("ar", "en"):
                assert LAYER_TEXT[layer][field][lang], (layer, field, lang)
                assert layer_text(layer, field, lang) != layer_text(layer, field, "fr")
    for theme in THEMES:
        assert theme_label(theme, "ar") != theme_label(theme, "fr")


def test_t_and_fallback():
    set_lang("ar")
    assert t("btn_analyse") == "🔍 تحليل القطعة"
    assert t("chip_zones", n=9) == "📍 9 مناطق فلاحية"
    set_lang("xx")  # langue inconnue -> français
    assert t("btn_analyse") == "🔍 Analyser la parcelle"
    assert t("unknown_key") == "unknown_key"


def test_interpretation_in_each_language():
    a = {"NDVI": 0.55, "NDMI": 0.25, "NDRE": 0.32, "PSRI": 0.02, "MSI": 0.75}
    b = {**a, "NDMI": 0.10, "MSI": 1.0}
    out = {lang: interpret_change(a, b, date(2026, 6, 1), date(2026, 7, 1), "Olivier", lang=lang) for lang in LANGS}
    assert out["fr"]["hypotheses"][0]["title"] == "Stress hydrique"
    assert out["ar"]["hypotheses"][0]["title"] == "إجهاد مائي"
    assert out["en"]["hypotheses"][0]["title"] == "Water stress"
    assert out["ar"]["disclaimer"] != out["fr"]["disclaimer"]
    assert [h["key"] for h in out["ar"]["hypotheses"]] == [h["key"] for h in out["fr"]["hypotheses"]]


def test_glossary_languages():
    for lang in LANGS:
        g = glossary(lang)
        assert set(g) == set(GLOSSARY_TEXT)
        assert all(g[k]["use"] for k in g)
