# Fantacalcio Engine — Fase 1: Ingestion & Canonical Data Layer

Personal league data engine per fantacalcio classico. Costruisce un data layer canonico, storicizzato e interrogabile.

## Stato

**Milestone:** M0 (Scaffold + Listone)

Vedi `PROGRESS.md` e `DECISIONS.md` per dettagli.

## Quickstart

### Setup

```bash
cd /Volumes/macOSdev/playground/fanta
uv sync
```

### Verificare il sistema

```bash
bash verify.sh
```

Questo esegue:
- Lint e format check (ruff)
- Unit test (pytest)
- Validazione config (fanta status)

### CLI Commands

```bash
# Mostra stato: regole caricate, file raw presenti
uv run fanta status

# Scarica il listone (quando endpoint è disponibile)
uv run fanta download --source listone_ufficiale [--force]

# Comandi stub (M1+)
uv run fanta stage   # Not implemented
uv run fanta build   # Not implemented
uv run fanta verify  # Not implemented
```

## Struttura

```
.
├── config/
│   ├── rules_lega.yaml       # Regolamento: single source of truth
│   └── sources.yaml          # Config sorgenti dati
├── data/
│   ├── raw/                  # Raw immutabile (scaricati, non toccati)
│   └── canonical/            # Output canonico (DuckDB)
├── src/fanta/
│   ├── domain/               # Modelli puri (no I/O)
│   ├── rules/                # Config loader + motore ricalcolo
│   ├── sources/              # Adapter per sorgenti dati
│   ├── pipeline/             # raw → staging → canonical
│   ├── entity/               # Entity resolution
│   ├── quality/              # Quality gates
│   └── cli.py                # Typer CLI
├── tests/
│   ├── fixtures_real/        # Snapshot reali committati
│   └── test_*.py             # Unit tests
├── DECISIONS.md              # Scelte architetturali
├── PROGRESS.md               # Stato milestone
└── verify.sh                 # Gate di verifica end-to-end
```

## Design

### Ports & Adapters
Ogni sorgente dati (listone, storico, voti giornalieri) implementa `SourceAdapter`:
- `download() -> Path`: scarica in `data/raw/<source>/<YYYYMMDD>/`
- `parse(raw_path) -> list[dict]`: parsa il raw

Il cambiare fonte NON tocca pipeline o canonical.

### Raw immutabile
I file scaricati rimangono esattamente come ottenuti. Se miglioriamo il parsing, riprocessiamo dai raw committati **senza riscaricamento** → determinismo + riproducibilità.

### Dati reali, non mock
Test girano su **snapshot reali** committati in `tests/fixtures_real/`. Offline, deterministico, evita deviazione test/prod.

## Sorgenti dati

### Listone Ufficiale
- **Fonte:** Fantacalcio.it
- **Formato:** XLSX
- **Status:** ⚠️ Endpoint richiede autenticazione. [Vedi DECISIONS.md]

### Storico Aggregato
- **Fonte:** Fantacalcio.it (4 stagioni)
- **Cosa:** Voto + fantavoto separati + componenti grezzi (gol, assist, cartellini, rigori, clean sheet)
- **Status:** M1+

### Voti Giornada (D/C/P)
- **Fonte:** PianetaFanta
- **Tipo:** Web scraping
- **Archivio:** 2002-2025
- **Status:** M4

## Regolamento

Tutto il regolamento è in `config/rules_lega.yaml`:

```yaml
lega:
  partecipanti: 10
  budget: 500
  rosa: { P: 3, D: 8, C: 8, A: 6 }  # 25 titolari

bonus_individuali:
  gol_segnato: +3
  assist:
    classic: +1.0
    soft: +0.5
    gold: +1.5
  # ... cartellini, rigori, clean sheet ...

modificatori_collettivi:  # Calcolati a formazione (M2+)
  difesa: { ... }
  capitano: { ... }
  fairplay: { ... }

modificatori_scontro:     # Dipendono dall'avversario (M2+)
  centrocampo: { ... }
  casalinga: { ... }
```

**Single source of truth:** codice legge da qui, no hardcoded values.

## Tests

```bash
# Esegui i test
uv run pytest tests/ -v

# Con coverage
uv run pytest tests/ --cov=src/fanta
```

Test attuali:
- `test_rules_loader.py`: validazione pydantic config
- `test_listone_download.py`: parsing fixture + quality gates (skip se fixture non esiste)

## Sviluppo

```bash
# Format e lint
uv run ruff format src/ tests/
uv run ruff check src/ tests/

# Type check
uv run pyright src/  # (opzionale, non in verify.sh)
```

## Milestone

- **M0** (current): Scaffold + config + listone adapter → `verify.sh` verde
- **M1**: Listone → `dim_player` / `dim_player_season` + `player_uid`
- **M2**: Storico + ER → `fact_season_agg`, coverage ER ≥99%
- **M3**: Ricalcolo fantavoto individuale → `media_fv_lega`
- **M4**: Voti giornalieri → `fact_giornata` + distribuzione D/C/P

Ogni milestone chiude con `verify.sh` verde su **dati reali**.

## Note

- **No ORM, no Postgres, no Docker**: il dataset è tiny (~10⁵ righe). DuckDB in-process, file-based.
- **No mock in tests**: snapshot reali committati, offline deterministico.
- **Niente scope-creep**: modificatori collettivi, asta, xG/xA, UI → fasi successive.

---

**Master spec:** [`SPEC-FANTA.md`](./SPEC-FANTA.md)
# fanta
