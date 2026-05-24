"""Core squad manager — FEAT-006 TASK-001.

Feature flag: HARNESS_FEATURE_SQUAD_NAMESPACE_V1 (default OFF until /a-ship).
"""

import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

_SQUAD_ID_RE = re.compile(r"^[a-z0-9-]{1,20}$")
_ITEM_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")


@dataclass(frozen=True)
class SquadConfig:
    id: str
    name: str
    prefix: str
    wip_limit: int
    owner: str


def load_squad_config(swarm_yaml_path: Path) -> list[SquadConfig]:
    """Carrega squads de swarm.yaml. Retorna [] se arquivo ou seção ausente."""
    if not swarm_yaml_path.exists():
        return []

    try:
        raw = swarm_yaml_path.read_text(encoding="utf-8")
    except OSError:
        return []

    if yaml is None:  # pragma: no cover
        raise ImportError("PyYAML required for load_squad_config")

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"swarm.yaml YAML inválido: {exc}") from exc

    if not isinstance(data, dict):
        return []

    squads_raw = data.get("squads")
    if not squads_raw:
        return []

    result: list[SquadConfig] = []
    for entry in squads_raw:
        squad_id = str(entry.get("id", ""))
        if not _SQUAD_ID_RE.match(squad_id):
            raise ValueError(
                f"squad_id inválido: '{squad_id}'. Deve corresponder a [a-z0-9-]{{1,20}}."
            )
        result.append(
            SquadConfig(
                id=squad_id,
                name=str(entry.get("name", squad_id)),
                prefix=str(entry.get("prefix", squad_id.upper())),
                wip_limit=int(entry.get("wip_limit", 5)),
                owner=str(entry.get("owner", "")),
            )
        )
    return result


def format_item_id(squad_prefix: str, seq: int) -> str:
    """Retorna '{SQUAD_PREFIX}-{seq:03d}' (ex: ALPHA-001)."""
    return f"{squad_prefix}-{seq:03d}"


def resolve_squad(item_id: str, config: list[SquadConfig]) -> str:
    """Retorna squad_id do item ou 'default'.

    Modo solo (config vazio): sempre 'default' sem warning.
    Modo multi-squad: emite UserWarning se item_id não corresponde a nenhum prefixo.
    """
    for squad in config:
        if item_id.startswith(f"{squad.prefix}-"):
            return squad.id

    if config:
        warnings.warn(
            f"Item '{item_id}' não corresponde a nenhum squad prefix — atribuído a 'default'.",
            UserWarning,
            stacklevel=2,
        )
    return "default"


def validate_item_id(item_id: str, config: list[SquadConfig]) -> bool:
    """True se ID segue padrão FEAT-NNN ou PREFIX-NNN de squad conhecido. Rejeita path traversal."""
    if not isinstance(item_id, str) or not item_id:
        return False
    if not _ITEM_ID_RE.match(item_id):
        return False
    return True
