"""
farm_dataset.py
===============
Entraîner HydroStress sur les données réelles d'une ferme.

Étapes (une commande chacune) :

  1. init        Décrire la ferme : position, culture, écartement, surface, sol, irrigation.
  2. climate     Télécharger le climat quotidien de la période (Open-Meteo, sans compte).
  3. irrigation  Lire les registres d'irrigation Excel (un fichier par campagne).
  4. balance     Bilan hydrique FAO-56 jour par jour -> Ks et classe de stress (sans Earth Engine).
  5. build       Dataset d'entraînement : 26 features (Sentinel-2 via Earth Engine + climat) + classe.
  6. train       Entraîner le modèle sur ce dataset (split par campagne, pas de fuite d'une année à l'autre).

Exemple (bloc 4, amandier, Errachidia) :

  python farm_dataset.py init --name "Bloc 4" --lat 31.887705 --lon -4.155879 \
      --crop amandier --spacing 7x5 --area-ha 102 --planting-year 2018 --irrigation goutte --soil sableux
  python farm_dataset.py climate farms/bloc-4.json --start 2018-01-01 --end 2025-12-31
  python farm_dataset.py irrigation farms/bloc-4.json registres/*.xlsx
  python farm_dataset.py balance farms/bloc-4.json
  python farm_dataset.py build farms/bloc-4.json --every-days 10
  python farm_dataset.py train farms/bloc-4.json

Fichiers produits dans data/<ferme>/ : climat.csv, irrigation.csv,
bilan_hydrique.csv, dataset.csv ; le modèle va dans models/<ferme>_*.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

from farm import CROPS, IRRIGATION, SOILS, Farm, parse_spacing

logger = logging.getLogger("farm_dataset")

LABEL_SOURCE = "bilan_hydrique_fao56"
WARMUP_DAYS = 60          # le bilan démarre réserve pleine : on ignore ses 60 premiers jours
HISTORY_DAYS = 60         # une date n'est étiquetée que si le registre couvre les 60 jours précédents


def data_dir(farm: Farm) -> Path:
    return Path("data") / farm.id


# ---------------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------------
def cmd_init(args) -> Path:
    row = tree = None
    if args.spacing:
        row, tree = parse_spacing(args.spacing)
    boundary = None
    if args.boundary:
        boundary = load_boundary(args.boundary)
    farm = Farm(
        name=args.name, latitude=args.lat, longitude=args.lon, crop=args.crop,
        spacing_row_m=row, spacing_tree_m=tree, area_ha=args.area_ha,
        planting_year=args.planting_year, canopy_diameter_m=args.canopy_m,
        irrigation=args.irrigation, soil=args.soil, boundary=boundary, notes=args.notes or "",
    )
    path = farm.save(args.farms_dir)
    print(farm.summary())
    print(f"\n✓ Ferme enregistrée : {path}")
    return path


def load_boundary(path: str) -> List[List[float]]:
    """Polygone GeoJSON (Feature, FeatureCollection ou Polygon) -> [[lon, lat], ...]."""
    gj = json.loads(Path(path).read_text(encoding="utf-8"))
    if gj.get("type") == "FeatureCollection":
        gj = gj["features"][0]
    if gj.get("type") == "Feature":
        gj = gj["geometry"]
    if gj.get("type") != "Polygon":
        raise ValueError("Le fichier de limites doit contenir un polygone GeoJSON.")
    return [[float(x), float(y)] for x, y, *_ in gj["coordinates"][0]]


def cmd_climate(args) -> pd.DataFrame:
    from climate_history import download_climate

    farm = Farm.load(args.farm)
    out = data_dir(farm) / "climat.csv"
    df = download_climate(farm.latitude, farm.longitude, args.start, args.end,
                          source=args.source, cache_file=str(out))
    rain = df.groupby(df["date"].dt.year).agg(pluie_mm=("precipitation_mm", "sum"), et0_mm=("et0_mm", "sum"),
                                               tmax_moy=("temperature_max_c", "mean"), jours=("date", "size"))
    print(rain.round(1).to_string())
    print(f"\n✓ {len(df)} jours dans {out}")
    return df


def cmd_irrigation(args) -> pd.DataFrame:
    from irrigation_register import campaign_of, coverage_report, read_registers

    farm = Farm.load(args.farm)
    if not farm.area_ha:
        raise SystemExit("La surface du bloc (--area-ha à l'étape init) est nécessaire pour convertir les m3 en mm.")
    daily = read_registers(args.files, farm.area_ha)
    out = data_dir(farm) / "irrigation.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out, index=False)

    report = coverage_report(daily)
    print(report.round(1).to_string())
    by_campaign = daily.assign(campagne=daily["date"].map(campaign_of)).groupby("campagne").agg(
        m3=("irrigation_m3", "sum"), mm=("irrigation_mm", "sum"), jours_irrigues=("date", "size"))
    print("\n" + by_campaign.round(0).to_string())
    empty = [str(m) for m, r in report.iterrows() if r["jours_irrigues"] == 0]
    if empty:
        print(f"\n⚠️  Mois sans aucun apport : {', '.join(empty)}")
        print("   Arrêt réel de l'irrigation, ou registre manquant ? Les longues périodes vides ne sont pas étiquetées.")
    print(f"\n✓ {len(daily)} jours irrigués dans {out}")
    return daily


def load_inputs(farm: Farm):
    climate_path = data_dir(farm) / "climat.csv"
    irr_path = data_dir(farm) / "irrigation.csv"
    if not climate_path.exists():
        raise SystemExit(f"{climate_path} introuvable : lancez d'abord l'étape climate.")
    climate = pd.read_csv(climate_path, parse_dates=["date"])
    irrigation = pd.read_csv(irr_path, parse_dates=["date"]) if irr_path.exists() else None
    if irrigation is None and farm.irrigation != "pluvial":
        raise SystemExit(f"{irr_path} introuvable : lancez d'abord l'étape irrigation.")
    return climate, irrigation


def labelled_dates(balance: pd.DataFrame, irrigation: Optional[pd.DataFrame], every_days: int,
                   start: Optional[str] = None, end: Optional[str] = None) -> List[pd.Timestamp]:
    """Dates d'échantillonnage dont les HISTORY_DAYS jours précédents sont couverts par le registre."""
    from irrigation_register import covered_months

    first = balance["date"].min() + pd.Timedelta(days=WARMUP_DAYS)
    last = balance["date"].max()
    if irrigation is not None and not irrigation.empty:
        first = max(first, irrigation["date"].min() + pd.Timedelta(days=WARMUP_DAYS))
        covered = covered_months(irrigation)
    else:
        covered = None
    if start:
        first = max(first, pd.Timestamp(start))
    if end:
        last = min(last, pd.Timestamp(end))
    dates = []
    d = first
    while d <= last:
        if covered is None or all(m in covered for m in pd.period_range(d - pd.Timedelta(days=HISTORY_DAYS), d, freq="M")):
            dates.append(d)
        d += pd.Timedelta(days=every_days)
    return dates


