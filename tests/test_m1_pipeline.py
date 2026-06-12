"""Test per M1: pipeline listone → canonical."""

import tempfile
from pathlib import Path

import duckdb
import pytest

from fanta.entity.uid import generate_player_uid, normalize_name
from fanta.pipeline.listone import run_listone_pipeline
from fanta.pipeline.schema import create_canonical_schema
from fanta.sources.listone_ufficiale import ListoneAdapter


@pytest.fixture
def fixture_listone():
    """Path al fixture listone reale."""
    return Path(__file__).parent / "fixtures_real" / "listone_ufficiale" / "quotazioni.xlsx"


@pytest.fixture
def tmp_db():
    """Temporary DuckDB per i test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        create_canonical_schema(db_path)
        yield db_path


def test_normalize_name():
    """Verifica normalizzazione nomi."""
    assert normalize_name("Nicolò Barella") == "barella nicolo"
    assert normalize_name("De Rossi Andrea") == "andrea de rossi"
    assert normalize_name("  Gianluigi  Buffon  ") == "buffon gianluigi"


def test_player_uid_stable():
    """Player uid deterministic: stesso input → stesso output."""
    uid1 = generate_player_uid("Nicolò Barella", "Inter", "C", None)
    uid2 = generate_player_uid("Nicolo Barella", "Inter", "C", None)

    assert uid1 == uid2, "Normalizzazione non deterministico"


def test_player_uid_differenti():
    """Player uid identici per stesso giocatore (squadra ignorata), diversi per nomi diversi."""
    uid1 = generate_player_uid("Nicolò Barella", "Inter", "C", None)
    uid2 = generate_player_uid(
        "Nicolò Barella", "Milan", "C", None
    )  # squadra diversa, STESSO giocatore
    uid3 = generate_player_uid("Lautaro Martinez", "Inter", "A", None)  # nome diverso

    assert uid1 == uid2  # Stesso giocatore → stesso UID, indipendentemente da squadra
    assert uid1 != uid3  # Nomi diversi → UID diversi


def test_parse_fixture_listone(fixture_listone):
    """Parsa il fixture reale e asserisce conteggi."""
    if not fixture_listone.exists():
        pytest.skip(f"Fixture non disponibile: {fixture_listone}")

    adapter = ListoneAdapter(url="<placeholder>")
    records = adapter.parse(fixture_listone)

    assert len(records) > 0, "Nessun record parsato"
    assert all("nome" in r for r in records)
    assert all("squadra" in r for r in records)
    assert all("ruolo_classic" in r for r in records)


def test_find_latest_raw(tmp_path):
    """find_latest_raw() trova il file più recente per data."""
    raw_dir = tmp_path / "raw" / "listone_ufficiale"

    # Crea struttura con date diverse
    (raw_dir / "20260601").mkdir(parents=True, exist_ok=True)
    (raw_dir / "20260601" / "quotazioni.xlsx").touch()

    (raw_dir / "20260612").mkdir(parents=True, exist_ok=True)
    (raw_dir / "20260612" / "quotazioni.xlsx").touch()

    adapter = ListoneAdapter(url="<placeholder>", raw_dir=raw_dir)
    latest = adapter.find_latest_raw()

    assert latest is not None
    assert latest.name == "quotazioni.xlsx"
    assert latest.parent.name == "20260612"  # più recente


def test_pipeline_end_to_end(fixture_listone, tmp_db):
    """Pipeline completa: raw → staging → canonical."""
    if not fixture_listone.exists():
        pytest.skip(f"Fixture non disponibile: {fixture_listone}")

    result = run_listone_pipeline(
        raw_path=fixture_listone,
        db_path=tmp_db,
        stagione="2025-26",
    )

    assert result.players_inserted > 0, "Nessun giocatore inserito"
    assert result.records_rejected == 0, "Non dovrebbe avere rejects su fixture valido"

    # Verifica che i dati sono nel canonico
    db = duckdb.connect(str(tmp_db))

    # dim_player
    players = db.execute("SELECT COUNT(*) FROM dim_player").fetchall()
    assert players[0][0] > 0, "dim_player vuota"

    # dim_player_season
    seasons = db.execute(
        "SELECT COUNT(*) FROM dim_player_season WHERE stagione = '2025-26'"
    ).fetchall()
    assert seasons[0][0] > 0, "dim_player_season vuota"

    # dim_team_season
    teams = db.execute("SELECT COUNT(*) FROM dim_team_season WHERE stagione = '2025-26'").fetchall()
    assert teams[0][0] > 0, "dim_team_season vuota"

    db.close()


def test_quality_gates(fixture_listone, tmp_db):
    """Verifica quality gate M1."""
    if not fixture_listone.exists():
        pytest.skip(f"Fixture non disponibile: {fixture_listone}")

    run_listone_pipeline(
        raw_path=fixture_listone,
        db_path=tmp_db,
        stagione="2025-26",
    )

    db = duckdb.connect(str(tmp_db))

    # Gate 1: conteggio [450, 650]
    count = db.execute(
        "SELECT COUNT(*) FROM dim_player_season WHERE stagione = '2025-26'"
    ).fetchall()[0][0]
    assert 450 <= count <= 650, f"Conteggio {count} fuori range"

    # Gate 2: null-check
    nulls = db.execute(
        """
    SELECT COUNT(*) FROM dim_player_season
    WHERE stagione = '2025-26' AND (squadra IS NULL OR ruolo_classic IS NULL)
    """
    ).fetchall()[0][0]
    assert nulls == 0, f"{nulls} record con campi null"

    # Gate 3: ruoli distinti
    roles = db.execute(
        "SELECT DISTINCT ruolo_classic FROM dim_player_season WHERE stagione = '2025-26'"
    ).fetchall()
    assert len(roles) >= 3, f"Solo {len(roles)} ruoli distinti"

    db.close()
