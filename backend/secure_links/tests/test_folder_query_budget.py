"""Filing reads stay bounded as the folder and link inventory grows."""
import pytest
from secure_links import folder_services as filing
from secure_links.queries import folder_index

pytestmark = pytest.mark.django_db


@pytest.fixture(params=[1, 12])
def folder_inventory(request, make_link, project):
    for index in range(request.param):
        folder = filing.save_folder(data={'name': f'Servidores {index}', 'parent': project.secure_link_root_folder})
        make_link(folder=folder)
    return request.param


def test_folder_index_uses_bounded_queries(folder_inventory, django_assert_max_num_queries):
    with django_assert_max_num_queries(6):
        result = folder_index()
    assert result['navigation']['totals']['active']['documents'] == folder_inventory
    assert len(result['folders']) >= folder_inventory + 1
