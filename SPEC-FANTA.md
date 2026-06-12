# FANTACALCIO ENGINE — FASE 1: INGESTION & CANONICAL DATA LAYER
### Master prompt per Claude Code

> Sistema di supporto **personale** (no SaaS, no MVP, nessuna distribuzione).
> Modalità **Classic**, lega a 10 partecipanti, regole proprietarie codificate qui sotto.
> Questa fase costruisce **le fondamenta dati**: dominio normalizzato + entity resolution.
> Lo scraping è solo un *adapter sottile e sostituibile*, NON la fondazione.

---

## 0. Obiettivo della fase

Produrre un **data layer canonico, storicizzato e interrogabile** che alimenterà le fasi successive (Asta, Formazione, Analisi). Al termine della fase devo poter eseguire un singolo comando di verifica che, **su dati reali scaricati** (nessun mock, nessuna fixture sintetica), dimostri che:

1. Esiste un universo giocatori Serie A della stagione corrente con ruolo Classic e quotazione ufficiale.
2. Esiste lo storico aggregato delle ultime stagioni, con **voto e fantavoto separati** e tutti i componenti grezzi (gol, assist, ammonizioni, espulsioni, rigori, gol subiti, presenze).
3. Ogni giocatore ha una **chiave canonica stabile** (`player_uid`) che lo identifica attraverso fonti e stagioni nonostante differenze di nome.
4. Esiste un **motore di ricalcolo del fantavoto** parametrizzato sulle MIE regole di lega, validato contro la fantamedia delle fonti a parità di regole standard.
5. Esiste la **distribuzione giornata-per-giornata dei voti** per difensori, centrocampisti e portieri delle ultime stagioni (serve per stimare i modificatori collettivi nelle fasi successive).

---

## 1. Vincoli architetturali (NON negoziabili)

- **Ports & Adapters.** Ogni sorgente dati è dietro un'interfaccia `SourceAdapter`. Cambiare/aggiungere una fonte NON deve toccare staging o canonical. Lo scraper è usa-e-getta.
- **Tre strati separati e con responsabilità unica:**
  - `raw/` — file sorgente **immutabili e datati**, salvati così come scaricati. Mai modificati, mai cancellati. Sono la verità di partenza: se miglioro un parser, ri-processo dai raw **senza ri-scaricare**.
  - `staging` — il raw parsato e tipizzato, **ancora nello schema della fonte**. Nessuna fusione qui.
  - `canonical` — entity-resolved, normalizzato, con `fm_lega` ricalcolata. È l'unico strato che le fasi successive vedono.
- **Ingerisci gli EVENTI ATOMICI, non la fantamedia delle fonti.** La `Fm` di una fonte assume regole bonus/malus che NON sono le mie. Ingerisci i componenti grezzi e ricalcola tu. La FM della fonte si conserva solo come *validazione*.
- **Voto e fantavoto sono due campi distinti e obbligatori** ovunque. I miei modificatori più pesanti (difesa, centrocampo, capitano) leggono il **voto puro**, non il fantavoto.
- **Tutto locale e file-based.** Il dataset è minuscolo (~600 giocatori × 38 giornate × poche stagioni ≈ 10^5 righe). Niente Postgres, niente Docker, niente cloud, niente ORM pesante. Over-engineering = fallimento della fase.
- **Nessun mock nei test.** I test girano su snapshot **reali** committati in `raw/` (vedi §11). Il primo run fa il download reale; i run successivi rigiocano i raw committati per determinismo. "Dati reali" significa esattamente questo.

---

## 2. Stack

- Python **3.12**, gestione con **uv**.
- **DuckDB** come motore canonico (colonnare, in-process, legge xlsx/csv/parquet nativamente, sta in un file).
- **Polars** per le trasformazioni.
- **httpx** (download) + **selectolax** o **lxml** (parsing HTML) + **openpyxl** (xlsx).
- **pydantic v2** per validazione dei record in staging.
- **typer** per la CLI.
- **pytest** per i test, **ruff** per lint+format.
- Nessuna altra dipendenza senza giustificazione scritta in `DECISIONS.md`.

---

## 3. Struttura repo

