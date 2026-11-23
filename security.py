"""
security.py
===========
Protections de l'application publique :

- limite d'usage par session des calculs Earth Engine (analyse, images, zones), pour qu'un robot ou
  un visiteur pressé n'épuise pas le quota du compte de service ;
- espace administrateur (entraînement sur une ferme) fermé par un mot de passe gardé dans les
  Secrets, comparé en temps constant ; sans mot de passe configuré, l'espace n'existe pas ;
- messages d'erreur publics génériques : le détail technique part dans les journaux du serveur,
  jamais à l'écran (pas de chemin, de clé ni de trace de pile visible).
"""

from __future__ import annotations

import hmac
import logging
import time
import uuid
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# action -> (nombre maximal, fenêtre en secondes) par session
RATE_LIMITS: Dict[str, Tuple[int, int]] = {
    "analysis": (15, 3600),
    "images": (20, 3600),
    "zones": (20, 3600),
    "station": (10, 3600),
    "contribution": (3, 3600),
}

ADMIN_SECRET = "HYDROSTRESS_ADMIN_PASSWORD"
MIN_ADMIN_PASSWORD_LENGTH = 12
MAX_ADMIN_ATTEMPTS = 5


def prune(timestamps: List[float], now: float, window: int) -> List[float]:
    return [ts for ts in timestamps if now - ts < window]


def rate_check(timestamps: List[float], now: float, limit: int, window: int) -> Tuple[bool, int]:
    """(autorisé, secondes avant la prochaine tentative possible)."""
    recent = prune(timestamps, now, window)
    if len(recent) < limit:
        return True, 0
    return False, int(window - (now - min(recent))) + 1


def allow(action: str, state, now: Optional[float] = None) -> Tuple[bool, int]:
    """Enregistre une tentative de `action` dans l'état de session si elle est autorisée."""
    limit, window = RATE_LIMITS[action]
    now = time.time() if now is None else now
    key = f"_rate_{action}"
    stamps = prune(list(state.get(key, [])), now, window)
    ok, wait = rate_check(stamps, now, limit, window)
    if ok:
        stamps.append(now)
    state[key] = stamps
    return ok, wait


def admin_password(secrets_getter) -> Optional[str]:
    """Mot de passe administrateur configuré, ou None s'il est absent ou trop court."""
    try:
        value = secrets_getter(ADMIN_SECRET)
    except Exception:
        return None
    value = str(value or "").strip()
    return value if len(value) >= MIN_ADMIN_PASSWORD_LENGTH else None


def check_password(given: str, expected: str) -> bool:
    return hmac.compare_digest((given or "").encode(), (expected or "").encode())


def log_incident(where: str, exc: BaseException) -> str:
    """Journalise une erreur avec une référence courte, affichable sans rien révéler."""
    ref = uuid.uuid4().hex[:8]
    logger.error("[%s] %s : %s", ref, where, exc, exc_info=exc)
    return ref
