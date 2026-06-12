"""Entity resolution: generazione e gestione player_uid canonici."""

import hashlib
import unicodedata
from datetime import date


def normalize_name(nome: str) -> str:
    """Normalizza un nome per entity resolution.

    - Rimuove accenti (NFD + filter)
    - Converte a lowercase
    - Ordina token alfabeticamente (token sort)
    - Rimuove whitespace extra

    Esempio:
      "Nicolò Barella" -> "barella nicolo"
      "De Rossi Andrea" -> "andrea de rossi"
    """
    # Rimuovi accenti
    nfd = unicodedata.normalize("NFD", nome)
    without_accents = "".join(c for c in nfd if unicodedata.category(c) != "Mn")

    # Lowercase e split
    tokens = without_accents.lower().split()

    # Ordina alfabeticamente
    tokens.sort()

    return " ".join(tokens)


def generate_player_uid(
    nome: str,
    squadra: str = None,
    ruolo: str = None,
    data_nascita: date | None = None,
) -> str:
    """Genera player_uid canonico stabile.

    Deterministic hash su nome_norm + data_nascita (SENZA squadra/ruolo).
    Cross-stagione determinism: stesso giocatore → stesso UID, indipendentemente da trasferimenti.

    IDENTITY: nome_norm + data_nascita (la squadra non è parte dell'identità)

    Args:
        nome: nome giocatore
        squadra: IGNORATO (presente per backwards-compat, non usato)
        ruolo: IGNORATO (presente per backwards-compat, non usato)
        data_nascita: data di nascita (opzionale, disambiguatore omonimi)

    Returns:
        UID di 16 caratteri hex (SHA1 troncato)
    """
    nome_norm = normalize_name(nome)
    parts = [nome_norm]

    if data_nascita:
        parts.append(str(data_nascita))

    key = "|".join(parts)
    sha1_hash = hashlib.sha1(key.encode()).hexdigest()
    return sha1_hash[:16]
