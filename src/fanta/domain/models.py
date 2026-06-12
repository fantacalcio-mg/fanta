"""Modelli di dominio per il data layer.

Entità pure senza I/O.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ListoneRecord(BaseModel):
    """Record di un giocatore dal Listone Ufficiale (staging schema)."""

    nome: str
    squadra: str
    ruolo_classic: Literal["P", "D", "C", "A"]
    qt_iniziale: int = Field(ge=1)
    qt_attuale: int = Field(ge=1)
    fvm: int | None = None
    data_nascita: date | None = None


class PlayerUID:
    """Player UID canonico (generato da entity resolution)."""

    uid: str
    nome_canonico: str
    nome_norm: str
    data_nascita: date | None = None


class StoricoRecord(BaseModel):
    """Record di un giocatore dal Storico Aggregato (staging schema)."""

    id: int | None = None
    nome: str
    squadra: str
    stagione: str
    presenze_voto: int = Field(ge=0)
    media_voto: float = Field(ge=0, le=10)
    media_fv_fonte: float
    gol: int = Field(default=0, ge=0)
    assist_tot: int = Field(default=0, ge=0)
    ammonizioni: int = Field(default=0, ge=0)
    espulsioni: int = Field(default=0, ge=0)
    rig_segnati: int = Field(default=0, ge=0)
    rig_parati: int = Field(default=0, ge=0)
    gol_subiti: int = Field(default=0, ge=0)
    autogol: int | None = None
    rig_sbagliati: int | None = None
    clean_sheet: int | None = None