```
fanta-engine/
  pyproject.toml
  README.md
  PROGRESS.md
  DECISIONS.md
  verify.sh                      # gate unico della fase
  config/
    rules_lega.yaml              # le MIE regole, single source of truth
    sources.yaml                 # config delle sorgenti (URL, stagioni, rate limit)
  data/
    raw/                         # immutabile, datato: raw/<source>/<YYYYMMDD>/...
    canonical/fanta.duckdb       # output canonico
  src/fanta/
    domain/                      # entità e tipi di dominio puri (no I/O)
    rules/                       # loader config + motore ricalcolo fantavoto
    sources/                     # un modulo per adapter, dietro SourceAdapter
      base.py                    # il port: SourceAdapter
      listone_ufficiale.py
      storico_aggregato.py
      giornata_voti.py
    pipeline/                    # raw->staging->canonical
    entity/                      # entity resolution + xref + override
    quality/                     # quality gates
    cli.py                       # typer: download, stage, build, verify, status
  tests/
    fixtures_real/               # snapshot REALI committati (vedi §11)
    test_*.py
```

---

## 4. Workflow operativo (rispettare alla lettera)

- Mantieni **`PROGRESS.md`** (stato per milestone, spuntato man mano) e **`DECISIONS.md`** (ogni scelta non ovvia, ogni mapping di colonne reali, ogni assunzione su valori non specificati dal regolamento).
- **`/plan` prima di `/execute`** per ogni milestone. Non scrivere codice prima di aver proposto il piano della milestone e di aver aggiornato PROGRESS.
- `/clear` del contesto tra una milestone e l'altra.
- Procedi a **walking skeleton verticale**: ogni milestone (M0→M4) deve chiudere con `verify.sh` **verde su dati reali** prima di passare alla successiva. Niente milestone "a metà".
- Quando una fonte reale non espone un campo che il regolamento richiede, **NON inventare**: registra il gap in `DECISIONS.md`, implementa un fallback esplicito con un flag `*_available=false`, e continua.

---

## 5. Regole della lega → `config/rules_lega.yaml`

Codifica **tutto** il regolamento qui. È la single source of truth: sia il ricalcolo fantavoto sia (nelle fasi successive) la valutazione e la simulazione leggono da qui. In questa fase il motore usa solo i **bonus/malus individuali**; i modificatori collettivi e di scontro vanno comunque codificati (servono dopo), ma marcati `scope: collective` / `scope: matchup` così è chiaro che NON entrano nel fantavoto del singolo.

Valori da codificare:

