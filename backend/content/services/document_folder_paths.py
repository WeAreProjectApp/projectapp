"""Shared display paths for document folders."""


def folder_path(folder) -> str:
    """Return the folder ancestry and name with the document-manager separator."""
    names = [ancestor.name for ancestor in folder.get_ancestors()] + [folder.name]
    return ' / '.join(names)
