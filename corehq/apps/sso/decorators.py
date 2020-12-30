from functools import wraps

from django.http import Http404
from onelogin.saml2.auth import OneLogin_Saml2_Auth

from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils import get_saml2_config


def identity_provider_required(view_func):
    @wraps(view_func)
    def _inner(request, idp_slug, *args, **kwargs):
        _add_idp_to_request_or_404(request, idp_slug)
        return view_func(request, idp_slug, *args, **kwargs)
    return _inner


def use_saml2_auth(view_func):
    @wraps(view_func)
    def _inner(request, idp_slug, *args, **kwargs):
        _add_idp_to_request_or_404(request, idp_slug)
        request.saml2_auth = OneLogin_Saml2_Auth(request, get_saml2_config(request.idp))
        return view_func(request, idp_slug, *args, **kwargs)
    return _inner


def _add_idp_to_request_or_404(request, idp_slug):
    idp = IdentityProvider.objects.filter(slug=idp_slug).first()
    if not idp:
        raise Http404()
    request.idp = idp