```yaml
lega:
  partecipanti: 10
  budget: 500
  base_asta: 1
  rosa: { P: 3, D: 8, C: 8, A: 6 }     # 23 titolari
  panchina_ordinata: { P: 1, D: 2, C: 2, A: 2 }
  sostituzioni_max: 5                   # solo in caso di S.V., ruolo per ruolo
  giornate_lega: 33                     # inizia a G4 Serie A, finisce a G36, 3 tornate
  ultimo_girone_campo_neutro: true      # niente bonus casalinga nell'ultimo girone

bonus_individuali:        # scope: individual  -> entrano nel fantavoto del singolo
  gol_segnato: +3
  assist:
    tiers:                # 3 fasce: scarpetta bronzo/argento/oro
      soft: +0.5
      classic: +1.0
      gold: +1.5
    fallback_se_tier_non_disponibile: +1.0   # vedi DECISIONS: usare se la fonte dà solo il totale
  # I valori sotto NON sono nel regolamento (che dice "i classici"): sono lo STANDARD
  # fantacalcio.it. VANNO CONFERMATI da me -> registrare in DECISIONS come assunzione.
  ammonizione: -0.5
  espulsione: -1.0
  autogol: -2.0
  rigore_segnato: +3.0
  rigore_sbagliato: -3.0
  rigore_parato: +3.0            # portiere
  gol_subito_portiere: -1.0      # per gol subito
  imbattibilita_portiere: +1.0   # 1 punto se non subisce gol giocando >=45'  (scope: individual)

modificatori_collettivi:   # scope: collective -> NON nel singolo, calcolati a formazione (fasi successive)
  difesa:
    base: VOTO              # usa il VOTO, non il fantavoto
    difesa_minima: 4
    migliori_n: 4          # media dei 4 migliori voti difensori
    soglie:                # media > soglia -> bonus  (funzione a gradini)
      "6.00": +0.5
      "6.25": +1.0
      "6.50": +1.5
      step: { delta_soglia: 0.25, delta_bonus: 0.5 }   # "e così via"
  capitano:
    base: VOTO
    riferimento: 6.0       # voto 6.5->+0.5, 7->+1, 5.5->-0.5  (lineare, passo 0.5)
    passo: 0.5
  fairplay:
    base: cartellini
    bonus: +1.0            # se nessun cartellino tra gli 11 in campo, solo se si gioca in 11

modificatori_scontro:      # scope: matchup -> dipendono dall'avversario
  centrocampo:
    base: VOTO
    sempre_attivo: true
    somma_voti: true       # somma dei due centrocampi che si sfidano
    soglia_diff: 2.0       # diff 2 -> +1/-1, diff 4 -> +2/-2 ...
    passo_bonus: 1.0
    voto_giocatore_mancante: 5.0   # chi ha meno cc prende 5 per ogni cc mancante
  partita_casalinga:
    bonus_totale_voti: +2.0        # disattivo nell'ultimo girone (campo neutro)
  soglie_gol:
    base_punti: 66         # 66 -> 1 gol
    passo_punti: 6         # ogni 6 punti 1 gol in più
    regola_sotto_60: true  # se faccio <60 e avversario >60 -> 1 gol a chi ha il punteggio piu alto
```

Implementa un **loader pydantic** che valida questo YAML allo startup e fallisce forte se incoerente.

---

## 6. Modello dati canonico (DuckDB DDL)

Dimensioni separate dai fatti. **Ruolo e squadra sono per-stagione**, non per-giocatore.

```sql
-- identità cross-stagione (stabile nel tempo)
CREATE TABLE dim_player (
  player_uid     VARCHAR PRIMARY KEY,   -- chiave canonica generata
  nome_canonico  VARCHAR NOT NULL,
  nome_norm      VARCHAR NOT NULL,      -- accenti rimossi, lower, traslitterato
  data_nascita   DATE                   -- disambiguatore omonimi (null ammesso)
);

-- ruolo/squadra/quotazione per stagione
CREATE TABLE dim_player_season (
  player_uid     VARCHAR NOT NULL REFERENCES dim_player,
  stagione       VARCHAR NOT NULL,      -- es '2025-26'
  squadra        VARCHAR NOT NULL,
  ruolo_classic  VARCHAR NOT NULL,      -- P/D/C/A
  qt_iniziale    INTEGER,               -- dal listone
  qt_attuale     INTEGER,
  fvm            INTEGER,               -- Fanta Valore di Mercato (listone)
  PRIMARY KEY (player_uid, stagione)
);

CREATE TABLE dim_team_season (
  squadra        VARCHAR NOT NULL,
  stagione       VARCHAR NOT NULL,
  neopromossa    BOOLEAN,
  allenatore     VARCHAR,
  PRIMARY KEY (squadra, stagione)
);

-- AGGREGATO stagionale: lo zoccolo dell'asta
CREATE TABLE fact_season_agg (
  player_uid     VARCHAR NOT NULL,
  stagione       VARCHAR NOT NULL,
  presenze_voto  INTEGER,               -- partite con voto
  presenze_fv    INTEGER,               -- partite con fantavoto (entrate in campo)
  media_voto     DOUBLE,
  media_fv_fonte DOUBLE,                -- FM della fonte (solo validazione)
  media_fv_lega  DOUBLE,                -- RICALCOLATA sulle mie regole individuali
  gol            INTEGER,
  assist_tot     INTEGER,
  assist_soft    INTEGER,               -- null se la fonte non classifica
  assist_classic INTEGER,
  assist_gold    INTEGER,
  ammonizioni    INTEGER,
  espulsioni     INTEGER,
  autogol        INTEGER,
  rig_segnati    INTEGER,
  rig_sbagliati  INTEGER,
  rig_parati     INTEGER,               -- portiere
  gol_subiti     INTEGER,               -- portiere
  clean_sheet    INTEGER,               -- partite da imbattuto >=45' (portiere)
  PRIMARY KEY (player_uid, stagione)
);

-- GRANULARE: solo D/C/P, ultime 1-2 stagioni. Serve per la distribuzione dei voti.
CREATE TABLE fact_giornata (
  player_uid     VARCHAR NOT NULL,
  stagione       VARCHAR NOT NULL,
  giornata       INTEGER NOT NULL,
  squadra        VARCHAR,
  ruolo_classic  VARCHAR,
  voto           DOUBLE,                -- null = non giocato; gestire S.V. a parte
  is_sv          BOOLEAN,               -- presente senza voto (voto politico): stato distinto
  fantavoto      DOUBLE,
  gol INTEGER, assist INTEGER, ammonito BOOLEAN, espulso BOOLEAN,
  gol_subiti INTEGER, clean_sheet BOOLEAN,
  PRIMARY KEY (player_uid, stagione, giornata)
);

-- ENTITY RESOLUTION: (fonte, chiave_sorgente) -> player_uid
CREATE TABLE xref_alias (
  source         VARCHAR NOT NULL,
  source_key     VARCHAR NOT NULL,      -- come la fonte identifica il giocatore
  player_uid     VARCHAR NOT NULL,
  confidence     DOUBLE,
  manual         BOOLEAN DEFAULT FALSE, -- override umano: prevale sempre
  PRIMARY KEY (source, source_key)
);
```

