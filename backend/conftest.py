import pytest
from django.core.management import call_command


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Load the synthetic sample ONCE, committed, into the test database.

    It has to be committed (not inside a test transaction) because the guarded SQL tool opens a
    second connection as the read-only role, which cannot see uncommitted rows.
    """
    with django_db_blocker.unblock():
        call_command("seed_sample")
