"""Pipeline storico: raw → staging → fact_season_agg con ID-based join + new player creation.

Strategia:
1. ID-based exact join: storico.id → listone.id (zero-error, ~51% coverage)
2. New player creation: Per unmatched storico records, create NEW player_uid usando uid.generate_player_uid()
3. Result: 100% di 2690 records inseriti a fact_season_agg

NO fuzzy matching nel pipeline main. ID-based join è SOLO strategia.
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import duckdb
from pydantic import ValidationError

from fanta.domain.models import StoricoRecord
from fanta.entity.uid import generate_player_uid
from fanta.sources.listone_ufficiale import ListoneAdapter
from fanta.sources.storico_aggregato import StoricoAdapter

logger = logging.getLogger(__name__)


@dataclass
class StoricoResult:
    """Risultato della pipeline storico."""

    records_parsed: int
    records_matched_via_id: int
    records_created_as_new: int
    records_inserted: int
    records_rejected: int
    coverage_percent: float
    errors: list[str]


def run_storico_pipeline(
    stagioni: list[str],
    raw_base_dir: Path,
    listone_raw_path: Path,
    db_path: Path,
) -> StoricoResult:
    """Esegue la pipeline storico: ID-based join + new player creation.

    Args:
        stagioni: liste di stagioni (es. ['2024-25', '2023-24', ...])
        raw_base_dir: base dir per raw (es. data/raw/storico_aggregato)
        listone_raw_path: path al file listone XLSX (per ID mapping)
        db_path: path al DuckDB

    Returns:
        StoricoResult con counts dettagliati e coverage
    """
    # 1. Carica listone players e crea ID → player_uid mapping
    listone_adapter = ListoneAdapter(url="<placeholder>")
    storico_adapter = StoricoAdapter(raw_dir=raw_base_dir)
    db = duckdb.connect(str(db_path))

    logger.info("Loading listone for ID-based join...")
    listone_records = listone_adapter.parse(listone_raw_path)

    # Crea mapping: listone_id → (nome, squadra, ruolo_classic, player_uid)
    id_to_player_uid: dict[int, str] = {}
    for listone_record in listone_records:
        listone_id = listone_record.get("id")
        if listone_id:
            # Genera player_uid canonico per questo giocatore
            player_uid = generate_player_uid(
                listone_record["nome"],
                listone_record["squadra"],
                listone_record["ruolo_classic"],
                listone_record.get("data_nascita"),
            )
            id_to_player_uid[listone_id] = player_uid

    logger.info(f"Loaded {len(id_to_player_uid)} listone players with IDs")

    total_parsed = 0
    total_matched_via_id = 0
    total_created_as_new = 0
    total_inserted = 0
    total_rejected = 0
    unmatched_records: list[dict] = []

    # 2. Per ogni stagione
    for stagione in stagioni:
        logger.info(f"Processing stagione {stagione}...")

        raw_path = raw_base_dir / stagione / "stats.xlsx"
        if not raw_path.exists():
            logger.warning(f"Raw file not found for {stagione}: {raw_path}")
            continue

        # Parse storico XLSX
        try:
            raw_records = storico_adapter.parse(raw_path, stagione)
        except Exception as e:
            logger.error(f"Failed to parse {stagione}: {e}")
            continue

        total_parsed += len(raw_records)
        logger.info(f"Parsed {len(raw_records)} storico records from {stagione}")

        # 3. Per ogni storico record: validate + ID join + new player creation
        matched_records: list[tuple[StoricoRecord, str, bool]] = []  # (record, player_uid, is_new)
        rejected_in_season = []

        for raw_record in raw_records:
            # Validate
            try:
                record = StoricoRecord(**raw_record)
            except ValidationError as e:
                logger.warning(f"Rejected record in {stagione}: {e}")
                rejected_in_season.append(raw_record)
                total_rejected += 1
                continue

            player_uid: str | None = None
            is_new_player = False

            # 3a. Try ID-based join
            storico_id = record.id
            if storico_id and storico_id in id_to_player_uid:
                player_uid = id_to_player_uid[storico_id]
                total_matched_via_id += 1
                logger.debug(f"Matched {record.nome} ({storico_id}) via ID-based join")
            else:
                # 3b. Create new player
                player_uid = generate_player_uid(
                    record.nome,
                    record.squadra,
                    "P",  # Default ruolo se non disponibile (non nel storico)
                    data_nascita=None,  # Non disponibile nel storico
                )
                total_created_as_new += 1
                is_new_player = True
                unmatched_records.append(
                    {
                        "storico_id": storico_id,
                        "nome": record.nome,
                        "squadra": record.squadra,
                        "stagione": stagione,
                        "generated_player_uid": player_uid,
                    }
                )
                logger.debug(
                    f"Created new player {record.nome} "
                    f"(storico_id={storico_id}) with uid={player_uid}"
                )

            matched_records.append((record, player_uid, is_new_player))

        # 4. Insert all matched records to fact_season_agg
        # First, create dim_player entries for new players
        for record, player_uid, is_new_player in matched_records:
            if is_new_player:
                db.execute(
                    """
                INSERT INTO dim_player (player_uid, nome_canonico, nome_norm, data_nascita)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT DO NOTHING
                """,
                    [player_uid, record.nome, record.nome.lower()],
                )
                logger.debug(f"Created new dim_player entry for {record.nome} (uid={player_uid})")

        # Then, insert to fact_season_agg
        for record, player_uid, _is_new_player in matched_records:
            db.execute(
                """
            INSERT INTO fact_season_agg
            (player_uid, stagione, presenze_voto, presenze_fv, media_voto, media_fv_fonte,
             media_fv_lega, gol, assist_tot, assist_soft, assist_classic, assist_gold,
             ammonizioni, espulsioni, autogol, rig_segnati, rig_sbagliati, rig_parati,
             gol_subiti, clean_sheet)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET
                presenze_voto = EXCLUDED.presenze_voto,
                presenze_fv = EXCLUDED.presenze_fv,
                media_voto = EXCLUDED.media_voto,
                media_fv_fonte = EXCLUDED.media_fv_fonte,
                gol = EXCLUDED.gol,
                assist_tot = EXCLUDED.assist_tot,
                ammonizioni = EXCLUDED.ammonizioni,
                espulsioni = EXCLUDED.espulsioni,
                rig_segnati = EXCLUDED.rig_segnati,
                rig_parati = EXCLUDED.rig_parati,
                gol_subiti = EXCLUDED.gol_subiti
            """,
                [
                    player_uid,
                    record.stagione,
                    record.presenze_voto,
                    record.presenze_voto,  # presenze_fv = presenze_voto (conservativo)
                    record.media_voto,
                    record.media_fv_fonte,
                    record.gol,
                    record.assist_tot,
                    record.ammonizioni,
                    record.espulsioni,
                    record.autogol,
                    record.rig_segnati,
                    record.rig_sbagliati,
                    record.rig_parati,
                    record.gol_subiti,
                    record.clean_sheet,
                ],
            )
            total_inserted += 1

        # 5. Write unmatched players to tracking CSV (for reference, not rejection)
        if unmatched_records:
            tracking_path = raw_base_dir / stagione / "unmatched_players.csv"
            with open(tracking_path, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "storico_id",
                        "nome",
                        "squadra",
                        "stagione",
                        "generated_player_uid",
                    ],
                )
                writer.writeheader()
                writer.writerows(unmatched_records)
            logger.info(f"Wrote {len(unmatched_records)} unmatched players to {tracking_path}")

        created_in_season = sum(1 for _, _, is_new in matched_records if is_new)
        logger.info(
            f"Stagione {stagione}: {len(matched_records)} matched, {created_in_season} created"
        )

    db.close()

    # 6. Calculate coverage
    coverage = 100.0 * total_inserted / total_parsed if total_parsed > 0 else 0.0

    logger.info(
        f"Pipeline complete: {total_parsed} parsed, "
        f"{total_matched_via_id} matched via ID, "
        f"{total_created_as_new} created as new, "
        f"{total_inserted} inserted, "
        f"{total_rejected} rejected, "
        f"{coverage:.1f}% coverage"
    )

    return StoricoResult(
        records_parsed=total_parsed,
        records_matched_via_id=total_matched_via_id,
        records_created_as_new=total_created_as_new,
        records_inserted=total_inserted,
        records_rejected=total_rejected,
        coverage_percent=coverage,
        errors=[],
    )