`is_sv` / voto politico va trattato come **stato distinto** da "non giocato": altrimenti le medie mentono.

---

## 7. Sorgenti dati reali

> Regola generale: **preferisci il download ufficiale strutturato allo scraping**. Scraping solo dove non c'è alternativa, sempre educato (User-Agent identificativo, rate limit da `sources.yaml`, cache su `raw/`). Per ogni fonte, **ispeziona la struttura reale corrente** prima di scrivere l'adapter, e **documenta in `DECISIONS.md` il mapping colonna-reale → campo-canonico**. Non assumere colonne: guardale.

Tre adapter, in quest'ordine di priorità:

1. **`listone_ufficiale`** — il file **Quotazioni/Listone ufficiale** (Fantacalcio.it, export `.xlsx`). È l'**ancora**: definisce l'universo giocatori della stagione corrente, il ruolo Classic, FVM e quotazioni. È un download pulito, non scraping fragile. Da questo si seminano `dim_player` + `dim_player_season` + `dim_team_season` e si generano i `player_uid` iniziali. Va ri-scaricato una volta vicino alla data della mia asta (post-mercato).

2. **`storico_aggregato`** — statistiche aggregate per stagione delle ultime stagioni (scegli UNA fonte reale solida che esponga **voto E fantavoto separati** più i componenti grezzi; candidate: pagine statistiche di Fantacalcio.it, Fanta.Soccer, Pianetafanta — valuta quale è più stabile e completa, **giustifica la scelta in DECISIONS**). Le stagioni chiuse sono immutabili: si scaricano una volta e non cambiano più. Alimenta `fact_season_agg`.

3. **`giornata_voti`** — voti per giornata di **difensori, centrocampisti e portieri**, ultime **1–2 stagioni**. Serve la distribuzione, non solo la media (i modificatori difesa/capitano sono funzioni NON lineari del voto: `E[f(voto)] ≠ f(E[voto])`). Alimenta `fact_giornata`.

`xG/xA` (FBref/Understat) è **fuori scope** in questa fase: lo aggiungeremo nella fase Analisi. Non implementarlo ora.

Stagioni di backfill aggregato: **ultime 4** (default; parametrizzabile in `sources.yaml`). Oltre, il dato è poco predittivo per via dei cambi di Serie A.

