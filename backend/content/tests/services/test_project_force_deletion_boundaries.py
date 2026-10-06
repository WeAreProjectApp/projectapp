"""Boundary tests for project force deletion across shared records and JSON files."""

from datetime import date

import pytest
from django.core.files.base import ContentFile

from accounts.models import (
    BillingContextEvent,
    DeliveryPromptContext,
    DeliveryPromptSource,
    Deliverable,
    Project,
)
from content.models import (
    BusinessProposal,
    Document,
    DocumentFolder,
    DocumentThread,
    DocumentThreadItem,
    Linktree,
    LinktreeAsset,
    LinktreeTemplate,
    LinktreeTemplateVersion,
    ProposalApprovalFile,
)
from content.services.project_force_deletion import (
    ProjectForceDeleteError,
    force_delete_project,
    forced_deletion_preview,
)
from content.storage import get_private_storage


pytestmark = pytest.mark.django_db


@pytest.fixture
def target_project(make_client_profile):
    profile = make_client_profile(company='Boundary target client')
    return Project.objects.create(name='Boundary target project', client=profile.user)


def full_preview(project, actor):
    initial = forced_deletion_preview(project, actor=actor)
    delete_keys = [dependency['key'] for dependency in initial['dependencies']]
    return forced_deletion_preview(project, actor=actor, delete_keys=delete_keys)


def force_delete(project, actor):
    preview = full_preview(project, actor)
    force_delete_project(
        project.pk,
        actor=actor,
        confirmation='DELETE',
        impact_token=preview['impact_token'],
        delete_keys=preview['delete_keys'],
    )


