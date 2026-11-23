from i18n import LANGS
from region import CROPS as REGION_CROPS, ZONES
from report_text import (CLASS_TEXT, CROP_NAMES, CROP_TIPS_TEXT, REC_TEXT, ZONE_NAMES, class_label,
                         localized_recommendations)


def test_french_texts_match_the_model():
    from predict import CROP_TIPS, RECOMMENDATIONS_DB
    for idx, rec in RECOMMENDATIONS_DB.items():
        assert REC_TEXT[idx]["title"]["fr"] == rec["title"]
        assert [a["fr"] for a in REC_TEXT[idx]["actions"]] == rec["actions"]
    for crop, tips in CROP_TIPS.items():
        assert CROP_TIPS_TEXT[crop]["fr"] == tips[0]


def test_everything_translated():
    for z in ZONES:
        assert ZONE_NAMES[z]["ar"] and ZONE_NAMES[z]["en"]
    for c in REGION_CROPS:
        assert CROP_NAMES[c]["ar"] and CROP_NAMES[c]["en"], c
    for idx in CLASS_TEXT:
        for lang in LANGS:
            assert class_label(idx, lang)
    for entry in [*CROP_TIPS_TEXT.values(), *(a for r in REC_TEXT.values() for a in r["actions"])]:
        assert set(entry) == set(LANGS)


def test_localized_recommendations_same_structure():
    fr = localized_recommendations(2, "Palmier dattier", "errachidia", "high", "fr")
    ar = localized_recommendations(2, "Palmier dattier", "errachidia", "high", "ar")
    en = localized_recommendations(2, "Palmier dattier", "errachidia", "high", "en")
    assert len(fr["actions"]) == len(ar["actions"]) == len(en["actions"]) == 5
    assert "ORMVA du Tafilalet" in fr["actions"][-1]
    assert "تافيلالت" in ar["actions"][-1]
    assert "Tafilalet" in en["actions"][-1]
    assert ar["priority"] == "عالية"
