import logging
from pathlib import Path

import duckdb
import typer
import yaml

from .pipeline.listone import run_listone_pipeline
from .pipeline.schema import create_canonical_schema
from .pipeline.storico import run_storico_pipeline
from .rules import load_rules
from .sources.listone_ufficiale import ListoneAdapter
from .sources.storico_aggregato import StoricoAdapter

app = typer.Typer(help="Fantacalcio Engine CLI")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_repo_root() -> Path:
    """Trova la root del repo cercando pyproject.toml."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Cannot find repo root (pyproject.toml not found)")


def get_config_dir() -> Path:
    """Ritorna il percorso alla directory config."""
    return get_repo_root() / "config"


def get_data_dir() -> Path:
    """Ritorna il percorso alla directory data."""
    return get_repo_root() / "data"


@app.command()
def download(
    source: str = typer.Option("listone_ufficiale", help="Fonte da scaricare"),
    force: bool = typer.Option(False, "--force", help="Forza il re-download"),
) -> None:
    """Scarica i raw da una sorgente."""
    config_dir = get_config_dir()
    data_dir = get_data_dir()

    if source == "listone_ufficiale":
        with open(config_dir / "sources.yaml") as f:
            sources_config = yaml.safe_load(f)
        listone_config = sources_config["sources"]["listone_ufficiale"]

        adapter = ListoneAdapter(
            url=listone_config["url"],
            raw_dir=data_dir / "raw" / "listone_ufficiale",
            user_agent=listone_config["user_agent"],
            timeout_seconds=listone_config["timeout_seconds"],
        )

        try:
            raw_path = adapter.download(force=force)
            typer.echo(f"✓ Listone scaricato: {raw_path}")
        except Exception as e:
            typer.echo(f"✗ Download fallito: {e}", err=True)
            raise typer.Exit(1) from e
    else:
        typer.echo(f"✗ Sorgente non riconosciuta: {source}", err=True)
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Mostra lo stato del sistema: regole caricate, sorgenti, file raw."""
    config_dir = get_config_dir()
    data_dir = get_data_dir()

    try:
        rules = load_rules(config_dir / "rules_lega.yaml")
        typer.echo("=== Regole Lega ===")
        typer.echo(f"Partecipanti: {rules.lega.partecipanti}")
        typer.echo(f"Budget: {rules.lega.budget}")
        typer.echo(
            f"Rosa: P={rules.lega.rosa.P} D={rules.lega.rosa.D} C={rules.lega.rosa.C} A={rules.lega.rosa.A}"
        )
        typer.echo(f"Giornate: {rules.lega.giornate_lega}")
        typer.echo("✓ Config valido")
    except Exception as e:
        typer.echo(f"✗ Errore caricamento config: {e}", err=True)
        raise typer.Exit(1) from e

    raw_dir = data_dir / "raw"
    if raw_dir.exists():
        raw_files = list(raw_dir.rglob("*.xlsx")) + list(raw_dir.rglob("*.csv"))
        typer.echo("\n=== Raw Files ===")
        if raw_files:
            for f in sorted(raw_files):
                typer.echo(f"  {f.relative_to(raw_dir)}")
        else:
            typer.echo("  (nessuno scaricato)")
    else:
        typer.echo("\n=== Raw Files ===")
        typer.echo("  (directory non esiste ancora)")


@app.command()
def stage(
    source: str = typer.Option("listone_ufficiale", help="Fonte da stageare"),
) -> None:
    """Stage: parsing e validazione raw."""
    data_dir = get_data_dir()

    if source == "listone_ufficiale":
        adapter = ListoneAdapter(url="<placeholder>")
        raw_path = adapter.find_latest_raw()

        if not raw_path:
            typer.echo("✗ Nessun file listone trovato in data/raw/", err=True)
            raise typer.Exit(1)

        typer.echo(f"Staging {raw_path}...")
        try:
            records = adapter.parse(raw_path)
            typer.echo(f"✓ Parsed {len(records)} records")
        except Exception as e:
            typer.echo(f"✗ Stage fallito: {e}", err=True)
            raise typer.Exit(1) from e

    elif source == "storico_aggregato":
        adapter = StoricoAdapter(raw_dir=data_dir / "raw" / "storico_aggregato")

        # Cerca tutte le stagioni in raw
        raw_base = data_dir / "raw" / "storico_aggregato"
        if not raw_base.exists():
            typer.echo("✗ Nessun file storico trovato in data/raw/storico_aggregato/", err=True)
            raise typer.Exit(1)

        stagioni = sorted(
            [d.name for d in raw_base.iterdir() if d.is_dir() and d.name.count("-") == 1]
        )
        if not stagioni:
            typer.echo("✗ Nessuna stagione trovata in data/raw/storico_aggregato/", err=True)
            raise typer.Exit(1)

        total_parsed = 0
        for stagione in stagioni:
            raw_path = raw_base / stagione / "stats.xlsx"
            if not raw_path.exists():
                continue

            try:
                records = adapter.parse(raw_path, stagione)
                total_parsed += len(records)
                typer.echo(f"  {stagione}: {len(records)} records")
            except Exception as e:
                typer.echo(f"✗ Stage {stagione} fallito: {e}", err=True)

        typer.echo(f"✓ Total parsed: {total_parsed} records")

    else:
        typer.echo(f"✗ Sorgente non riconosciuta: {source}", err=True)
        raise typer.Exit(1)


