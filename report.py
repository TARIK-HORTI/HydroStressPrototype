"""
report.py
=========
Construction du rapport d'analyse d'une parcelle (dictionnaire + export HTML
autonome, imprimable en PDF depuis le navigateur).
"""

from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional

from region import REGION_NAME

CLASS_STYLES = {
    0: {"label": "Normal", "color": "#22C55E", "summary": "La parcelle ne montre pas de stress hydrique marqué."},
    1: {"label": "Modéré", "color": "#F59E0B", "summary": "Stress hydrique modéré : ajuster l'irrigation et surveiller."},
    2: {"label": "Sévère", "color": "#EF4444", "summary": "Stress hydrique sévère : intervention rapide recommandée."},
}

STATUS_LABELS = {"healthy": "Normal", "low": "Bas", "high": "Élevé", "unknown": "—"}


def build_report(
    *,
    coordinates: List[List[float]],
    area_km2: float,
    zone: str,
    crop: str,
    data: Dict[str, Any],
    prediction: Dict[str, Any],
    recommendations: Dict[str, Any],
    interpretation: Dict[str, Dict[str, Any]],
    model_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Rassemble tout ce qui compose le rapport d'une parcelle."""
    lons = [c[0] for c in coordinates]
    lats = [c[1] for c in coordinates]
    features = data["features"]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "region": REGION_NAME,
        "zone": zone,
        "crop": crop,
        "parcel": {
            "centroid": [round(sum(lats) / len(lats), 5), round(sum(lons) / len(lons), 5)],
            "area_ha": round(area_km2 * 100, 2),
            "vertices": len(coordinates) - 1 if coordinates[0] == coordinates[-1] else len(coordinates),
        },
        "analysis_date": data["date_analyzed"],
        "sentinel_meta": data.get("sentinel_meta", {}),
        "demo": bool(data.get("demo")),
        "prediction": prediction,
        "recommendations": recommendations,
        "interpretation": interpretation,
        "weather": {
            "precipitation_30d_mm": round(features["precipitation_total_30j"], 1),
            "precipitation_7d_mm": round(features["precipitation_total_7j"], 1),
            "dry_days_max": int(features["max_consecutive_dry_days"]),
            "temperature_mean_c": round(features["temperature_mean"], 1),
            "temperature_max_c": round(features["temperature_max"], 1),
            "humidity_mean_pct": round(features["humidity_mean"], 0),
        },
        "model": {
            "data_source": (model_meta or {}).get("data_source", "inconnue"),
            "trained_at": (model_meta or {}).get("created_at", "")[:10],
        },
    }


