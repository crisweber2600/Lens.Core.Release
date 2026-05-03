import pytest

# These tests define the red-phase contract for the future complete-ops.py.
# They are marked xfail until complete-ops.py is implemented by the
# lens-dev-new-codebase-complete dev phase.
_NOT_YET_IMPLEMENTED = "complete-ops.py is not yet implemented"


@pytest.mark.xfail(reason=_NOT_YET_IMPLEMENTED, strict=True)
def test_check_preconditions_pass():
    """Feature in dev phase with retrospective.md present should return status:pass."""
    raise NotImplementedError(_NOT_YET_IMPLEMENTED)


@pytest.mark.xfail(reason=_NOT_YET_IMPLEMENTED, strict=True)
def test_check_preconditions_warn_no_retrospective():
    """Feature in dev phase without retrospective.md should return status:warn and retrospective_skipped:True."""
    raise NotImplementedError(_NOT_YET_IMPLEMENTED)


@pytest.mark.xfail(reason=_NOT_YET_IMPLEMENTED, strict=True)
def test_check_preconditions_fail_wrong_phase():
    """Feature in a non-completable phase should return status:fail."""
    raise NotImplementedError(_NOT_YET_IMPLEMENTED)


@pytest.mark.xfail(reason=_NOT_YET_IMPLEMENTED, strict=True)
def test_finalize_dry_run():
    """finalize --dry-run should return planned_changes without writing governance files."""
    raise NotImplementedError(_NOT_YET_IMPLEMENTED)


@pytest.mark.xfail(reason=_NOT_YET_IMPLEMENTED, strict=True)
def test_finalize_archives_feature():
    """finalize should set phase=complete, mark the index archived, and write summary.md."""
    raise NotImplementedError(_NOT_YET_IMPLEMENTED)


@pytest.mark.xfail(reason=_NOT_YET_IMPLEMENTED, strict=True)
def test_archive_status_archived():
    """A completed feature should return archived:True from archive-status."""
    raise NotImplementedError(_NOT_YET_IMPLEMENTED)


@pytest.mark.xfail(reason=_NOT_YET_IMPLEMENTED, strict=True)
def test_archive_status_not_archived():
    """A non-complete feature should return archived:False from archive-status."""
    raise NotImplementedError(_NOT_YET_IMPLEMENTED)


@pytest.mark.xfail(reason=_NOT_YET_IMPLEMENTED, strict=True)
def test_prerequisite_missing_degradation():
    """finalize should proceed with warnings when optional prerequisite artifacts are absent."""
    raise NotImplementedError(_NOT_YET_IMPLEMENTED)
