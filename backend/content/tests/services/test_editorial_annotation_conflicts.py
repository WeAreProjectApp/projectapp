"""One editorial leaf cannot have competing format declarations."""
import pytest
from rest_framework.exceptions import ValidationError

from content.services.editorial_format import validate_formats, validate_nested_formats


def test_nested_annotations_reject_conflicting_profiles():
    value = {'group': {'body': '**Text**', 'text_formats': {'/body': 'plain'}},
             'text_formats': {'/group/body': 'markdown_html_v1'}}

    with pytest.raises(ValidationError, match='contradictorios'):
        validate_nested_formats(value)


def test_root_annotation_rejects_conflicting_local_profile():
    value = {'content_json': {'intro': '**Text**', 'text_formats': {'/intro': 'plain'}}}

    with pytest.raises(ValidationError, match='contradictorios'):
        validate_formats('proposalsection', value, {'/content_json/intro': 'markdown_html_v1'})


def test_repeated_annotation_accepts_same_profile():
    value = {'group': {'body': '**Text**', 'text_formats': {'/body': 'markdown_html_v1'}},
             'text_formats': {'/group/body': 'markdown_html_v1'}}

    validate_nested_formats(value)

    assert value['group']['body'] == '**Text**'