def cmd_balance(args) -> pd.DataFrame:
    from irrigation_register import campaign_of
    from water_balance import label_at, run_water_balance

    farm = Farm.load(args.farm)
    climate, irrigation = load_inputs(farm)
    balance = run_water_balance(climate, irrigation, farm)
    out = data_dir(farm) / "bilan_hydrique.csv"
    balance.to_csv(out, index=False)

    dates = labelled_dates(balance, irrigation, args.every_days)
    labels = pd.DataFrame([{"date": d, **dict(zip(("stress_class", "ks"), label_at(balance, d, thresholds=args.ks_thresholds)))}
                           for d in dates])
    if labels.empty:
        raise SystemExit("Aucune date étiquetable : vérifiez que climat et registres couvrent la même période.")
    labels["campagne"] = labels["date"].map(campaign_of)
    labels.to_csv(data_dir(farm) / "etiquettes.csv", index=False)

    b = balance.assign(campagne=balance["date"].map(campaign_of))
    summary = b.groupby("campagne").agg(
        pluie_mm=("precipitation_mm", "sum"), et0_mm=("et0_mm", "sum"), etc_mm=("etc_mm", "sum"),
        irrigation_mm=("irrigation_mm", "sum"), eta_mm=("eta_mm", "sum"), ks_moyen=("ks", "mean"))
    summary["couverture_besoin_%"] = 100 * (summary["eta_mm"] / summary["etc_mm"])
    print(summary.round(2).to_string())
    dist = labels.pivot_table(index="campagne", columns="stress_class", values="ks", aggfunc="size", fill_value=0)
    dist = dist.rename(columns={0: "normal", 1: "modéré", 2: "sévère"})
    print("\nÉtiquettes (une date tous les", args.every_days, "jours) :\n" + dist.to_string())
    print(f"\n✓ Bilan quotidien : {out}")
    return labels


