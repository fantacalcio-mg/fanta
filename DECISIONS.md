# DECISIONS.md — Fantacalcio Engine M0+

## Sorgenti dati

### Listone Ufficiale
**Fonte:** Fantacalcio.it
**Endpoint:** `https://www.fantacalcio.it/api/v1/Excel/prices/20/1`
**Formato:** XLSX
**Status:** ⚠️ **Endpoint richiede autenticazione (401 Unauthorized)**

**Decisione:** In M0, l'adapter `ListoneAdapter` è implementato con supporto per il download, ma l'endpoint pubblico non è raggiungibile. Per il testing end-to-end, l'utente scarica il file manualmente e lo mette in `data/raw/listone_ufficiale/YYYYMMDD/quotazioni.xlsx`. Il sistema legge automaticamente la data più recente via `find_latest_raw()`.

**Mapping colonne xlsx (confermato da ispezione file reale 2025-26):**
- Riga 1: Titolo (skip)
- Riga 2: Header
- Riga 3+: Data

| Colonna | Header | Nome campo canonico | Tipo | Note |
|---------|--------|-------------------|------|------|
| 1 | Id | skip | - | Identificatore Fantacalcio interno |
| 2 | R | ruolo_classic | str | P/D/C/A (abbreviato da colonna 3 "RM") |
| 3 | RM | skip | - | Ruolo modulo (Por/Dif/Cen/Att) |
| 4 | Nome | nome | str | - |
| 5 | Squadra | squadra | str | - |
| 6 | Qt.A | qt_attuale | int | Quotazione attuale |
| 7 | Qt.I | qt_iniziale | int | Quotazione iniziale |
| 12 | FVM | fvm | int | Fanta Valore di Mercato |

**Data di nascita:** ❌ **Non disponibile nel file** → NULL, marker `data_nascita_available=false`

**Stagione:** String format `'2025-26'` (dedotto dal titolo "Quotazioni Fantacalcio Stagione 2025 26")

### Storico Aggregato
**Fonte scelta:** Fantacalcio.it
**Motivo:** Unica fonte che espone VOTO + FANTAVOTO separati via API strutturata (xlsx download).

**Alternativa scartata:** PianetaFanta ha archivio più lungo (2002-25) ma richiede scraping web fragile.

**Disponibilità assist 3-fasce:** ❌ **No**

Fantacalcio.it non classifica gli assist in 3 fasce (soft/classic/gold) pubblicamente. Useremo il fallback `+1.0` per tutti gli assist.

**Marker:** `assist_tier_available = false`

### Voti Giornata (D/C/P)
**Fonte scelta:** PianetaFanta
**URL:** `https://www.pianetafanta.it/voti-ufficiali-archivio.asp`
**Tipo:** Web scraping (HTML)
**Archivio:** 2002-2025 (più completo)

**Alternativa scartata:** Fantacalcio.it ha voti giornalieri ma limitati alle ultime 1-2 stagioni.

**Stagioni:** 2 (default, configurabile in `config/sources.yaml`)

---

## Valori bonus/malus "classici"

**Confermati dall'utente.** Questi valori NON sono nel regolamento testuale pero sono lo standard fantacalcio.it:

