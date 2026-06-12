"""Schema DuckDB per il canonical data layer."""

from pathlib import Path

import duckdb


def create_canonical_schema(db_path: Path) -> None:
    """Crea le tabelle canoniche se non esistono (idempotente).

    Args:
        db_path: path al file DuckDB
    """
    db = duckdb.connect(str(db_path))

    db.execute(
        """
    CREATE TABLE IF NOT EXISTS dim_player (
        player_uid     VARCHAR PRIMARY KEY,
        nome_canonico  VARCHAR NOT NULL,
        nome_norm      VARCHAR NOT NULL,
        data_nascita   DATE
    )
    """
    )

    db.execute(
        """
    CREATE TABLE IF NOT EXISTS dim_player_season (
        player_uid     VARCHAR NOT NULL REFERENCES dim_player(player_uid),
        stagione       VARCHAR NOT NULL,
        squadra        VARCHAR NOT NULL,
        ruolo_classic  VARCHAR NOT NULL,
        qt_iniziale    INTEGER,
        qt_attuale     INTEGER,
        fvm            INTEGER,
        PRIMARY KEY (player_uid, stagione)
    )
    """
    )

    db.execute(
        """
    CREATE TABLE IF NOT EXISTS dim_team_season (
        squadra        VARCHAR NOT NULL,
        stagione       VARCHAR NOT NULL,
        neopromossa    BOOLEAN,
        allenatore     VARCHAR,
        PRIMARY KEY (squadra, stagione)
    )
    """
    )

    db.execute(
        """
    CREATE TABLE IF NOT EXISTS fact_season_agg (
        player_uid      VARCHAR NOT NULL,
        stagione        VARCHAR NOT NULL,
        presenze_voto   INTEGER,
        presenze_fv     INTEGER,
        media_voto      DOUBLE,
        media_fv_fonte  DOUBLE,
        media_fv_lega   DOUBLE,
        gol             INTEGER,
        assist_tot      INTEGER,
        assist_soft     INTEGER,
        assist_classic  INTEGER,
        assist_gold     INTEGER,
        ammonizioni     INTEGER,
        espulsioni      INTEGER,
        autogol         INTEGER,
        rig_segnati     INTEGER,
        rig_sbagliati   INTEGER,
        rig_parati      INTEGER,
        gol_subiti      INTEGER,
        clean_sheet     INTEGER,
        PRIMARY KEY (player_uid, stagione)
    )
    """
    )

    db.execute(
        """
    CREATE TABLE IF NOT EXISTS xref_alias (
        source       VARCHAR NOT NULL,
        source_key   VARCHAR NOT NULL,
        player_uid   VARCHAR NOT NULL,
        confidence   DOUBLE,
        manual       BOOLEAN DEFAULT FALSE,
        PRIMARY KEY (source, source_key)
    )
    """
    )

    db.close()
