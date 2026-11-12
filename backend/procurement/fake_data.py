def clear_examples():
    from procurement.models import Activity, Alert, Classification, Delivery, Notification, Opportunity, SavedSearch, ScheduleSlot, SyncRun
    for model in (Activity, Notification, Delivery, Classification, Alert, SavedSearch, ScheduleSlot, SyncRun, Opportunity):
        model.objects.all().delete()