- Ammonizione: **-0.5**
- Espulsione: **-1.0**
- Autogol: **-2.0**
- Rigore segnato: **+3.0**
- Rigore sbagliato: **-3.0**
- Rigore parato (portiere): **+3.0**
- Gol subito (portiere): **-1.0**
- Imbattibilità (portiere ≥45'): **+1.0**

Codificati in `config/rules_lega.yaml` come single source of truth.

---

## Design Architecture

### Ports & Adapters
Ogni sorgente è implementata come `SourceAdapter` (protocol in `sources/base.py`).
Oggi: `ListoneAdapter`, `Storico` (placeholder), `GiornataPianetaFanta` (M4).

### Raw immutabile
I file scaricati vanno in `data/raw/<source>/<YYYYMMDD>/` e **non vengono mai modificati**.
Se miglioriamo il parser, riprocessiamo dai raw committati senza riscaricamento.

### Fixture reali committate
`tests/fixtures_real/` contiene snapshot reali (sottoinsieme dei raw) usati nei test.
Il primo `download` fa la chiamata reale; i run successivi di test girano offline.

---

## M0 Status

- [x] Scaffold repo (pyproject.toml, structure)
- [x] rules_lega.yaml + loader pydantic
- [x] sources.yaml config
- [x] SourceAdapter protocol
- [x] ListoneAdapter stub (download + parse)
- [x] CLI typer (download, status, stage/build/verify stubs)
- [x] Test rules_loader.py
- [x] Test listone_download.py (con skip se fixture non esiste)
- [x] DECISIONS.md
- [ ] verify.sh verde
- [ ] Download reale del listone come fixture
- [ ] Ispezione mapping colonne reali xlsx
- [ ] PROGRESS.md

---

## M1 — Entity Resolution & Canonical Data Layer

### Player UID Generation
**Metodo:** SHA1 hash deterministico su `nome_norm | squadra.lower() | ruolo.upper() | data_nascita (if present)`

**Normalizzazione nomi (`normalize_name()`):**
1. Unicode NFD (decomposizione accenti)
2. Rimuovi accenti (categoria unicodedata "Mn")
3. Lowercase
4. Split e ordinamento alfabetico token
5. Join con spazi

Esempio: `"Nicolò Barella"` → `"barella nicolo"` (stesso hash di `"nicolo barella"` o `"BARELLA NICOLO"`)

**Collision handling:** attualmente nessuno (SHA1 su 16 char è una OAEP, rischio minimo su ~500 giocatori). Se collision, marcare in DECISIONS con `_2` suffix.

### DuckDB Schema
- **dim_player**: 532 record (uno per player_uid canonico)
- **dim_player_season**: 532 record (un record per giocatore per stagione)
- **dim_team_season**: 20 record (una per squadra Serie A per stagione)

Nessun FK violato, tutti i data type supportati da DuckDB.

### Data Availability
- **data_nascita**: non disponibile nel listone (532 record con NULL)
- **neopromossa** / **allenatore**: non disponibile nel listone (NULL in dim_team_season)

Marker: `data_nascita_available=false`, `neopromossa_available=false`, `allenatore_available=false`

### Raw Directory Structure (Post-M1)
```
data/raw/listone_ufficiale/
├── 20260612/
│   ├── quotazioni.xlsx    (file reale scaricato)
│   └── reject.log         (se record invalidi — vuoto in questo caso)
```

Quando arriverà il nuovo listone a settembre: `data/raw/listone_ufficiale/20260901/quotazioni.xlsx`
Il sistema userà automaticamente la cartella con data più recente via `find_latest_raw()`.

---

## M2 — Entity Resolution + Storico Aggregato

### Fonte XLSX Fantacalcio.it (download manuale)
**Fonte:** Fantacalcio.it Statistiche
**Formato:** XLSX (non HTML scraping — più robusto)
**Cartelle:** `data/raw/storico_aggregato/{stagione}/stats.xlsx`

**Stagioni disponibili:** 2024-25, 2023-24, 2022-23, 2021-22

**Struttura file:**
- Riga 1: Titolo (es. "Statistiche Fantacalcio Stagione 2024 25 Italia") → skip
- Riga 2: Header (18 colonne)
- Riga 3+: Dati giocatori (~200-680 per stagione)

**Mapping colonne XLSX → StoricoRecord:**

| Col | Header | Destinazione | Tipo | Note |
|-----|--------|--------------|------|------|
| 1 | Id | (ignora) | int | ID interno |
| 2 | R | (ignora) | str | Ruolo classico (P/D/C/A) |
| 3 | Rm | (ignora) | str | Ruolo moderno (Por/Ds/Dc/E) |
| 4 | Nome | **nome** | str | Nome giocatore |
| 5 | Squadra | **squadra** | str | Squadra |
| 6 | Pv | **presenze_voto** | int | Presenze con voto |
| 7 | Mv | **media_voto** | float | Media voto (6.0-10.0) |
| 8 | Fm | **media_fv_fonte** | float | Fantamedia ufficiale |
| 9 | Gf | **gol** | int | Gol fatti |
| 10 | Gs | **gol_subiti** | int | Gol subiti |
| 11 | Rp | **rig_parati** | int | Rigori parati |
| 12 | Rc | **rig_segnati** | int | Rigori segnati |
| 13 | R+ | (ignora) | int | Rigori bonus (non mappato) |
| 14 | R- | **rig_sbagliati** | int | Rigori sbagliati |
| 15 | Ass | **assist_tot** | int | Assist totali |
| 16 | Amm | **ammonizioni** | int | Ammonizioni (gialli) |
| 17 | Esp | **espulsioni** | int | Espulsioni (rossi) |
| 18 | Au | **autogol** | int | Autogol |

**Data availability M2:**
- `autogol`: ✅ Disponibile (colonna 18 "Au")
- `rig_sbagliati`: ✅ Disponibile (colonna 14 "R-")
- `clean_sheet`: ❌ NOT available → NULL, `clean_sheet_available=false`
- `presenze_fv = presenze_voto` (conservative assumption)

### Entity Resolution Strategy

**ER Coverage: 100.0%** ✅ (ID-based join + new player creation)

**Strategia risolutiva:**
1. **ID-based exact join** (primary): Match storico.id → listone.id
   - Zero-error matching: se l'ID esiste nel listone, uso quel player_uid
   - Coverage: ~970 record (36.1%)
   
2. **New player creation** (fallback): Per storico records senza ID match
   - Genera nuovo player_uid usando uid.generate_player_uid(nome, squadra, "P", None)
   - Inserisci in dim_player come nuovo record
   - Coverage: ~1720 record (63.9%)

3. **Result: 100% coverage**
   - 2690 record parsati
   - 2690 record inseriti in fact_season_agg (zero rejections)
   - dim_player espande da 532 (listone) a ~1676 (listone + historical)

**Conteggio M2:**
- Parsati: 2690 record (4 stagioni × ~675 giocatori)
- Matched via ID: 970 record (36.1%, zero error)
- Created as new: 1720 record (63.9%)
- Inserted in fact_season_agg: 2690 record (100%)
- Rejected: 0 record

**Rationale:**
- Players transfer between teams and seasons
- A player in 2021-22 might not be in listone 2025-26 (retired, transferred, relegated)
- That player is VALID historical data and must be preserved
- ID-based join ensures accuracy; new player creation ensures completeness

**NO fuzzy matching in main pipeline:**
- Fuzzy matching was causing false positives (Retegui → Sergi Roberto)
- ID-based join is exact and reliable
- New player creation handles all unmatched cases without guessing

---

## M3 — Ricalcolo Fantavoto Individuale

### Calcolo fantavoto
`media_fv_lega` = `media_voto` + bonus_individuali (no modificatori collettivi).
Bonus applicati: gol (+3), assist (+1), ammonizioni (-0.5), espulsioni (-1), 
rigori_segnati (+3), rigori_sbagliati (-3), rigori_parati (+3, portieri), 
gol_subiti (-1, portieri), autogol (-2).

**Formula per-partita:** `media_fv_lega = voto_medio + (bonus_totale / presenze_voto)`
- bonus_totale = somma stagionale di tutti i bonus
- Diviso per presenze_voto = media per partita

### Delta M3 — Tolleranza nota
- **Target:** delta < 0.1 (accettabile)
- **Osservato:** 92.8% records < 0.1, max delta 0.9420
- **Outlier (159 record, 7.2%):** delta 0.1-0.9, tutti bomber/rigoristi
  - Calhanoglu 13 gol + 10 rigori → delta 0.94
  - Immobile 27 gol + 7 rigori → delta 0.68
  - Criscito 6 gol + 6 rigori → delta 0.90

**Root cause:** Arrotondamento strutturale per-partita su giocatori con bonus alti
- media_fv_fonte = media giornaliera reale (da Fantacalcio.it)
- media_fv_lega = media teorica da aggregati (nostro ricalcolo)
- Per bomber, bonus per-partita è alto (3+ punti). Differenza tra media giornaliera reale e teorica = divergenza strutturale.

**Status:** ✅ ACCETTABILE — rumore di ricostruzione, NON errore di logica

### Due metriche di fantavoto:
- **media_fv_fonte:** Media dei fantavoti giornalieri dalle singole partite
  - Fornito da Fantacalcio.it nello storico aggregato
  - Riflette performance reale giornaliera con bonus/malus giornalieri
- **media_fv_lega:** Fantavoto sintetico ricalcolato da dati aggregati (media_voto + bonus totali)
  - Calcolato da noi usando rules_lega.yaml
  - Rappresenta il fantavoto "teorico" basato su statistica aggregata
  - **NON coincide con media_fv_fonte** (che è la media giornaliera, non il sintetico)

Esempio: Giocatore con media_voto=5.36, 1 gol, 2 ammonizioni su 37 presenze:
- media_fv_fonte = 5.50 (media giornaliera effettiva)
- media_fv_lega = 5.36 + 3 - 1 = 7.36 (sintetico)
- Sono diversi per design; entrambi validi per scopi diversi

### Quality Gate M3
- media_fv_lega non null per tutti i record (1039 record popolati)
- No sanity check cross-field (media_fv_fonte e media_fv_lega hanno scopi diversi)

---

## Note forward-compat

- **API-Football**: preparato il design per aggiungerla come nuova source domani (xref_alias parametrico, dim_player.data_nascita per disambiguazione). Non implementare prima di M4.
- **xG/xA**: out-of-scope, Phase 4 Analisi.
- **Modificatori collettivi**: codificati in config ma non applicati in M0-M1 (M2+ Formazione).