def cmd_build(args) -> pd.DataFrame:
    import ee

    from climate_history import weather_features
    from extract_data import DataPipeline, DataUnavailableError, assemble_features, get_site_features
    from irrigation_register import campaign_of
    from water_balance import label_at, run_water_balance

    farm = Farm.load(args.farm)
    climate, irrigation = load_inputs(farm)
    balance = run_water_balance(climate, irrigation, farm)
    dates = labelled_dates(balance, irrigation, args.every_days, args.start, args.end)
    logger.info(f"{len(dates)} dates à extraire")

    pipeline = DataPipeline()
    coords = farm.parcel_coordinates()
    geometry = pipeline.sentinel.create_geometry(coords)
    site = get_site_features(geometry.centroid(maxError=1))
    zone_id = farm.zone[0]

    out = Path(args.output) if args.output else data_dir(farm) / "dataset.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, skipped = [], 0
    for i, d in enumerate(dates, 1):
        try:
            stats, n_img, valid, window = pipeline.extract_sentinel(geometry, d.to_pydatetime(), args.lookback_days)
            weather = weather_features(climate, d)
        except (DataUnavailableError, ee.EEException) as e:
            skipped += 1
            logger.warning(f"{d:%Y-%m-%d} ignoré : {e}")
            continue
        chirps_keys = ("precipitation_total_30j", "precipitation_total_7j", "precipitation_mean",
                       "max_consecutive_dry_days", "rainy_days_count")
        features = assemble_features(stats, {k: weather[k] for k in chirps_keys},
                                     {k: v for k, v in weather.items() if k not in chirps_keys},
                                     d.to_pydatetime(), site)
        label, ks = label_at(balance, d, thresholds=args.ks_thresholds)
        rows.append({**features, "stress_class": label, "ks": ks, "zone": zone_id, "crop": farm.crop,
                     "parcel_id": farm.id, "campagne": campaign_of(d), "date": d.strftime("%Y-%m-%d"),
                     "s2_images": n_img, "label_source": LABEL_SOURCE})
        if i % 10 == 0:
            pd.DataFrame(rows).to_csv(out, index=False)
            logger.info(f"{i}/{len(dates)} dates traitées")
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    print(f"✓ {len(df)} échantillons dans {out} ({skipped} dates sans image Sentinel-2 exploitable)")
    if not df.empty:
        print(df.groupby("campagne")["stress_class"].value_counts().unstack(fill_value=0).to_string())
    return df


def cmd_train(args):
    from train_model import train_production_model

    farm = Farm.load(args.farm)
    data = Path(args.data) if args.data else data_dir(farm) / "dataset.csv"
    df = pd.read_csv(data)
    if args.extra:
        extras = [pd.read_csv(p) for p in args.extra]
        df = pd.concat([df] + extras, ignore_index=True)
        if "campagne" in df.columns:
            df["campagne"] = df["campagne"].fillna(df.get("parcel_id", "autre"))
    n_groups = df["campagne"].nunique()
    if n_groups < 4:
        raise SystemExit(f"Seulement {n_groups} campagne(s) : il en faut au moins 4 pour séparer entraînement et test.")
    combined = data.with_name("dataset_entrainement.csv")
    df.to_csv(combined, index=False)
    output = args.output or f"models/{farm.id}"
    model, results = train_production_model(
        str(combined), output_path=output, use_grid_search=not args.no_grid_search,
        data_source=f"terrain:{farm.id}", group_column="campagne",
    )
    print(f"\n✓ Modèle : {output}_pipeline.joblib")
    print("  Pour l'utiliser dans l'application : copiez-le en models/hydrostress_pipeline.joblib "
          "et models/hydrostress_metadata.json (gardez une copie de l'ancien).")
    return model, results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Décrire la ferme")
    p.add_argument("--name", required=True)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--crop", required=True, help=f"Culture : {', '.join(CROPS)}")
    p.add_argument("--spacing", help="Écartement entre rangs x sur le rang, en mètres (ex. 7x5)")
    p.add_argument("--area-ha", type=float)
    p.add_argument("--planting-year", type=int)
    p.add_argument("--canopy-m", type=float, help="Diamètre actuel de la couronne (m), si connu")
    p.add_argument("--irrigation", default="goutte", choices=list(IRRIGATION))
    p.add_argument("--soil", default="limoneux", choices=list(SOILS))
    p.add_argument("--boundary", help="Limites de la parcelle (fichier GeoJSON)")
    p.add_argument("--notes")
    p.add_argument("--farms-dir", default="farms")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("climate", help="Télécharger le climat quotidien")
    p.add_argument("farm")
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--source", default="open-meteo", choices=["open-meteo", "nasa-power"])
    p.set_defaults(func=cmd_climate)

    p = sub.add_parser("irrigation", help="Lire les registres d'irrigation (xlsx)")
    p.add_argument("farm")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_irrigation)

    def thresholds(text):
        a, b = (float(x) for x in text.split(","))
        return (a, b)

    for name, func, help_ in (("balance", cmd_balance, "Bilan hydrique et étiquettes (sans Earth Engine)"),
                              ("build", cmd_build, "Dataset d'entraînement (Earth Engine)")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("farm")
        p.add_argument("--every-days", type=int, default=10)
        p.add_argument("--ks-thresholds", type=thresholds, default=(0.60, 0.85),
                       help="Seuils Ks sévère,modéré (défaut 0.60,0.85)")
        if name == "build":
            p.add_argument("--start")
            p.add_argument("--end")
            p.add_argument("--lookback-days", type=int, default=30)
            p.add_argument("--output")
        p.set_defaults(func=func)

    p = sub.add_parser("train", help="Entraîner le modèle sur le dataset de la ferme")
    p.add_argument("farm")
    p.add_argument("--data", help="Dataset (défaut : data/<ferme>/dataset.csv)")
    p.add_argument("--extra", nargs="*", help="Autres datasets à ajouter (autres blocs, VHI...)")
    p.add_argument("--output")
    p.add_argument("--no-grid-search", action="store_true")
    p.set_defaults(func=cmd_train)
    return parser


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ValueError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
