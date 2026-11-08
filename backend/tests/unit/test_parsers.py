from io import BytesIO

import pytest
from openpyxl import Workbook

from investor.ingest import parse_world_bank


def test_world_bank_parser_missing_and_negative_values():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Monthly Prices"
    for row in [
        ("Historical prices",),
        ("", "Gold", "Crude oil, Brent"),
        ("", "$/oz", "$/bbl"),
        ("2020M01", 1500, 60),
        ("2020M02", "..", -10),
        ("2020M03", float("inf"), None),
    ]:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    assets, points = parse_world_bank(stream.getvalue())
    assert len(assets) == 2
    assert points == [
        ("wb-gold", "2020-01-01", 1500.0),
        ("wb-crude-oil-brent", "2020-01-01", 60.0),
        ("wb-crude-oil-brent", "2020-02-01", -10.0),
    ]


def test_fred_parser_rejects_missing_schema_and_skips_gaps():
    from investor.ingest import parse_fred

    data = b"observation_date,FR10\n2020-01-01,-0.1\n2020-02-01,.\n2020-03-01,1.2\n"
    assert parse_fred(data, "FR10") == [
        ("FR10", "2020-01-01", -0.1),
        ("FR10", "2020-03-01", 1.2),
    ]
    with pytest.raises(ValueError):
        parse_fred(b"<html>Unavailable</html>", "FR10")
    with pytest.raises(ValueError):
        parse_fred(b"observation_date,FR10\ninvalid,2\n", "FR10")
