"""Huey registration imported from accounts.tasks for autodiscovery."""
from huey import crontab
from huey.contrib.djhuey import task, periodic_task


@task()
def process_ai_job(job_id):
    from accounts.services.platform_ai_jobs import process_job
    process_job(job_id)


@periodic_task(crontab(minute='*/10'))
def cleanup_ai_jobs():
    from accounts.services.platform_ai_jobs import cleanup_jobs
    cleanup_jobs()
