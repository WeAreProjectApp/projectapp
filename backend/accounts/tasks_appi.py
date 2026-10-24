"""Provider I/O runs outside request workers; tests use Huey immediate mode."""
from huey import crontab
from huey.contrib.djhuey import db_task, db_periodic_task


@db_task()
def process_appi_turn(turn_id):
    from accounts.services.appi import process
    process(turn_id)


@db_periodic_task(crontab(minute='*/5'))
def cleanup_appi_history():
    from accounts.services.appi import cleanup
    cleanup()
