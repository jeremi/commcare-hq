from django.http import Http404

from couchdbkit import ResourceNotFound

from corehq import toggles
from corehq.apps.accounting.models import Subscription, SoftwarePlanEdition
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.privileges import DAILY_SAVED_EXPORT, EXCEL_DASHBOARD
from corehq.toggles import MESSAGE_LOG_METADATA


def is_occurrence_deleted(last_occurrences, app_ids_and_versions):
    is_deleted = True
    for app_id, version in app_ids_and_versions.items():
        occurrence = last_occurrences.get(app_id)
        if occurrence is not None and occurrence >= version:
            is_deleted = False
            break
    return is_deleted


def domain_has_excel_dashboard_access(domain):
    return domain_has_privilege(domain, EXCEL_DASHBOARD)


def domain_has_daily_saved_export_access(domain):
    return domain_has_privilege(domain, DAILY_SAVED_EXPORT)


def get_export(export_type, domain, export_id=None, username=None):
    from corehq.apps.export.models import (
        FormExportInstance,
        CaseExportInstance,
        SMSExportInstance,
        SMSExportDataSchema
    )
    if export_type == 'form':
        try:
            return FormExportInstance.get(export_id)
        except ResourceNotFound:
            raise Http404()
    elif export_type == 'case':
        try:
            return CaseExportInstance.get(export_id)
        except ResourceNotFound:
            raise Http404()
    elif export_type == 'sms':
        if not username:
            raise Exception("Username needed to ensure permissions")
        include_metadata = MESSAGE_LOG_METADATA.enabled(username)
        return SMSExportInstance._new_from_schema(
            SMSExportDataSchema.get_latest_export_schema(domain, include_metadata)
        )
    raise Exception("Unexpected export type received %s" % export_type)


def get_default_export_settings_for_user(username, domain):
    """
    Only creates settings if the the subscription level supports it
    Currently only available to Enterprise accounts with the DEFAULT_EXPORT_SETTINGS FF enabled
    """
    if not toggles.DEFAULT_EXPORT_SETTINGS.enabled(username):
        return None

    settings = None
    current_subscription = Subscription.get_active_subscription_by_domain(domain)
    # currently only available for enterprise customers
    supported_editions = [SoftwarePlanEdition.ENTERPRISE]
    if current_subscription.plan_version.plan.edition in supported_editions:
        from corehq.apps.export.models import DefaultExportSettings
        settings = DefaultExportSettings.objects.get_or_create(account=current_subscription.account)[0]

    return settings
