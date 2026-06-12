from typing import Literal

from pydantic import BaseModel, model_validator


class RosaComposizione(BaseModel):
    P: int
    D: int
    C: int
    A: int


class PanchinaOrdinata(BaseModel):
    P: int
    D: int
    C: int
    A: int


class LegaBase(BaseModel):
    partecipanti: int
    budget: int
    base_asta: int
    rosa: RosaComposizione
    panchina_ordinata: PanchinaOrdinata
    sostituzioni_max: int
    giornate_lega: int
    ultimo_girone_campo_neutro: bool


class AssistTiers(BaseModel):
    soft: float
    classic: float
    gold: float


class AssistConfig(BaseModel):
    tiers: AssistTiers
    fallback_se_tier_non_disponibile: float


class BonusIndividuali(BaseModel):
    scope: Literal["individual"] = "individual"
    gol_segnato: float
    assist: AssistConfig
    ammonizione: float
    espulsione: float
    autogol: float
    rigore_segnato: float
    rigore_sbagliato: float
    rigore_parato: float
    gol_subito_portiere: float
    imbattibilita_portiere: float


class DifesaConfig(BaseModel):
    base: Literal["VOTO"]
    difesa_minima: int
    migliori_n: int
    soglie: dict[str, float]
    step: dict[str, float]


class CapitanoConfig(BaseModel):
    base: Literal["VOTO"]
    riferimento: float
    passo: float


class FairplayConfig(BaseModel):
    base: Literal["cartellini"]
    bonus: float


class ModificatoriCollettivi(BaseModel):
    scope: Literal["collective"] = "collective"
    difesa: DifesaConfig
    capitano: CapitanoConfig
    fairplay: FairplayConfig


class CentrocampoConfig(BaseModel):
    base: Literal["VOTO"]
    sempre_attivo: bool
    somma_voti: bool
    soglia_diff: float
    passo_bonus: float
    voto_giocatore_mancante: float


class PartitaCasalingaConfig(BaseModel):
    bonus_totale_voti: float


class SogliGolConfig(BaseModel):
    base_punti: int
    passo_punti: int
    regola_sotto_60: bool


class ModificatoriScontro(BaseModel):
    scope: Literal["matchup"] = "matchup"
    centrocampo: CentrocampoConfig
    partita_casalinga: PartitaCasalingaConfig
    soglie_gol: SogliGolConfig


class LegaConfig(BaseModel):
    lega: LegaBase
    bonus_individuali: BonusIndividuali
    modificatori_collettivi: ModificatoriCollettivi
    modificatori_scontro: ModificatoriScontro

    @model_validator(mode="after")
    def validate_rosa_totale(self) -> "LegaConfig":
        rosa = self.lega.rosa
        totale_titolari = rosa.P + rosa.D + rosa.C + rosa.A
        if totale_titolari != 25:
            raise ValueError(f"Rosa totale deve essere 25, trovato {totale_titolari}")
        return self

    @model_validator(mode="after")
    def validate_panchina_totale(self) -> "LegaConfig":
        panchina = self.lega.panchina_ordinata
        totale_panchina = panchina.P + panchina.D + panchina.C + panchina.A
        if totale_panchina != 7:
            raise ValueError(f"Panchina ordinata totale deve essere 7, trovato {totale_panchina}")
        return self
