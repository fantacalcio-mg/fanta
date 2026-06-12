from pathlib import Path

import pytest

from fanta.rules import load_rules


@pytest.fixture
def rules_config_path():
    """Path al config rules_lega.yaml."""
    return Path(__file__).parent.parent / "config" / "rules_lega.yaml"


def test_load_rules_valid(rules_config_path):
    """Carica il config valido senza errori."""
    rules = load_rules(rules_config_path)
    assert rules.lega.partecipanti == 10
    assert rules.lega.budget == 500
    assert rules.lega.rosa.P == 3
    assert rules.lega.rosa.D == 8
    assert rules.lega.rosa.C == 8
    assert rules.lega.rosa.A == 6


def test_load_rules_invalid_path():
    """Fallisce se il file non esiste."""
    with pytest.raises(FileNotFoundError):
        load_rules(Path("/nonexistent/path/rules.yaml"))


def test_load_rules_rosa_validation(tmp_path):
    """Valida che rosa_totale sia esattamente 25."""
    invalid_config = tmp_path / "invalid_rules.yaml"
    invalid_config.write_text("""
lega:
  partecipanti: 10
  budget: 500
  base_asta: 1
  rosa:
    P: 3
    D: 8
    C: 8
    A: 5  # INVALIDO: totale 24 invece di 25
  panchina_ordinata:
    P: 1
    D: 2
    C: 2
    A: 2
  sostituzioni_max: 5
  giornate_lega: 33
  ultimo_girone_campo_neutro: true

bonus_individuali:
  scope: individual
  gol_segnato: 3
  assist:
    tiers:
      soft: 0.5
      classic: 1.0
      gold: 1.5
    fallback_se_tier_non_disponibile: 1.0
  ammonizione: -0.5
  espulsione: -1.0
  autogol: -2.0
  rigore_segnato: 3.0
  rigore_sbagliato: -3.0
  rigore_parato: 3.0
  gol_subito_portiere: -1.0
  imbattibilita_portiere: 1.0

modificatori_collettivi:
  scope: collective
  difesa:
    base: VOTO
    difesa_minima: 4
    migliori_n: 4
    soglie:
      "6.00": 0.5
      "6.25": 1.0
      "6.50": 1.5
    step:
      delta_soglia: 0.25
      delta_bonus: 0.5
  capitano:
    base: VOTO
    riferimento: 6.0
    passo: 0.5
  fairplay:
    base: cartellini
    bonus: 1.0

modificatori_scontro:
  scope: matchup
  centrocampo:
    base: VOTO
    sempre_attivo: true
    somma_voti: true
    soglia_diff: 2.0
    passo_bonus: 1.0
    voto_giocatore_mancante: 5.0
  partita_casalinga:
    bonus_totale_voti: 2.0
  soglie_gol:
    base_punti: 66
    passo_punti: 6
    regola_sotto_60: true
""")

    with pytest.raises(ValueError, match="Rosa totale deve essere 25"):
        load_rules(invalid_config)