def test_force_delete_blocks_version_used_by_another_card(superuser, target_project):
    """A hidden active-version backlink cannot detach an unrelated live card."""
    tree = Linktree.objects.create(project=target_project, handle='owned-version', name='Owned card')
    template = LinktreeTemplate.objects.create(name='Shared template', html='<main>Shared</main>')
    version = LinktreeTemplateVersion.objects.create(
        linktree=tree, template=template, profile_digest='a' * 64,
    )
    other_tree = Linktree.objects.create(
        handle='external-version', name='Other card', active_template_version=version,
    )
    preview = full_preview(target_project, superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(target_project.pk, actor=superuser,
                             confirmation='DELETE', impact_token=preview['impact_token'],
                             delete_keys=preview['delete_keys'])

    other_tree.refresh_from_db()
    assert error.value.code == 'project_force_delete_blocked'
    assert other_tree.active_template_version_id == version.pk
    assert LinktreeTemplateVersion.objects.filter(pk=version.pk).exists()
    assert Project.objects.filter(pk=target_project.pk).exists()


def test_force_delete_removes_thread_with_only_project_documents(superuser, target_project):
    """Fails if an exclusively owned document thread survives a project purge."""
    first = Document.objects.create(title='First project document', project=target_project)
    second = Document.objects.create(title='Second project document', project=target_project)
    thread = DocumentThread.objects.create(title='Exclusive project thread', created_by=superuser)
    first_item = DocumentThreadItem.objects.create(
        thread=thread,
        document=first,
        occurred_on=date(2026, 10, 4),
    )
    second_item = DocumentThreadItem.objects.create(
        thread=thread,
        document=second,
        occurred_on=date(2026, 10, 5),
    )

    force_delete(target_project, superuser)

    assert not DocumentThread.objects.filter(pk=thread.pk).exists()
    assert not DocumentThreadItem.objects.filter(pk=first_item.pk).exists()
    assert not DocumentThreadItem.objects.filter(pk=second_item.pk).exists()
    assert not Document.objects.filter(pk=first.pk).exists()
    assert not Document.objects.filter(pk=second.pk).exists()


def test_force_delete_blocks_thread_with_foreign_document(
    superuser, target_project, make_client_profile,
):
    """Fails if purging one project removes a document thread that contains another project's document."""
    other_profile = make_client_profile(company='Boundary other client')
    other_project = Project.objects.create(name='Boundary other project', client=other_profile.user)
    target_document = Document.objects.create(title='Target thread document', project=target_project)
    foreign_document = Document.objects.create(title='Foreign thread document', project=other_project)
    thread = DocumentThread.objects.create(title='Shared document thread', created_by=superuser)
    target_item = DocumentThreadItem.objects.create(
        thread=thread,
        document=target_document,
        occurred_on=date(2026, 10, 4),
    )
    foreign_item = DocumentThreadItem.objects.create(
        thread=thread,
        document=foreign_document,
        occurred_on=date(2026, 10, 5),
    )
    preview = full_preview(target_project, superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(
            target_project.pk,
            actor=superuser,
            confirmation='DELETE',
            impact_token=preview['impact_token'],
            delete_keys=preview['delete_keys'],
        )

    assert preview['can_delete'] is False
    assert error.value.code == 'project_force_delete_blocked'
    assert DocumentThread.objects.filter(pk=thread.pk).exists()
    assert DocumentThreadItem.objects.filter(pk=target_item.pk).exists()
    assert DocumentThreadItem.objects.filter(pk=foreign_item.pk).exists()
    assert Document.objects.filter(pk=target_document.pk).exists()
    assert Document.objects.filter(pk=foreign_document.pk).exists()


def test_force_delete_blocks_folder_with_foreign_project_document(
    superuser, target_project, make_client_profile,
):
    """Fails if a project folder purge removes a document assigned to another project."""
    other_profile = make_client_profile(company='Folder foreign client')
    other_project = Project.objects.create(name='Folder foreign project', client=other_profile.user)
    folder = DocumentFolder.objects.create(name='Target project folder', project=target_project)
    target_document = Document.objects.create(
        title='Target folder document',
        project=target_project,
        folder=folder,
    )
    foreign_document = Document.objects.create(
        title='Foreign folder document',
        project=other_project,
        folder=folder,
    )
    preview = full_preview(target_project, superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(
            target_project.pk,
            actor=superuser,
            confirmation='DELETE',
            impact_token=preview['impact_token'],
            delete_keys=preview['delete_keys'],
        )

    assert preview['can_delete'] is False
    assert error.value.code == 'project_force_delete_blocked'
    assert DocumentFolder.objects.filter(pk=folder.pk).exists()
    assert Document.objects.filter(pk=target_document.pk).exists()
    assert Document.objects.filter(pk=foreign_document.pk).exists()
    assert Project.objects.filter(pk=target_project.pk).exists()
    assert Project.objects.filter(pk=other_project.pk).exists()


def test_force_delete_preserves_managed_client_root(superuser, target_project):
    """Fails if project deletion removes the independent document root owned by its client."""
    client_root = DocumentFolder.objects.create(
        name='Client managed root',
        client_user=target_project.client,
        managed_client=target_project.client,
    )

    force_delete(target_project, superuser)

    client_root.refresh_from_db()
    assert client_root.managed_client_id == target_project.client_id
    assert client_root.client_user_id == target_project.client_id


def test_force_delete_removes_linktree_asset_json_paths(
    superuser, target_project, django_capture_on_commit_callbacks,
):
    """Fails if project-owned Linktree asset JSON paths leave private image bytes after commit."""
    tree = Linktree.objects.create(
        project=target_project,
        handle='boundary-asset',
        name='Boundary asset',
    )
    storage = get_private_storage()
    density_one = storage.save('force-delete-assets/one.png', ContentFile(b'one'))
    density_two = storage.save('force-delete-assets/two.png', ContentFile(b'two'))
    asset = LinktreeAsset.objects.create(
        linktree=tree,
        key='hero',
        image={'paths': {'1': density_one, '2': density_two}},
    )

    with django_capture_on_commit_callbacks(execute=True):
        force_delete(target_project, superuser)

    assert not Linktree.objects.filter(pk=tree.pk).exists()
    assert not LinktreeAsset.objects.filter(pk=asset.pk).exists()
    assert not storage.exists(density_one)
    assert not storage.exists(density_two)


def test_force_delete_removes_version_json_paths_while_preserving_template(
    superuser, target_project, django_capture_on_commit_callbacks,
):
    """Fails if version JSON files remain after deletion or the retained template is destroyed."""
    tree = Linktree.objects.create(
        project=target_project,
        handle='boundary-version',
        name='Boundary version',
    )
    template = LinktreeTemplate.objects.create(
        owner=tree,
        client=target_project.client,
        name='Boundary retained template',
        manifest={'assets': []},
        html='<main>Boundary template</main>',
    )
    storage = get_private_storage()
    asset_path = storage.save('force-delete-versions/asset.png', ContentFile(b'asset'))
    screenshot_path = storage.save('force-delete-versions/screenshot.png', ContentFile(b'screenshot'))
    version = LinktreeTemplateVersion.objects.create(
        linktree=tree,
        template=template,
        assets={'hero': {'paths': {'1': asset_path}}},
        screenshots={'480': screenshot_path},
        profile_digest='a' * 64,
    )

    with django_capture_on_commit_callbacks(execute=True):
        force_delete(target_project, superuser)

    template.refresh_from_db()
    assert not LinktreeTemplateVersion.objects.filter(pk=version.pk).exists()
    assert template.owner_id is None
    assert template.name == 'Boundary retained template'
    assert not storage.exists(asset_path)
    assert not storage.exists(screenshot_path)


def test_force_delete_preserves_proposal_approval_file_boundary(superuser, target_project):
    """Fails if forced deletion destroys the immutable file that approved a commercial project package."""
    deliverable = Deliverable.objects.create(
        project=target_project,
        title='Approved package deliverable',
        uploaded_by=superuser,
    )
    proposal = BusinessProposal.objects.create(
        title='Approved package proposal',
        client_name='Boundary target client',
        deliverable=deliverable,
    )
    approval = ProposalApprovalFile.objects.create(
        proposal=proposal,
        project=target_project,
        deliverable=deliverable,
        source_key='approved-contract',
        title='Approved contract',
        document_type='contract',
        filename='approved-contract.pdf',
        file=ContentFile(b'approved package bytes', name='approved-contract.pdf'),
        sha256='a' * 64,
        size=22,
        created_by=superuser,
    )
    preview = full_preview(target_project, superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(
            target_project.pk,
            actor=superuser,
            confirmation='DELETE',
            impact_token=preview['impact_token'],
            delete_keys=preview['delete_keys'],
        )

    approval.file.open('rb')
    proposal.refresh_from_db()
    assert error.value.code == 'project_force_delete_blocked'
    assert Project.objects.filter(pk=target_project.pk).exists()
    assert Deliverable.objects.filter(pk=deliverable.pk).exists()
    assert proposal.deliverable_id == deliverable.pk
    assert ProposalApprovalFile.objects.filter(pk=approval.pk).exists()
    assert approval.file.read() == b'approved package bytes'


def test_force_delete_preserves_billing_context_event(superuser, target_project):
    """Fails if forced deletion removes the immutable before-and-after billing decision history."""
    event = BillingContextEvent.objects.create(
        project=target_project,
        actor=superuser,
        operation='assign_billing_context',
        reason='Preserve billing responsibility',
        before={'project': target_project.pk, 'scope': 'previous'},
        after={'project': target_project.pk, 'scope': 'current'},
    )
    preview = full_preview(target_project, superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(
            target_project.pk,
            actor=superuser,
            confirmation='DELETE',
            impact_token=preview['impact_token'],
            delete_keys=preview['delete_keys'],
        )

    event.refresh_from_db()
    assert error.value.code == 'project_force_delete_blocked'
    assert event.project_id == target_project.pk
    assert event.before == {'project': target_project.pk, 'scope': 'previous'}
    assert event.after == {'project': target_project.pk, 'scope': 'current'}


def test_force_delete_preserves_private_prompt_source(superuser, target_project):
    """Fails if force deletion erases a captured authoring context or its private source bytes."""
    context = DeliveryPromptContext.objects.create(
        project=target_project,
        actor=superuser,
        mode='guides',
        request_id='force-delete-prompt-boundary',
        fingerprint='b' * 64,
        captured_version=1,
        prompt='Use the captured source as the approved reference.',
        manifest_sha256='c' * 64,
    )
    source = DeliveryPromptSource.objects.create(
        context=context,
        source_key='private-approved-source',
        title='Private approved source',
        origin='document',
        source_id='source-1',
        role='primary',
        status='included',
        file=ContentFile(b'private prompt source', name='private-source.pdf'),
        filename='private-source.pdf',
        sha256='d' * 64,
    )
    preview = full_preview(target_project, superuser)

    with pytest.raises(ProjectForceDeleteError) as error:
        force_delete_project(
            target_project.pk,
            actor=superuser,
            confirmation='DELETE',
            impact_token=preview['impact_token'],
            delete_keys=preview['delete_keys'],
        )

    source.file.open('rb')
    assert error.value.code == 'project_force_delete_blocked'
    assert DeliveryPromptContext.objects.filter(pk=context.pk).exists()
    assert DeliveryPromptSource.objects.filter(pk=source.pk).exists()
    assert source.file.read() == b'private prompt source'


def test_force_delete_keeps_json_path_reused_by_retained_template(
    superuser, target_project, django_capture_on_commit_callbacks,
):
    """Fails if cleanup removes JSON image bytes still referenced by a retained template."""
    tree = Linktree.objects.create(
        project=target_project,
        handle='boundary-shared-json',
        name='Boundary shared JSON',
    )
    storage = get_private_storage()
    shared_path = storage.save(
        'force-delete-shared/template-asset.png',
        ContentFile(b'retained template asset'),
    )
    asset = LinktreeAsset.objects.create(
        linktree=tree,
        key='hero',
        image={'paths': {'1': shared_path}},
    )
    template = LinktreeTemplate.objects.create(
        name='Template retaining JSON asset',
        manifest={'assets': []},
        html='<main>Retained JSON template</main>',
        assets={'hero': {'paths': {'1': shared_path}}},
    )

    with django_capture_on_commit_callbacks(execute=True):
        force_delete(target_project, superuser)

    template.refresh_from_db()
    assert not LinktreeAsset.objects.filter(pk=asset.pk).exists()
    assert template.assets == {'hero': {'paths': {'1': shared_path}}}
    assert storage.exists(shared_path)
