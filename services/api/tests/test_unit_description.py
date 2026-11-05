from app.domain.unit_description import occupied_unit_description, original_unit_description


def test_imported_name_keeps_physical_unit_when_buyer_moves():
    original = original_unit_description(
        'MARIA FICTÍCIA CONCEIÇÃO  - ARARAS RESIDENCE -QUADRA 05 LOTE 15A',
        'Maria Fictícia Conceição', 'ARARAS RESIDENCE',
    )
    assert original == 'ARARAS RESIDENCE -QUADRA 05 LOTE 15A'
    assert occupied_unit_description(original, 'JOAO EXEMPLO ARAÚJO', 'ARARAS RESIDENCE') == (
        'JOAO EXEMPLO ARAÚJO - ARARAS RESIDENCE -QUADRA 05 LOTE 15A'
    )
    assert occupied_unit_description(original, 'MARIA FICTÍCIA CONCEIÇÃO', 'ARARAS RESIDENCE') == (
        'MARIA FICTÍCIA CONCEIÇÃO - ARARAS RESIDENCE -QUADRA 05 LOTE 15A'
    )


def test_legacy_name_without_separator_restores_original_suffix():
    assert original_unit_description(
        'JOAO EXEMPLO ARAÚJO RESIDENCIAL OT  -  12/2025', 'João Exemplo Araújo', 'RESIDENCIAL OT',
    ) == 'RESIDENCIAL OT  -  12/2025'


def test_destination_uses_its_project_and_physical_details():
    assert occupied_unit_description('QUADRA 20 - LOTE 29 CASA 01', 'JOAO EXEMPLO ARAÚJO', 'RESIDENCIAL OT') == (
        'JOAO EXEMPLO ARAÚJO - RESIDENCIAL OT - QUADRA 20 - LOTE 29 CASA 01'
    )


def test_buyer_prefix_must_respect_word_boundary():
    assert original_unit_description('ANABELA - CASA 01', 'Ana', 'Residencial') == 'ANABELA - CASA 01'


def test_project_name_must_not_match_part_of_another_word():
    assert occupied_unit_description('SOLAR CASA 01', 'ANA', 'SOL') == 'ANA - SOL - SOLAR CASA 01'
