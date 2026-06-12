"""Pipeline listone: raw → staging → canonical."""

import logging
from dataclasses import dataclass
from pathlib import Path

import duckdb
from pydantic import ValidationError

from fanta.domain.models import ListoneRecord
from fanta.entity.uid import generate_player_uid
from fanta.sources.listone_ufficiale import ListoneAdapter

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Risultato dell'esecuzione della pipeline."""

    players_inserted: int
    players_updated: int
    records_rejected: int
    errors: list[str]


def run_listone_pipeline(
    raw_path: Path,
    db_path: Path,
    stagione: str,
) -> PipelineResult:
    """Esegue la pipeline completa: raw → staging → canonical.

    Args:
        raw_path: path al file xlsx
        db_path: path al DuckDB
        stagione: string format '2025-26'

    Returns:
        PipelineResult con counts
    """
    adapter = ListoneAdapter(url="<placeholder>")

    # 1. Parse raw
    raw_records = adapter.parse(raw_path)
    logger.info(f"Parsed {len(raw_records)} raw records")

    # 2. Validate & collect rejects
    validated_records: list[tuple[ListoneRecord, str]] = []
    rejected_records: list[dict] = []

    for raw_record in raw_records:
        try:
            record = ListoneRecord(**raw_record)
            uid = generate_player_uid(
                record.nome,
                record.squadra,
                record.ruolo_classic,
                record.data_nascita,
            )
            validated_records.append((record, uid))
        except ValidationError as e:
            logger.warning(f"Rejected record: {raw_record} - {e}")
            rejected_records.append(raw_record)

    logger.info(f"Validated {len(validated_records)}, rejected {len(rejected_records)}")

    # 3. Write rejects to log
    if rejected_records:
        reject_log = raw_path.parent / "reject.log"
        with open(reject_log, "w") as f:
            for rec in rejected_records:
                f.write(f"{rec}\n")
        logger.warning(f"Rejects logged to {reject_log}")

    # 4. Upsert to canonical
    db = duckdb.connect(str(db_path))

    players_inserted = 0

    # Upsert dim_player
    for record, uid in validated_records:
        db.execute(
            """
        INSERT INTO dim_player (player_uid, nome_canonico, nome_norm, data_nascita)
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO UPDATE SET
            data_nascita = COALESCE(EXCLUDED.data_nascita, dim_player.data_nascita)
        """,
            [uid, record.nome, record.nome.lower(), record.data_nascita],
        )
        players_inserted += 1

    # Upsert dim_player_season
    for record, uid in validated_records:
        db.execute(
            """
        INSERT INTO dim_player_season
        (player_uid, stagione, squadra, ruolo_classic, qt_iniziale, qt_attuale, fvm)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT DO UPDATE SET
            squadra = EXCLUDED.squadra,
            ruolo_classic = EXCLUDED.ruolo_classic,
            qt_iniziale = EXCLUDED.qt_iniziale,
            qt_attuale = EXCLUDED.qt_attuale,
            fvm = EXCLUDED.fvm
        """,
            [
                uid,
                stagione,
                record.squadra,
                record.ruolo_classic,
                record.qt_iniziale,
                record.qt_attuale,
                record.fvm,
            ],
        )

    # Upsert dim_team_season (squadre distinte)
    squadre = {rec.squadra for rec, _ in validated_records}
    for squadra in squadre:
        db.execute(
            """
        INSERT INTO dim_team_season (squadra, stagione, neopromossa, allenatore)
        VALUES (?, ?, NULL, NULL)
        ON CONFLICT DO UPDATE SET
            neopromossa = COALESCE(EXCLUDED.neopromossa, dim_team_season.neopromossa),
            allenatore = COALESCE(EXCLUDED.allenatore, dim_team_season.allenatore)
        """,
            [squadra, stagione],
        )

    db.close()

    return PipelineResult(
        players_inserted=players_inserted,
        players_updated=0,
        records_rejected=len(rejected_records),
        errors=[],
    )
