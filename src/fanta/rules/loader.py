from pathlib import Path

import yaml

from .models import LegaConfig


def load_rules(config_path: str | Path) -> LegaConfig:
    """Carica e valida il config regole da YAML.

    Args:
        config_path: path a rules_lega.yaml

    Returns:
        LegaConfig validato

    Raises:
        FileNotFoundError: se il file non esiste
        ValueError: se il config è invalido (validazione pydantic)
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return LegaConfig(**data)
