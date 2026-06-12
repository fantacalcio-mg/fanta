"""Entity resolution: fuzzy matching verso dim_player."""

import logging
from typing import NamedTuple

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


class ResolverResult(NamedTuple):
    """Risultato di una risoluzione."""

    player_uid: str | None
    confidence: float
    manual: bool = False


def normalize_squad(squadra: str) -> str:
    """Normalizza nome squadra (lowercase, trim)."""
    return squadra.lower().strip()


def resolve_player(
    nome: str,
    squadra: str,
    existing_players: dict[tuple[str, str], str],
    threshold: float = 85.0,
) -> ResolverResult:
    """Risolve un giocatore verso dim_player via fuzzy matching.

    Strategia:
    1. Prova match su NOME SOLO (ignora squadra inizialmente)
    2. Se confidence ≥ threshold: accettato
    3. Se nessun match o confidence bassa, escala a cross-squad match

    Nota: Per storico multi-stagione, non possiamo usare squadra corrente perché
    il dim_player ha solo squadre della stagione 2025-26. Usiamo il nome come
    chiave primaria.

    Args:
        nome: nome del giocatore
        squadra: squadra (informativa, non usata per matching nel storico)
        existing_players: dict[tuple(nome_norm, squadra), player_uid] da DuckDB
        threshold: soglia di confidence (0-100)

    Returns:
        ResolverResult(uid, confidence, manual=False)
    """
    best_uid = None
    best_confidence = 0.0

    # Estratto nomi da existing_players (ignora squadra)
    nome_to_uids: dict[str, str] = {}
    for (existing_nome, _existing_squadra), uid in existing_players.items():
        # Se lo stesso nome ha squad diverse, usa l'ultimo (raro)
        nome_to_uids[existing_nome] = uid

    # Match su NOME SOLO
    for existing_nome, uid in nome_to_uids.items():
        confidence = fuzz.token_set_ratio(nome.lower(), existing_nome.lower())

        if confidence > best_confidence:
            best_confidence = confidence
            best_uid = uid

    # Accetta solo se sopra soglia
    if best_confidence >= threshold:
        return ResolverResult(best_uid, best_confidence, manual=False)

    return ResolverResult(None, best_confidence, manual=False)


def load_existing_players_from_db(db) -> dict[tuple[str, str], str]:
    """Carica dim_player da DuckDB in memoria per ER.

    Carica TUTTI i giocatori di TUTTE le stagioni per supportare ingestion storico.

    Returns:
        dict[tuple(nome_norm, squadra), player_uid]
    """
    # Carica da dim_player (master list) + dim_player_season (per squadra)
    # NON filtrare per stagione: serve per supportare storico multi-stagione
    query = """
    SELECT DISTINCT dp.player_uid, dp.nome_norm, dps.squadra
    FROM dim_player dp
    JOIN dim_player_season dps ON dp.player_uid = dps.player_uid
    """
    result = db.execute(query).fetchall()

    # Costruisci dizionario (nome_norm, squadra) → player_uid
    # Se uno stesso giocatore ha giocato in squadre diverse, crea entry separate
    players = {}
    for player_uid, nome_norm, squadra in result:
        squadra_norm = normalize_squad(squadra)
        # Usa il nome_norm dalla dim_player (canonico)
        key = (nome_norm, squadra_norm)
        players[key] = player_uid

    return players