def report_to_html(report: Dict[str, Any]) -> str:
    """Rapport HTML autonome (aucune ressource externe)."""
    pred = report["prediction"]
    style = CLASS_STYLES[pred["class_index"]]
    probs = pred["probabilities"]
    w = report["weather"]
    meta = report["sentinel_meta"]
    e = lambda v: escape(str(v))  # noqa: E731

    rows = "".join(
        f"<tr><td>{e(name)}</td><td>{e(info['value'])}</td>"
        f"<td>{e(info['healthy_range'][0])} – {e(info['healthy_range'][1])}</td>"
        f"<td>{e(STATUS_LABELS.get(info['status'], info['status']))}</td></tr>"
        for name, info in report["interpretation"].items()
    )
    actions = "".join(f"<li>{e(a)}</li>" for a in report["recommendations"]["actions"])
    prob_bars = "".join(
        f"<div class='bar'><span>{label}</span><div><i style='width:{probs[key]}%;background:{color}'></i></div>"
        f"<b>{probs[key]:.1f} %</b></div>"
        for label, key, color in [("Normal", "normal", "#22C55E"), ("Modéré", "moderate", "#F59E0B"),
                                  ("Sévère", "severe", "#EF4444")]
    )
    warnings = []
    if report["demo"]:
        warnings.append("Données de DÉMONSTRATION : les valeurs ne proviennent pas des satellites pour cette parcelle.")
    if report["model"]["data_source"] == "synthetic":
        warnings.append("Modèle entraîné sur des données synthétiques : résultat indicatif, non validé sur le terrain.")
    warning_html = "".join(f"<p class='warn'>⚠ {e(wn)}</p>" for wn in warnings)
    s2 = (f"Composite Sentinel-2 de {e(meta.get('image_count', '—'))} image(s) sur {e(meta.get('window_days', '—'))} jours, "
          f"{meta.get('valid_pixel_fraction', 0):.0%} de pixels valides.") if meta else ""
    lat, lon = report["parcel"]["centroid"]

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Rapport HydroStress — {e(report['analysis_date'])}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;color:#0F172A;background:#F8FAFC;margin:0;padding:32px}}
.wrap{{max-width:880px;margin:auto;background:#fff;border-radius:16px;padding:32px;box-shadow:0 4px 24px rgba(15,23,42,.08)}}
h1{{margin:0;font-size:24px}} h2{{font-size:16px;margin:28px 0 10px;color:#334155;text-transform:uppercase;letter-spacing:.06em}}
.muted{{color:#64748B;font-size:14px}}
.status{{border-left:8px solid {style['color']};background:#F1F5F9;border-radius:12px;padding:16px 20px;margin-top:20px}}
.status b{{font-size:22px;color:{style['color']}}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.kpi{{background:#F1F5F9;border-radius:10px;padding:12px}} .kpi span{{display:block;color:#64748B;font-size:12px}} .kpi b{{font-size:18px}}
table{{width:100%;border-collapse:collapse;font-size:14px}} td,th{{padding:8px;border-bottom:1px solid #E2E8F0;text-align:left}}
.bar{{display:grid;grid-template-columns:80px 1fr 70px;align-items:center;gap:10px;margin:6px 0;font-size:14px}}
.bar div{{background:#E2E8F0;border-radius:6px;height:10px}} .bar i{{display:block;height:10px;border-radius:6px}}
.warn{{background:#FEF3C7;color:#92400E;border-radius:8px;padding:10px 14px;font-size:14px}}
@media print{{body{{background:#fff;padding:0}} .wrap{{box-shadow:none}}}}
</style></head><body><div class="wrap">
<h1>💧 Rapport de stress hydrique</h1>
<p class="muted">{e(report['region'])} · Zone : {e(report['zone'])} · Culture : {e(report['crop'])}<br>
Date analysée : <b>{e(report['analysis_date'])}</b> · Parcelle : {e(report['parcel']['area_ha'])} ha, centre {lat}, {lon}<br>
Généré le {e(report['generated_at'].replace('T', ' '))}</p>
{warning_html}
<div class="status"><b>{e(style['label'])}</b> — confiance {pred['confidence_percent']:.1f} %<br>{e(style['summary'])}</div>
<h2>Probabilités</h2>{prob_bars}
<h2>Indicateurs</h2>
<div class="grid">
<div class="kpi"><span>NDVI moyen</span><b>{report['interpretation']['NDVI']['value']}</b></div>
<div class="kpi"><span>NDWI moyen</span><b>{report['interpretation']['NDWI']['value']}</b></div>
<div class="kpi"><span>MSI moyen</span><b>{report['interpretation']['MSI']['value']}</b></div>
<div class="kpi"><span>Pluie 30 j</span><b>{w['precipitation_30d_mm']} mm</b></div>
<div class="kpi"><span>T° max (30 j)</span><b>{w['temperature_max_c']} °C</b></div>
<div class="kpi"><span>Jours secs consécutifs</span><b>{w['dry_days_max']}</b></div>
</div>
<p class="muted">{s2}</p>
<h2>Indices spectraux</h2>
<table><tr><th>Indice</th><th>Valeur</th><th>Plage de référence</th><th>État</th></tr>{rows}</table>
<h2>Recommandations — priorité {e(report['recommendations']['priority'].upper())}</h2>
<p><b>{e(report['recommendations']['title'])}</b></p><ul>{actions}</ul>
<p class="muted">Sources : Sentinel-2 (Copernicus), CHIRPS (UCSB-CHG), ERA5-Land (ECMWF). Modèle : Random Forest calibré
({e(report['model']['data_source'])}, entraîné le {e(report['model']['trained_at'])}). Identifiant : {e(pred.get('prediction_id', ''))}</p>
</div></body></html>"""
