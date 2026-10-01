"""The metadata list remains bounded when every row has replacement metadata."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from .test_platform_api import base

pytestmark = pytest.mark.django_db


def test_metadata_list_query_budget_is_bounded(platform_client, project, create_owned):
    """Detecta una consulta por fila al consultar sucesores/capacidades."""
    for number in range(26):
        create_owned(title=f'Credencial {number}')

    with CaptureQueriesContext(connection) as queries:
        response = platform_client.get(base(project))

    assert response.status_code == 200
    assert response.data['count'] == 26
    assert len(response.data['results']) == 25
    assert len(queries) <= 8
