"""Test M2+M3: storico aggregato, ID-based join, new player creation, ricalcolo fantavoto."""

import tempfile
from pathlib import Path

import duckdb
import pytest

from fanta.domain.models import StoricoRecord
from fanta.entity.uid import generate_player_uid
from fanta.pipeline.schema import create_canonical_schema
from fanta.rules.fantavoto import calcola_fantavoto, calcola_fantavoto_standard
from fanta.rules.loader import load_rules
from fanta.sources.storico_aggregato import StoricoAdapter


def test_storico_record_valid():
    """StoricoRecord con valori validi."""
    record = StoricoRecord(
        nome="Lautaro Martinez",
        squadra="Inter",
        stagione="2024-25",
        presenze_voto=20,
        media_voto=7.5,
        media_fv_fonte=8.2,
        gol=15,
        assist_tot=5,
    )
    assert record.nome == "Lautaro Martinez"
    assert record.gol == 15


def test_calcola_fantavoto_base():
    """Ricalcolo fantavoto base: voto 6 + gol (+3) = 9 (media per partita)."""
    rules = load_rules(Path(__file__).parent.parent / "config" / "rules_lega.yaml")

    fv = calcola_fantavoto(
        voto=6.0,
        gol=1,
        assist_tot=0,
        ammonizioni=0,
        espulsioni=0,
        autogol=None,
        rig_segnati=0,
        rig_sbagliati=None,
        rig_parati=0,
        gol_subiti=0,
        clean_sheet=None,
        regole=rules,
        presenze_voto=1,
    )

    assert fv == 9.0


def test_calcola_fantavoto_penalita():
    """Fantavoto con penalità: voto 6.5 + ammonizione (-0.5) = 6.0 (media per partita)."""
    rules = load_rules(Path(__file__).parent.parent / "config" / "rules_lega.yaml")

    fv = calcola_fantavoto(
        voto=6.5,
        gol=0,
        assist_tot=0,
        ammonizioni=1,
        espulsioni=0,
        autogol=None,
        rig_segnati=0,
        rig_sbagliati=None,
        rig_parati=0,
        gol_subiti=0,
        clean_sheet=None,
        regole=rules,
        presenze_voto=1,
    )

    assert fv == 6.0


def test_calcola_fantavoto_standard_equivalence():
    """Fantavoto standard equivale a quella con regole standard (media per partita)."""
    fv_standard = calcola_fantavoto_standard(
        voto=7.0,
        gol=2,
        assist_tot=1,
        ammonizioni=1,
        espulsioni=0,
        autogol=None,
        rig_segnati=0,
        rig_sbagliati=None,
        rig_parati=0,
        gol_subiti=0,
        clean_sheet=None,
        presenze_voto=1,
    )

    # 7.0 + (2*3 + 1*1 + 1*(-0.5)) / 1 = 7.0 + 6.5 = 13.5
    assert fv_standard == 13.5


def test_generate_player_uid_deterministic():
    """generate_player_uid ritorna lo stesso UID per stesso input."""
    uid1 = generate_player_uid("Lautaro Martinez", "Inter", "A", None)
    uid2 = generate_player_uid("Lautaro Martinez", "Inter", "A", None)
    assert uid1 == uid2
    assert len(uid1) == 16  # SHA1 troncato a 16 char


def test_generate_player_uid_different_squads():
    """generate_player_uid IDENTICO per stesso giocatore in squadre diverse (squadra ignorata)."""
    uid_inter = generate_player_uid("Lautaro Martinez", "Inter", "A", None)
    uid_juventus = generate_player_uid("Lautaro Martinez", "Juventus", "A", None)
    assert uid_inter == uid_juventus  # Stesso giocatore → stesso UID, indipendentemente da squadra


def test_xref_alias_table():
    """Tabella xref_alias esiste e supporta insert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        create_canonical_schema(db_path)

        db = duckdb.connect(str(db_path))

        # Insert manuale
        db.execute(
            """
        INSERT INTO xref_alias (source, source_key, player_uid, confidence, manual)
        VALUES (?, ?, ?, ?, ?)
        """,
            ["storico_aggregato", "lautaro_martinez_inter_2024", "uid_123", 95.0, False],
        )

        # Query
        result = db.execute(
            "SELECT player_uid, confidence FROM xref_alias WHERE source = 'storico_aggregato'"
        ).fetchall()

        assert len(result) == 1
        assert result[0][0] == "uid_123"
        assert result[0][1] == 95.0

        db.close()


def test_fact_season_agg_schema():
    """Tabella fact_season_agg esiste con i campi corretti."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.duckdb"
        create_canonical_schema(db_path)

        db = duckdb.connect(str(db_path))

        # Insert record
        db.execute(
            """
        INSERT INTO fact_season_agg
        (player_uid, stagione, presenze_voto, presenze_fv, media_voto, media_fv_fonte,
         media_fv_lega, gol, assist_tot, ammonizioni, espulsioni, rig_segnati, rig_parati,
         gol_subiti)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                "uid_123",
                "2024-25",
                20,
                20,
                7.5,
                8.0,
                8.2,
                10,
                5,
                2,
                0,
                0,
                0,
                2,
            ],
        )

        # Query
        result = db.execute(
            "SELECT media_voto, media_fv_fonte, gol FROM fact_season_agg WHERE player_uid = 'uid_123'"
        ).fetchall()

        assert len(result) == 1
        assert result[0][0] == 7.5
        assert result[0][1] == 8.0
        assert result[0][2] == 10

        db.close()


def test_parse_storico_xlsx_fixture():
    """Test parsing of real XLSX file."""
    fixture_path = Path("data/raw/storico_aggregato/2024-25/stats.xlsx")
    if not fixture_path.exists():
        pytest.skip("XLSX fixture not found")

    adapter = StoricoAdapter()
    records = adapter.parse(fixture_path, "2024-25")

    assert len(records) > 0
    assert 200 <= len(records) <= 700
    assert all(isinstance(r, dict) for r in records)
    assert all("nome" in r for r in records)
    assert all("squadra" in r for r in records)
    assert all("media_voto" in r for r in records)
    assert all("media_fv_fonte" in r for r in records)
    assert all("gol" in r for r in records)