> **Nota forward-compat (NON implementare in questa fase).** Esiste una fonte oggettiva professionale, **API-Football**, che sarà il backbone *oggettivo + identitario* nelle fasi successive (minutaggio, formazioni, infortuni in Fase 3; xG e candidati a regressione in Fase 4). NON espone il **voto in pagella** (ha solo un `rating` algoritmico, su scala diversa: inutilizzabile per i miei modificatori, che girano sulla pagella). Quindi **non è una fonte-voto e non entra in M2/M4 qui**. Va però *anticipata a costo zero* nel design: l'architettura deve poterla aggiungere domani come semplice nuova `source` senza rework. Concretamente è già così — `xref_alias` è parametrico per `source` e `dim_player.data_nascita` è nullable e ribackfillabile (API-Football fornirà `player_id` stabile + data di nascita, ottimi per disambiguare gli omonimi quando in Fase 4 si attraversa verso fonti estranee). Non aggiungere nulla per lei adesso: basta non fare scelte che la escludano.

---

## 8. Pipeline raw → staging → canonical

- `download`: ogni adapter scarica e salva in `raw/<source>/<YYYYMMDD>/` il file grezzo **non toccato**. Idempotente: se il raw del giorno esiste, non riscarica (flag `--force` per forzare).
- `stage`: parser per-fonte → tabelle pydantic-validate, schema della fonte. Qui si tipizza e si validano i record; record invalidi vanno in un reject log, non scartati silenziosamente.
- `build`: entity resolution + merge nello schema canonico + ricalcolo fantavoto + quality gates. Ricostruibile **interamente dai raw**, in modo deterministico, senza rete.

Tutta la CLI via typer: `fanta download|stage|build|verify|status`.

---

## 9. Entity resolution (qui è il costo vero, non nello scraping)

- Genera `player_uid` canonico dall'ancora (listone): da `nome_norm` (rimozione accenti, traslitterazione, lowercase, ordinamento token) + squadra + ruolo + data nascita quando disponibile.
- In ingestion delle altre fonti: **fuzzy match** (token set + Levenshtein/RapidFuzz) verso i `player_uid` esistenti, con soglia di confidence da config.
- Sotto soglia → **coda di override manuale**: scrivi le righe non risolte in un file `data/entity_review.csv` con i candidati top-k; gli override umani vanno in `xref_alias` con `manual=true` e **prevalgono sempre**. La tabella override è un **asset che cresce e si riusa ogni stagione**.
- Omonimi: data di nascita o squadra come tie-breaker; se irrisolvibile, flag esplicito, mai merge silenzioso.
- `build` deve fallire il quality gate se la coverage ER è sotto soglia (vedi §11), così la coda di review non viene ignorata.

---

## 10. Motore di ricalcolo fantavoto (solo individuale, questa fase)

In `src/fanta/rules/`:

- Funzione pura `calcola_fantavoto(voto, eventi, regole) -> float` che applica **solo** i `bonus_individuali` del config (gol, assist per fascia con fallback, cartellini, rigori, autogol, imbattibilità/gol subiti per i portieri). NON applica modificatori collettivi/scontro (quelli sono fasi successive).
- Aggregazione a `media_fv_lega` per `fact_season_agg`.
- **Validazione incrociata:** ricalcola anche una `media_fv_standard` usando un preset di regole "standard fantacalcio.it" e confrontala con `media_fv_fonte`. Se la differenza media supera una tolleranza piccola (es. 0.05), è un **bug di parsing** dei componenti → fallisci il gate. Questo è il sanity check che protegge dall'ingerire dati sporchi.

---

## 11. Quality gates + politica "dati reali"

`build` non scrive il canonico se un gate fallisce. Gate minimi:

- **Conteggio giocatori** stagione corrente in `[450, 650]`.
- **Null-check** su campi chiave (`ruolo_classic`, `squadra`, `presenze_voto`).
- **Coverage entity resolution** ≥ **99%** delle righe sorgente mappate a un `player_uid` (il residuo deve essere in `entity_review.csv`).
- **Sanity ricalcolo**: `media_fv_standard ≈ media_fv_fonte` entro tolleranza (vedi §10).
- **Voto ≠ fantavoto presenti entrambi** e non degeneri (no colonne tutte-null).
- **S.V. distinto da non-giocato** in `fact_giornata`.
- **Distribuzione disponibile**: per D/C/P delle stagioni granulari, almeno N osservazioni per giocatore-tipo per poter calcolare media+std.

