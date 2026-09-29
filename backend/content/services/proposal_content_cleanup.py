"""Discard retired calculator pricing from new edits and legacy imports."""


def without_module_percentages(value):
    if isinstance(value, list):
        return [without_module_percentages(item) for item in value]
    if isinstance(value, dict):
        return {key: without_module_percentages(item) for key, item in value.items()
                if key != 'price_percent'}
    return value
