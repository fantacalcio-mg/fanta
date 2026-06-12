from pathlib import Path
from typing import Any, Protocol


class SourceAdapter(Protocol):
    """Protocol per source adapters.

    Ogni sorgente dati implementa questo protocollo per scaricare e parsare.
    """

    def download(self, force: bool = False) -> Path:
        """Scarica il raw dal source e lo salva in data/raw/<source>/YYYYMMDD/.

        Args:
            force: se True, riscarica anche se il file esiste già.

        Returns:
            Path del file raw scaricato.

        Raises:
            Exception: se il download o il salvataggio fallisce.
        """
        ...

    def parse(self, raw_path: Path) -> list[dict[str, Any]]:
        """Parsa il raw e ritorna una lista di record nello schema della fonte.

        Args:
            raw_path: path al file raw precedentemente scaricato.

        Returns:
            Lista di record (dict) nello schema della fonte.

        Raises:
            ValueError: se il parsing fallisce.
        """
        ...
