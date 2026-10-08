"""Query-budget contracts for deliverable detail mutations."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import (
    Deliverable,
    DeliverableVersion,
    DeliveryWorkspace,
    Project,
    UserProfile,
)

User = get_user_model()
MAX_DELIVERABLE_VERSION_QUERIES = 1


def _detail_url(project_id, deliverable_id, suffix=""):
    return f"/api/accounts/projects/{project_id}/deliverables/{deliverable_id}/{suffix}"


def _version_selects(queries):
    table = DeliverableVersion._meta.db_table.lower()
    return [
        query["sql"]
        for query in queries
        if query["sql"].lstrip().upper().startswith("SELECT")
        and table in query["sql"].lower()
    ]


def _version_counts(queries):
    table = DeliverableVersion._meta.db_table.lower()
    return [
        query["sql"]
        for query in queries
        if "COUNT(" in query["sql"].upper() and table in query["sql"].lower()
    ]


def _version_authors(count, *, start):
    return User.objects.bulk_create(
        [
            User(
                username=f"deliverable-version-author-{index}@example.com",
                email=f"deliverable-version-author-{index}@example.com",
                first_name=f"Author{index}",
                last_name="Version",
            )
            for index in range(start, start + count)
        ]
    )


def _deliverable_versions(deliverable, count, *, start):
    authors = _version_authors(count, start=start)
    return DeliverableVersion.objects.bulk_create(
        [
            DeliverableVersion(
                deliverable=deliverable,
                file=f"deliverables/versions/{deliverable.pk}-{number}.zip",
                version_number=number,
                uploaded_by=author,
            )
            for number, author in enumerate(authors, start=1)
        ]
    )


def _version_names(versions):
    return [
        f"{version.uploaded_by.first_name} {version.uploaded_by.last_name}"
        for version in versions
    ]


def _invalid_design_file():
    return {"file": ContentFile(b"not a zip", name="invalid.pdf")}


def _invalid_category_payload():
    return {"category": "invalid"}


def _deliverables_with_history(project, admin, *, label):
    one_version = Deliverable.objects.create(
        project=project,
        uploaded_by=admin,
        title=f"One {label}",
        category=Deliverable.CATEGORY_DESIGNS,
        file=f"deliverables/one-{label}.zip",
        current_version=1,
    )
    fifty_versions = Deliverable.objects.create(
        project=project,
        uploaded_by=admin,
        title=f"Fifty {label}",
        category=Deliverable.CATEGORY_DESIGNS,
        file=f"deliverables/fifty-{label}.zip",
        current_version=50,
    )
    return (
        one_version,
        fifty_versions,
        _deliverable_versions(one_version, 1, start=1),
        _deliverable_versions(fifty_versions, 50, start=100),
    )


def _patch_detail_responses(api_client, headers, project, one_version, fifty_versions):
    with CaptureQueriesContext(connection) as one_queries:
        one_response = api_client.patch(
            _detail_url(project.pk, one_version.pk),
            {"title": "One version updated"},
            format="json",
            **headers,
        )
    with CaptureQueriesContext(connection) as fifty_queries:
        fifty_response = api_client.patch(
            _detail_url(project.pk, fifty_versions.pk),
            {"title": "Fifty versions updated"},
            format="json",
            **headers,
        )
    return one_response, fifty_response, one_queries, fifty_queries


def _upload_version_responses(api_client, headers, project, one_version, fifty_versions):
    with CaptureQueriesContext(connection) as one_queries:
        one_response = api_client.post(
            _detail_url(project.pk, one_version.pk, "upload-version/"),
            {"file": ContentFile(b"one upload", name="one-upload.zip")},
            format="multipart",
            **headers,
        )
    with CaptureQueriesContext(connection) as fifty_queries:
        fifty_response = api_client.post(
            _detail_url(project.pk, fifty_versions.pk, "upload-version/"),
            {"file": ContentFile(b"fifty upload", name="fifty-upload.zip")},
            format="multipart",
            **headers,
        )
    return one_response, fifty_response, one_queries, fifty_queries


@pytest.fixture
def api_client():
    """Provide an API client for real JWT authenticated deliverable mutations."""
    return APIClient()


@pytest.fixture
def actors():
    """Create the administrator and client actors for the project."""
    admin = User.objects.create_user(
        username="deliverable-budget-admin@example.com",
        email="deliverable-budget-admin@example.com",
        password=None,
        first_name="Deliverable",
        last_name="Budget Admin",
    )
    UserProfile.objects.create(
        user=admin,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
        profile_completed=True,
    )
    client = User.objects.create_user(
        username="deliverable-budget-client@example.com",
        email="deliverable-budget-client@example.com",
        password=None,
    )
    UserProfile.objects.create(
        user=client,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
        profile_completed=True,
        created_by=admin,
    )
    return admin, client


@pytest.fixture
def project(actors):
    """Create the project workspace before mutation query capture."""
    _, client = actors
    project = Project.objects.create(
        name="Deliverable detail budget project", client=client
    )
    DeliveryWorkspace.objects.get_or_create(project=project)
    return project


@pytest.fixture
def admin_headers(actors):
    """Issue the administrator access token before query capture starts."""
    admin, _ = actors
    return {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(admin)}"}


@pytest.fixture
def client_headers(actors):
    """Issue the client access token before query capture starts."""
    _, client = actors
    return {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(client)}"}


@pytest.mark.django_db
def test_admin_patch_keeps_version_history_reads_constant_as_history_grows(
    api_client,
    admin_headers,
    project,
    actors,
    record_property,
):
    """Falla si PATCH cuenta o carga autores de versiones una vez por historial."""
    admin, _ = actors
    one_version, fifty_versions, one_created, fifty_created = _deliverables_with_history(
        project, admin, label="version"
    )
    one_response, fifty_response, one_queries, fifty_queries = _patch_detail_responses(
        api_client, admin_headers, project, one_version, fifty_versions
    )

    one_body = one_response.json()
    fifty_body = fifty_response.json()
    record_property("query_count_one", len(one_queries))
    record_property("query_count_fifty", len(fifty_queries))
    assert (
        (one_response.status_code, one_body["title"], one_body["versions_count"]),
        (fifty_response.status_code, fifty_body["title"], fifty_body["versions_count"]),
    ) == ((200, "One version updated", 1), (200, "Fifty versions updated", 50))
    assert [entry["version_number"] for entry in one_body["versions"]] == [1]
    assert [entry["version_number"] for entry in fifty_body["versions"]] == list(
        range(50, 0, -1)
    )
    assert {entry["uploaded_by_name"] for entry in one_body["versions"]} == set(
        _version_names(one_created)
    )
    assert {entry["uploaded_by_name"] for entry in fifty_body["versions"]} == set(
        _version_names(fifty_created)
    )
    assert (
        len(_version_selects(one_queries)),
        len(_version_selects(fifty_queries)),
        _version_counts(one_queries),
        _version_counts(fifty_queries),
    ) == (
        MAX_DELIVERABLE_VERSION_QUERIES,
        MAX_DELIVERABLE_VERSION_QUERIES,
        [],
        [],
    )
    assert len(fifty_queries) == len(one_queries)


@pytest.mark.django_db
def test_admin_upload_keeps_version_history_reads_constant_as_history_grows(
    api_client,
    admin_headers,
    project,
    actors,
    record_property,
):
    """Falla si subir una versión vuelve a contar el historial o excluye la versión recién creada."""
    admin, _ = actors
    one_version, fifty_versions, _, _ = _deliverables_with_history(
        project, admin, label="upload"
    )
    one_response, fifty_response, one_queries, fifty_queries = _upload_version_responses(
        api_client, admin_headers, project, one_version, fifty_versions
    )

    one_body = one_response.json()
    fifty_body = fifty_response.json()
    record_property("query_count_one", len(one_queries))
    record_property("query_count_fifty", len(fifty_queries))
    assert (
        (
            one_response.status_code,
            one_body["current_version"],
            one_body["versions_count"],
            one_body["versions"][0]["version_number"],
        ),
        (
            fifty_response.status_code,
            fifty_body["current_version"],
            fifty_body["versions_count"],
            fifty_body["versions"][0]["version_number"],
        ),
    ) == ((201, 2, 2, 2), (201, 51, 51, 51))
    assert (
        one_body["versions"][0]["uploaded_by_name"],
        fifty_body["versions"][0]["uploaded_by_name"],
    ) == (
        admin.get_full_name() or admin.email,
        admin.get_full_name() or admin.email,
    )
    assert (
        len(_version_selects(one_queries)),
        len(_version_selects(fifty_queries)),
        _version_counts(one_queries),
        _version_counts(fifty_queries),
    ) == (
        MAX_DELIVERABLE_VERSION_QUERIES,
        MAX_DELIVERABLE_VERSION_QUERIES,
        [],
        [],
    )
    assert len(fifty_queries) == len(one_queries)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("method", "suffix", "payload_factory", "actor", "status_code", "error_field"),
    [
        ("post", "upload-version/", _invalid_design_file, "admin", 400, "file"),
        ("patch", "", _invalid_category_payload, "admin", 400, "category"),
        ("post", "upload-version/", _invalid_design_file, "client", 403, "detail"),
    ],
)
def test_rejected_deliverable_mutation_skips_version_history_reads(
    api_client,
    admin_headers,
    client_headers,
    project,
    actors,
    method,
    suffix,
    payload_factory,
    actor,
    status_code,
    error_field,
):
    """Falla si un rechazo carga historial o crea una versión antes de validar la solicitud."""
    admin, _ = actors
    deliverable = Deliverable.objects.create(
        project=project,
        uploaded_by=admin,
        title="Rejected mutation",
        category=Deliverable.CATEGORY_DESIGNS,
        file="deliverables/rejected.zip",
        current_version=1,
    )
    _deliverable_versions(deliverable, 1, start=1)
    headers = {"admin": admin_headers, "client": client_headers}[actor]
    request = getattr(api_client, method)

    with CaptureQueriesContext(connection) as queries:
        response = request(
            _detail_url(project.pk, deliverable.pk, suffix),
            payload_factory(),
            format="multipart",
            **headers,
        )

    deliverable.refresh_from_db()
    assert response.status_code == status_code
    assert error_field in response.json()
    assert deliverable.current_version == 1
    assert DeliverableVersion.objects.filter(deliverable=deliverable).count() == 1
    assert _version_selects(queries) == []
