import logging
from types import FunctionType

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from .models import NavigationEventAudit

log = logging.getLogger(__name__)


class AuditMiddleware(MiddlewareMixin):

    def __init__(self, get_response=None):
        """
        Audit middleware needs to be enabled on site after the login/user info
        is instantiated on the request object.
        """
        super(AuditMiddleware, self).__init__(get_response)
        self.active = any(getattr(settings, name, False) for name in [
            "AUDIT_ALL_VIEWS", "AUDIT_VIEWS", "AUDIT_MODULES"
        ])
        self.audit_modules = tuple(settings.AUDIT_MODULES)
        self.audit_views = set(settings.AUDIT_VIEWS)

        if not getattr(settings, 'AUDIT_ALL_VIEWS', False):
            if not self.audit_views:
                log.warning(
                    "You do not have the AUDIT_VIEWS settings variable setup. "
                    "If you want to setup central view call audit events, "
                    "please add the property and populate it with fully "
                    "qualified view names."
                )
            elif not self.audit_modules:
                log.warning(
                    "You do not have the AUDIT_MODULES settings variable "
                    "setup. If you want to setup central module audit events, "
                    "please add the property and populate it with module names."
                )

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Simple centralized manner to audit views without having to modify the
        requisite code.  This is an alternate way to manage audit events rather
        than using the decorator.
        """
        if self.active and self.should_audit(view_func):
            audit_doc = NavigationEventAudit.audit_view(request, request.user, view_func, view_kwargs)
            if audit_doc:
                setattr(request, 'audit_doc', audit_doc)
        return None

    def process_response(self, request, response):
        """
        For auditing views, we need to verify on the response whether or not the
        permission was granted, we infer this from the status code. Update the
        audit document set in the request object.

        We also need to add the user field when it was not initially inferred from the sessionid,
        such as when using Api Key, Basic Auth, Digest Auth, or HMAC auth.
        """
        audit_doc = getattr(request, 'audit_doc', None)
        if audit_doc:
            if not audit_doc.user:
                if hasattr(request, 'audit_user'):
                    audit_doc.user = request.audit_user
                elif hasattr(request, 'couch_user'):
                    audit_doc.user = request.couch_user.username
            audit_doc.status_code = response.status_code
            audit_doc.save()
        return response

    def should_audit(self, view_func):
        fn = view_func if isinstance(view_func, FunctionType) else view_func.__class__
        fqview = f"{view_func.__module__}.{fn.__name__}"
        if (fqview == "django.contrib.staticfiles.views.serve"
                or fqview == "debug_toolbar.views.debug_media"):
            return False
        return (
            getattr(settings, 'AUDIT_ALL_VIEWS', False)
            or fqview in self.audit_views
            or fqview.startswith(self.audit_modules)
            or (
                getattr(settings, "AUDIT_ADMIN_VIEWS", True)
                and fqview.startswith(('django.contrib.admin', 'reversion.admin'))
            )
        )
