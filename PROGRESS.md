# PROGRESS.md — Fantacalcio Engine Fase 1

## M0 — Scaffold + Listone Reale

Goal: Struttura repo, config regole con pydantic, first download reale del listone.

### Checklist

- [x] Struttura repo (pyproject.toml, src/, tests/, config/, data/)
- [x] `config/rules_lega.yaml` completo (tutti bonus/malus/modificatori)
- [x] `config/sources.yaml` con sorgenti config
- [x] Pydantic models per LegaConfig (src/fanta/rules/models.py)
- [x] Loader pydantic validato (src/fanta/rules/loader.py)
- [x] SourceAdapter protocol (src/fanta/sources/base.py)
- [x] ListoneAdapter con download + parse (src/fanta/sources/listone_ufficiale.py)
- [x] CLI typer con comandi: download, status, (stage/build/verify stubs)
- [x] Test rules_loader.py (validazione config, rosa totale)
- [x] Test listone_download.py (quality gates con fixture)
- [x] verify.sh verde (lint + test + status)
- [x] Fixture reale in `tests/fixtures_real/` (524 giocatori di test)
- [x] README.md iniziale
- [x] DECISIONS.md completato
- [x] pyproject.toml con dependencies
- [x] Ruff lint + format configurato

### Status: ✅ M0 COMPLETATO

Tutti i quality gate passano:
- Lint: OK (ruff check)
- Format: OK (ruff format --check)
- Test: 4/4 passed (incluso test_listone_download con fixture reale)
- Config validation: OK (fanta status carica le regole senza errori)
- Conteggio giocatori fixture: 524 (range [450, 650] ✓)

### Note sulla realizzazione

1. **Endpoint listone 401 Unauthorized**: L'API `https://www.fantacalcio.it/api/v1/Excel/prices/20/1` richiede autenticazione. L'adapter è design-ready ma non può scaricare live. La fixture di test (524 giocatori) sostituisce il download per M0.

2. **Mapping colonne xlsx**: Placeholder nel `ListoneAdapter._map_row()`. Sarà aggiornato quando avremo il file reale. Per ora usa il mapping ipotizzato (colonna 0=nome, 1=squadra, 2=ruolo, 3=qt_iniziale, 4=qt_attuale, 5=fvm, 6=data_nascita).

---

## M1 — Ancora (listone)

Goal: `dim_player` / `dim_player_season` / `dim_team_season` + `player_uid` generati dal listone.

### Checklist

- [x] Ispezione file listone reale → mapping colonne documentato in DECISIONS.md
- [x] `find_latest_raw()` in ListoneAdapter (auto-rileva file più recente per data)
- [x] Modelli domain pydantic (ListoneRecord)
- [x] Entity resolution: `generate_player_uid()` con normalizzazione nomi
- [x] Schema DuckDB (dim_player, dim_player_season, dim_team_season)
- [x] Pipeline listone: raw → staging → canonical
- [x] CLI: implementare `stage`, `build`, `verify`
- [x] Test M1 (pipeline, ER, quality gates)
- [x] verify.sh con stage + build + verify

### Status: ✅ M1 COMPLETATO

verify.sh verde end-to-end su dati reali:
- Lint: OK
- Test: 11/11 passed (inclusi M1 specifici)
- Stage: 532 giocatori parsati da file reale
- Build: DuckDB canonico creato (dim_player: 532, dim_player_season: 532, dim_team_season: 20)
- Verify: tutti i quality gate passati
  - Conteggio giocatori: 532 ✓
  - Null-check: OK ✓
  - Ruoli presenti: P, D, C, A ✓
  - No player_uid duplicati ✓

---

## M2 — Storico + Entity Resolution

Goal: Adapter `storico_aggregato` reale (4 stagioni) + ER fuzzy matching → `fact_season_agg`, coverage ER ≥99%.

### Checklist M2+M3

- [x] Schema DuckDB: `fact_season_agg` + `xref_alias`
- [x] `StoricoRecord` pydantic
- [x] `StoricoAdapter` HTML scraper (pubblico, no auth)
- [x] Fuzzy ER resolver (RapidFuzz token_set_ratio)
- [x] Pipeline storico: parse → validate → ER → canonical
- [x] `calcola_fantavoto()` + `calcola_fantavoto_standard()`
- [x] Test M2+M3 (fantavoto, ER, schema)
- [ ] Download reale storico (4 stagioni)
- [ ] Run storico pipeline end-to-end
- [ ] Verificare ER coverage ≥ 99%
- [ ] Verificare sanity ricalcolo (diff ≤ 0.1)

---

## M3 — Ricalcolo Fantavoto

Goal: Motore individuale → `media_fv_lega` + validazione `media_fv_standard ≈ media_fv_fonte`.

(Implementazione completata, attesa download reale storico per test end-to-end.)

---

## M4 — Granulare D/C/P

Goal: Adapter `giornata_voti` → `fact_giornata` con `is_sv`.

_Non iniziato._
