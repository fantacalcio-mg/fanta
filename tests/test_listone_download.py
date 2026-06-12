from pathlib import Path

import pytest

from fanta.sources.listone_ufficiale import ListoneAdapter


@pytest.fixture
def fixtures_dir():
    """Path alla directory fixtures_real."""
    return Path(__file__).parent / "fixtures_real"


def test_parse_listone_fixture(fixtures_dir):
    """Parsa il fixture reale del listone.

    NOTA: Questo test richiede un file xlsx in fixtures_real/.
    Se il file non esiste, il test viene skippato.
    """
    fixture_file = fixtures_dir / "listone_ufficiale" / "quotazioni.xlsx"

    if not fixture_file.exists():
        pytest.skip(f"Fixture non disponibile: {fixture_file}")

    adapter = ListoneAdapter(
        url="<placeholder>",  # Non usato nel parsing
        raw_dir=fixtures_dir / "listone_ufficiale",
    )

    records = adapter.parse(fixture_file)

    # Quality gates M0
    assert len(records) > 0, "Nessun record parsato"
    assert 450 <= len(records) <= 650, (
        f"Numero giocatori {len(records)} fuori intervallo [450, 650]"
    )

    # Controlla che ci siano i campi obbligatori
    for record in records:
        assert "nome" in record
        assert "squadra" in record
        assert "ruolo_classic" in record
        assert record["squadra"] is not None, "Campo squadra null"
        assert record["ruolo_classic"] is not None, "Campo ruolo_classic null"

    # Controlla che ci siano almeno 3 ruoli diversi (P/D/C/A)
    ruoli = {r["ruolo_classic"] for r in records}
    assert len(ruoli) >= 3, f"Troppo pochi ruoli distinti: {ruoli}"