**Politica dati reali (no mock).** I test NON usano dati sintetici. Si committano in `tests/fixtures_real/` gli **snapshot reali** scaricati (un sottoinsieme datato dei file in `raw/`, abbastanza da coprire i gate). `verify.sh` rigioca quei raw reali in modo deterministico e offline. Il primo `download` fa la chiamata reale; la verifica successiva non dipende dalla rete ma resta su **dato reale committato**. Documenta in `README.md` come rigenerare gli snapshot.

---

## 12. Milestone verticali (ognuna chiude con `verify.sh` verde su dati reali)

- **M0 — Scaffold.** Repo, `pyproject` (uv), ruff, pytest, typer skeleton, `PROGRESS.md`, `DECISIONS.md`, `rules_lega.yaml` completo + loader pydantic validato. `verify.sh` esegue lint+test e valida il config. *Tangibile:* `fanta status` stampa le regole caricate; il config invalido fa fallire forte.
- **M1 — Ancora (listone).** Adapter `listone_ufficiale` reale → `dim_player` / `dim_player_season` / `dim_team_season` + `player_uid`. *Tangibile:* `fanta build` popola il canonico; verify asserisce conteggio giocatori e null-check su dato reale.
- **M2 — Storico + entity resolution.** Adapter `storico_aggregato` reale (4 stagioni) → `fact_season_agg`, fuso via ER all'ancora. *Tangibile:* verify asserisce coverage ER ≥99% e produce `entity_review.csv` per il residuo.
- **M3 — Ricalcolo fantavoto.** Motore individuale → `media_fv_lega` + validazione `media_fv_standard ≈ media_fv_fonte`. *Tangibile:* verify asserisce la sanity di ricalcolo entro tolleranza su dato reale.
- **M4 — Granulare D/C/P.** Adapter `giornata_voti` reale (1–2 stagioni) → `fact_giornata` con `is_sv`. *Tangibile:* una query di esempio restituisce media+std del voto per un difensore reale; verify asserisce che la distribuzione è calcolabile.

---

## 13. Definition of Done della fase

- `verify.sh` verde end-to-end su dati reali, da `raw/` ricostruibile e deterministico.
- `fanta status` mostra: n. giocatori, stagioni caricate, coverage ER, esito sanity ricalcolo.
- `DECISIONS.md` contiene: la fonte storica scelta e perché, il mapping colonne reali, e **ogni valore assunto non presente nel regolamento** (in particolare i malus "classici" di §5 e la disponibilità o meno della classificazione assist a 3 fasce).
- Il canonico è interrogabile in SQL per le fasi successive senza ulteriori trasformazioni.

---

## 14. Cosa NON fare in questa fase (anti-scope-creep)

- NON calcolare modificatori collettivi/scontro (difesa, centrocampo, capitano, casalinga, soglie): si codificano nel config ma si applicano nelle fasi Formazione/Analisi.
- NON costruire il modello di valutazione d'asta (valore-voto vs valore-fantavoto, max-bid): è la Fase 2.
- NON integrare xG/xA, infortuni live, probabili formazioni: rispettivamente Fase 4 e Fase 3.
- NON costruire l'adapter **API-Football** in questa fase. È il backbone oggettivo/identitario delle fasi successive, non una fonte-voto (vedi nota in §7). Qui ci si limita a NON fare scelte di schema che ne impediscano l'aggiunta come nuova `source` domani.
- NON aggiungere UI. La CLI basta.
- NON introdurre DB server, container, o astrazioni "enterprise". Il dato è minuscolo: la cosa fatta bene È la cosa minima.

---

### Domande aperte da chiudere durante M0 (registrare le risposte in DECISIONS.md)

1. I **malus "classici"** (ammonizione, espulsione, autogol, rigore sbagliato/parato, gol subito portiere) NON sono nel regolamento testuale: confermare i valori standard fantacalcio.it adottati in §5.
2. La fonte storica scelta espone la **classificazione assist a 3 fasce** (soft/classic/gold) o solo il totale? Se solo il totale → usare il fallback e marcare `assist_tier_available=false`.
