"""Motore di ricalcolo fantavoto individuale."""

import logging

from fanta.rules.models import LegaConfig

logger = logging.getLogger(__name__)


def calcola_fantavoto(
    voto: float,
    gol: int,
    assist_tot: int,
    ammonizioni: int,
    espulsioni: int,
    autogol: int | None,
    rig_segnati: int,
    rig_sbagliati: int | None,
    rig_parati: int,
    gol_subiti: int,
    clean_sheet: int | None,
    regole: LegaConfig,
    presenze_voto: int = 0,
    assist_tier_available: bool = False,
) -> float:
    """Calcola fantavoto individuale MEDIO (per partita).

    NON applica modificatori collettivi/scontro (quelli vengono in M2+ formazione).

    Args:
        voto: voto base MEDIO (es. 6.5)
        gol: gol segnati TOTALI (di stagione)
        assist_tot: assist totali TOTALI
        ammonizioni: ammonizioni ricevute TOTALI
        espulsioni: espulsioni ricevute TOTALI
        autogol: autogol TOTALI (null se non disponibile)
        rig_segnati: rigori segnati TOTALI
        rig_sbagliati: rigori sbagliati TOTALI (null se non disponibile)
        rig_parati: rigori parati TOTALI (portieri)
        gol_subiti: gol subiti TOTALI (portieri)
        clean_sheet: partite da imbattuto TOTALI (null se non disponibile)
        regole: LegaConfig con i bonus
        presenze_voto: numero di presenze con voto (per normalizzare bonus a media per partita)
        assist_tier_available: se True, assist sono già classificati (attualmente sempre False)

    Returns:
        Fantavoto MEDIO per partita (arrotondato a 3 decimali)
    """
    bi = regole.bonus_individuali

    fv = voto

    # Bonus totali di stagione, poi dividi per presenze per ottenere media per partita
    if presenze_voto > 0:
        bonus_totale = 0.0
        bonus_totale += gol * bi.gol_segnato
        bonus_totale += assist_tot * bi.assist.fallback_se_tier_non_disponibile
        bonus_totale += ammonizioni * bi.ammonizione
        bonus_totale += espulsioni * bi.espulsione

        if autogol is not None:
            bonus_totale += autogol * bi.autogol

        bonus_totale += rig_segnati * bi.rigore_segnato

        if rig_sbagliati is not None:
            bonus_totale += rig_sbagliati * bi.rigore_sbagliato

        bonus_totale += rig_parati * bi.rigore_parato
        bonus_totale += gol_subiti * bi.gol_subito_portiere

        if clean_sheet is not None:
            bonus_totale += clean_sheet * bi.imbattibilita_portiere

        # Normalizza: media per partita
        fv += bonus_totale / presenze_voto

    return round(fv, 3)


def calcola_fantavoto_standard(
    voto: float,
    gol: int,
    assist_tot: int,
    ammonizioni: int,
    espulsioni: int,
    autogol: int | None,
    rig_segnati: int,
    rig_sbagliati: int | None,
    rig_parati: int,
    gol_subiti: int,
    clean_sheet: int | None,
    presenze_voto: int = 0,
) -> float:
    """Calcola fantavoto MEDIO con le regole STANDARD Fantacalcio.it.

    Usato come sanity check: comparare con media_fv_fonte dalla fonte.
    Bonus standard:
    - Gol: +3
    - Assist: +1.0
    - Ammonizione: -0.5
    - Espulsione: -1.0
    - Autogol: -2.0
    - Rigore segnato: +3
    - Rigore sbagliato: -3
    - Rigore parato: +3
    - Gol subito (portiere): -1.0
    - Imbattibilità: +1.0

    Bonus totali sono divisi per presenze_voto per ottenere MEDIA per partita.
    """
    fv = voto

    if presenze_voto > 0:
        # Calcola bonus totali, poi normalizza per presenze
        bonus_totale = 0.0
        bonus_totale += gol * 3.0
        bonus_totale += assist_tot * 1.0
        bonus_totale += ammonizioni * (-0.5)
        bonus_totale += espulsioni * (-1.0)

        if autogol is not None:
            bonus_totale += autogol * (-2.0)

        bonus_totale += rig_segnati * 3.0

        if rig_sbagliati is not None:
            bonus_totale += rig_sbagliati * (-3.0)

        bonus_totale += rig_parati * 3.0
        bonus_totale += gol_subiti * (-1.0)

        if clean_sheet is not None:
            bonus_totale += clean_sheet * 1.0

        # Media per partita
        fv += bonus_totale / presenze_voto

    return round(fv, 3)