@app.command()
def build(
    source: str = typer.Option("listone_ufficiale", help="Fonte da buildare"),
    stagione: str = typer.Option("2025-26", help="Stagione (es. 2025-26)"),
) -> None:
    """Build: entity resolution + canonical DuckDB."""
    data_dir = get_data_dir()
    db_path = data_dir / "canonical" / "fanta.duckdb"

    db_path.parent.mkdir(parents=True, exist_ok=True)
    create_canonical_schema(db_path)

    if source == "listone_ufficiale":
        adapter = ListoneAdapter(url="<placeholder>")
        raw_path = adapter.find_latest_raw()

        if not raw_path:
            typer.echo("✗ Nessun file listone trovato in data/raw/", err=True)
            raise typer.Exit(1)

        typer.echo(f"Eseguendo pipeline listone {raw_path}...")
        try:
            result = run_listone_pipeline(raw_path, db_path, stagione)
            typer.echo(
                f"✓ Inserted: {result.players_inserted}, Rejected: {result.records_rejected}"
            )
        except Exception as e:
            typer.echo(f"✗ Build fallito: {e}", err=True)
            raise typer.Exit(1) from e

    elif source == "storico_aggregato":
        raw_base = data_dir / "raw" / "storico_aggregato"

        if not raw_base.exists():
            typer.echo("✗ Nessun file storico trovato in data/raw/storico_aggregato/", err=True)
            raise typer.Exit(1)

        # Raccogli tutte le stagioni
        stagioni = sorted(
            [d.name for d in raw_base.iterdir() if d.is_dir() and d.name.count("-") == 1]
        )

        if not stagioni:
            typer.echo("✗ Nessuna stagione trovata in data/raw/storico_aggregato/", err=True)
            raise typer.Exit(1)

        # Trova il file listone più recente
        adapter_listone = ListoneAdapter(url="<placeholder>")
        listone_raw_path = adapter_listone.find_latest_raw()

        if not listone_raw_path:
            typer.echo(
                "✗ Nessun file listone trovato per ID-based join. "
                "Esegui 'fanta download --source listone_ufficiale' prima.",
                err=True,
            )
            raise typer.Exit(1)

        typer.echo(f"Eseguendo pipeline storico per stagioni: {stagioni}...")
        typer.echo(f"Usando listone per ID mapping: {listone_raw_path}")
        try:
            result = run_storico_pipeline(
                stagioni=stagioni,
                raw_base_dir=raw_base,
                listone_raw_path=listone_raw_path,
                db_path=db_path,
            )
            typer.echo(
                f"✓ Parsed: {result.records_parsed}, "
                f"Matched via ID: {result.records_matched_via_id}, "
                f"Created as new: {result.records_created_as_new}, "
                f"Inserted: {result.records_inserted}, "
                f"Rejected: {result.records_rejected}, "
                f"Coverage: {result.coverage_percent:.1f}%"
            )

            if result.coverage_percent < 99.0:
                typer.echo(
                    f"⚠ Warning: Coverage {result.coverage_percent:.1f}% < 99%",
                    err=True,
                )
        except Exception as e:
            typer.echo(f"✗ Build fallito: {e}", err=True)
            raise typer.Exit(1) from e

    else:
        typer.echo(f"✗ Sorgente non riconosciuta: {source}", err=True)
        raise typer.Exit(1)


@app.command()
def verify(
    stagione: str = typer.Option("2025-26", help="Stagione da verificare"),
) -> None:
    """Verify: quality gates su canonical."""
    data_dir = get_data_dir()
    db_path = data_dir / "canonical" / "fanta.duckdb"

    if not db_path.exists():
        typer.echo("✗ DuckDB non trovato. Esegui 'fanta build' prima.", err=True)
        raise typer.Exit(1)

    db = duckdb.connect(str(db_path))

    # Gate 1: conteggio giocatori
    count_result = db.execute(
        "SELECT COUNT(*) FROM dim_player_season WHERE stagione = ?",
        [stagione],
    ).fetchall()
    n_players = count_result[0][0] if count_result else 0

    typer.echo(f"Giocatori stagione {stagione}: {n_players}")
    if not (450 <= n_players <= 650):
        typer.echo(
            f"✗ GATE FAILED: conteggio {n_players} fuori range [450,650]",
            err=True,
        )
        raise typer.Exit(1)

    # Gate 2: null-check
    null_result = db.execute(
        """
    SELECT COUNT(*) FROM dim_player_season
    WHERE stagione = ? AND (squadra IS NULL OR ruolo_classic IS NULL)
    """,
        [stagione],
    ).fetchall()
    n_nulls = null_result[0][0] if null_result else 0

    if n_nulls > 0:
        typer.echo(f"✗ GATE FAILED: {n_nulls} record con campi null", err=True)
        raise typer.Exit(1)

    # Gate 3: ruoli distinti
    roles_result = db.execute(
        "SELECT DISTINCT ruolo_classic FROM dim_player_season WHERE stagione = ?",
        [stagione],
    ).fetchall()
    roles = {r[0] for r in roles_result}

    if len(roles) < 3:
        typer.echo(f"✗ GATE FAILED: solo {len(roles)} ruoli distinti", err=True)
        raise typer.Exit(1)

    typer.echo(f"✓ Ruoli presenti: {sorted(roles)}")

    # Gate 4: no player_uid duplicati
    dup_result = db.execute(
        "SELECT COUNT(*) FROM dim_player GROUP BY player_uid HAVING COUNT(*) > 1"
    ).fetchall()

    if dup_result:
        typer.echo(f"✗ GATE FAILED: {len(dup_result)} player_uid duplicati", err=True)
        raise typer.Exit(1)

    db.close()

    typer.echo("✓ Tutti i quality gate PASSATI")
    raise typer.Exit(0)


if __name__ == "__main__":
    app()
