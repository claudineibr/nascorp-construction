import unicodedata


def _normalized(value):
    return ''.join(char for char in unicodedata.normalize('NFKD', value or '').casefold()
                   if not unicodedata.combining(char))


def original_unit_description(description, buyer_name, project_name):
    value = (description or '').strip()
    buyer = _normalized((buyer_name or '').strip())
    if buyer:
        normalized, positions = [], []
        for index, char in enumerate(value):
            for part in _normalized(char):
                normalized.append(part)
                positions.append(index + 1)
        normalized = ''.join(normalized)
        if normalized.startswith(buyer) and (len(normalized) == len(buyer)
                                            or normalized[len(buyer)] in ' -–—'):
            value = value[positions[len(buyer) - 1]:].lstrip(' -–—')
    return value or (project_name or '').strip()


def occupied_unit_description(original, buyer_name, project_name):
    base = (original or '').strip()
    project = (project_name or '').strip()
    base_key = _normalized(base)
    project_key = _normalized(project)
    has_project_prefix = base_key.startswith(project_key) and (
        len(base_key) == len(project_key) or base_key[len(project_key)] in ' -–—'
    )
    if project and not has_project_prefix:
        base = f'{project} - {base}' if base else project
    return f'{buyer_name.strip()} - {base}'
