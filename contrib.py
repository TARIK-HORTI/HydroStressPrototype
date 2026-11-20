"""
contrib.py
==========
Contributions de données : un agriculteur décrit sa ferme, envoie ses registres
d'irrigation (et d'autres fichiers utiles) pour aider à entraîner HydroStress.

Chaque contribution est rangée dans un dossier :
    contributions/<AAAAMMJJ-HHMMSS>_<ferme>_<ref>/
        contribution.json   ferme, contact, consentement, résumé des registres
        fichiers/...        fichiers envoyés, tels quels

Stockage :
- Google Cloud Storage si CONTRIB_BUCKET est défini (Secrets Streamlit ou
  variable d'environnement) : durable, avec le compte de service déjà utilisé
  pour Earth Engine (rôle « Storage Object Creator » sur le bucket).
- Sinon, dossier local ``contributions/`` (développement uniquement : sur
  Streamlit Cloud, il est effacé à chaque redémarrage).
"""

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MAX_FILES = 30
MAX_TOTAL_MB = 50
REGISTER_TYPES = ("xlsx", "xls", "csv")
OTHER_TYPES = ("xlsx", "xls", "csv", "pdf", "jpg", "jpeg", "png", "txt", "kml", "geojson", "zip")
CONSENT_TEXT = (
    "J'accepte que ces données soient utilisées par HydroStress pour entraîner et évaluer son modèle. "
    "Le nom et la position de ma ferme ne seront jamais publiés, et je peux demander leur suppression à tout moment."
)


def _slug(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").lower()).strip("-")
    return text[:40] or "ferme"


def _safe_name(name: str) -> str:
    name = Path(name or "fichier").name
    name = re.sub(r"[^\w.\- ]+", "_", name).strip() or "fichier"
    return name[:120]


@dataclass
class Contribution:
    contact: Dict[str, str]
    farm: Dict
    consent: bool
    registers: List[Tuple[str, bytes]] = field(default_factory=list)
    other_files: List[Tuple[str, bytes]] = field(default_factory=list)
    comment: str = ""
    register_summary: Optional[Dict] = None

    def errors(self) -> List[str]:
        """Liste des problèmes qui empêchent l'envoi (vide si tout est bon)."""
        errs = []
        if not self.consent:
            errs.append("Cochez la case d'accord pour l'utilisation des données.")
        if not (self.contact.get("name") or "").strip():
            errs.append("Indiquez votre nom.")
        if not ((self.contact.get("phone") or "").strip() or (self.contact.get("email") or "").strip()):
            errs.append("Indiquez un téléphone (WhatsApp) ou un e-mail pour qu'on puisse vous recontacter.")
        email = (self.contact.get("email") or "").strip()
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errs.append("L'adresse e-mail ne semble pas valide.")
        if not self.registers and not self.other_files:
            errs.append("Ajoutez au moins un fichier (registre d'irrigation de préférence).")
        files = self.registers + self.other_files
        if len(files) > MAX_FILES:
            errs.append(f"{MAX_FILES} fichiers au maximum.")
        if sum(len(b) for _, b in files) > MAX_TOTAL_MB * 1024 * 1024:
            errs.append(f"{MAX_TOTAL_MB} Mo au maximum au total.")
        return errs

    def folder_name(self, now: Optional[datetime] = None, ref: Optional[str] = None) -> str:
        now = now or datetime.now(timezone.utc)
        ref = ref or uuid.uuid4().hex[:8]
        return f"{now:%Y%m%d-%H%M%S}_{_slug(self.farm.get('name', ''))}_{ref}"

    def manifest(self, ref: str, now: datetime) -> Dict:
        return {
            "reference": ref,
            "received_at": now.isoformat(timespec="seconds"),
            "contact": {k: (v or "").strip() for k, v in self.contact.items()},
            "farm": self.farm,
            "comment": self.comment.strip(),
            "consent": {"accepted": bool(self.consent), "text": CONSENT_TEXT},
            "files": {
                "registres": [_safe_name(n) for n, _ in self.registers],
                "autres": [_safe_name(n) for n, _ in self.other_files],
            },
            "register_summary": self.register_summary,
        }


def summarize_registers(registers: List[Tuple[str, bytes]], area_ha: Optional[float]) -> Optional[Dict]:
    """Lit les registres Excel avec le lecteur du projet pour un aperçu (campagnes, volumes).

    Renvoie None si rien n'est lisible : la contribution reste acceptée (lecture manuelle ensuite).
    """
    import tempfile

    xlsx = [(n, b) for n, b in registers if n.lower().endswith(".xlsx")]
    if not xlsx or not area_ha:
        return None
    from irrigation_register import campaign_of, read_registers

    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, data in xlsx:
            p = Path(tmp) / _safe_name(name)
            p.write_bytes(data)
            paths.append(str(p))
        try:
            daily = read_registers(paths, area_ha)
        except Exception:
            return None
    if daily.empty:
        return None
    camp = daily.assign(campagne=daily["date"].map(campaign_of)).groupby("campagne").agg(
        m3=("irrigation_m3", "sum"), jours=("date", "size"))
    return {
        "debut": daily["date"].min().strftime("%Y-%m-%d"),
        "fin": daily["date"].max().strftime("%Y-%m-%d"),
        "campagnes": {c: {"m3": round(float(r.m3)), "jours_irrigues": int(r.jours)} for c, r in camp.iterrows()},
    }


# ---------------------------------------------------------------------------
# Stockage
# ---------------------------------------------------------------------------
class LocalStorage:
    durable = False

    def __init__(self, root: str = "contributions"):
        self.root = Path(root)

    def put(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def describe(self) -> str:
        return f"dossier local {self.root}"


class GCSStorage:
    durable = True

    def __init__(self, bucket: str, credentials_info: Optional[dict] = None, client=None):
        if client is None:
            from google.cloud import storage

            if credentials_info:
                from google.oauth2 import service_account

                creds = service_account.Credentials.from_service_account_info(credentials_info)
                client = storage.Client(project=credentials_info.get("project_id"), credentials=creds)
            else:
                client = storage.Client()
        self.bucket_name = bucket
        self.bucket = client.bucket(bucket)

    def put(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.bucket.blob(f"contributions/{path}").upload_from_string(data, content_type=content_type)

    def describe(self) -> str:
        return f"gs://{self.bucket_name}/contributions"


def _setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def get_storage():
    """GCS si CONTRIB_BUCKET est configuré, sinon stockage local (non durable)."""
    bucket = _setting("CONTRIB_BUCKET")
    if not bucket:
        return LocalStorage()
    from extract_data import _service_account_from_env, _service_account_from_streamlit

    info = _service_account_from_streamlit() or _service_account_from_env()
    return GCSStorage(bucket, info)


def _content_type(name: str) -> str:
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    return {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel", "csv": "text/csv", "pdf": "application/pdf",
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "txt": "text/plain",
        "json": "application/json", "geojson": "application/geo+json", "kml": "application/vnd.google-earth.kml+xml",
        "zip": "application/zip",
    }.get(ext, "application/octet-stream")


def submit(contribution: Contribution, storage=None, now: Optional[datetime] = None) -> str:
    """Enregistre la contribution. Renvoie sa référence (8 caractères). Lève ValueError si incomplète."""
    errs = contribution.errors()
    if errs:
        raise ValueError(" ".join(errs))
    storage = storage or get_storage()
    now = now or datetime.now(timezone.utc)
    ref = uuid.uuid4().hex[:8]
    folder = contribution.folder_name(now, ref)
    used = set()
    for kind, files in (("registres", contribution.registers), ("autres", contribution.other_files)):
        for name, data in files:
            safe = _safe_name(name)
            while f"{kind}/{safe}" in used:
                safe = "_" + safe
            used.add(f"{kind}/{safe}")
            storage.put(f"{folder}/fichiers/{kind}/{safe}", data, _content_type(safe))
    manifest = json.dumps(contribution.manifest(ref, now), ensure_ascii=False, indent=2).encode("utf-8")
    storage.put(f"{folder}/contribution.json", manifest, "application/json")
    return ref
