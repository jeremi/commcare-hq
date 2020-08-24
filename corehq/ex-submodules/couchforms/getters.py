from django.utils.datastructures import MultiValueDictKeyError
from couchforms.const import (
    EMPTY_PAYLOAD_ERROR,
    MAGIC_PROPERTY,
    MULTIPART_EMPTY_PAYLOAD_ERROR,
    MULTIPART_INVALID_ATTACHMENT_FILE_EXTENSION_ERROR,
    MULTIPART_INVALID_SUBMISSION_FILE_EXTENSION_ERROR,
    MULTIPART_FILENAME_ERROR,
    PERMITTED_FORM_SUBMISSION_FILE_EXTENSIONS,
    SUPPORTED_MEDIA_FILE_EXTENSIONS,
)
import logging
from datetime import datetime
from django.conf import settings

from dimagi.utils.parsing import string_to_utc_datetime
from dimagi.utils.web import get_ip, get_site_domain


__all__ = ['get_path', 'get_instance_and_attachment',
           'get_location', 'get_received_on', 'get_date_header',
           'get_submit_ip', 'get_last_sync_token', 'get_openrosa_headers']


def get_path(request):
    return request.path


class MultimediaBug(Exception):
    pass


def get_instance_and_attachment(request):
    try:
        return request._instance_and_attachment
    except AttributeError:
        pass
    attachments = {}
    if request.META['CONTENT_TYPE'].startswith('multipart/form-data'):
        # ODK submission; of the form
        # $ curl --form 'xml_submission_file=@form.xml' $URL
        if list(request.POST):
            raise MultimediaBug("Received a submission with POST.keys()")

        try:
            instance_file = request.FILES[MAGIC_PROPERTY]
        except MultiValueDictKeyError:
            instance = MULTIPART_FILENAME_ERROR
        else:
            if not _valid_form_xml_file(instance_file):
                instance = MULTIPART_INVALID_SUBMISSION_FILE_EXTENSION_ERROR
            else:
                instance = instance_file.read()
                for key, item in request.FILES.items():
                    if key != MAGIC_PROPERTY:
                        if not _valid_attachment_file(item):
                            instance = MULTIPART_INVALID_ATTACHMENT_FILE_EXTENSION_ERROR
                            attachments.clear()
                            break
                        attachments[key] = item
        if not instance:
            instance = MULTIPART_EMPTY_PAYLOAD_ERROR
    else:
        # j2me and touchforms; of the form
        # $ curl --data '@form.xml' $URL
        instance = request.body
        if not instance:
            instance = EMPTY_PAYLOAD_ERROR
    request._instance_and_attachment = (instance, attachments)
    return instance, attachments


def _valid_form_xml_file(file):
    return _valid_file_extension(file, PERMITTED_FORM_SUBMISSION_FILE_EXTENSIONS)


def _valid_file_extension(file, permitted_extensions):
    # validate that file has only one extension and that is a permitted one
    try:
        file_extension = file.name.split('.', 1)[1]
    except IndexError:
        return False
    return file_extension in permitted_extensions


def _valid_attachment_file(file):
    return _valid_file_extension(file, SUPPORTED_MEDIA_FILE_EXTENSIONS)


def get_location(request=None):
    # this is necessary, because www.commcarehq.org always uses https,
    # but is behind a proxy that won't necessarily look like https
    if hasattr(settings, "OVERRIDE_LOCATION"):
        return settings.OVERRIDE_LOCATION
    if request is None:
        prefix = settings.DEFAULT_PROTOCOL
    else:
        prefix = "https" if request.is_secure() else "http"
    return "%s://%s" % (prefix, get_site_domain())


def get_received_on(request):
    received_on = request.META.get('HTTP_X_SUBMIT_TIME')
    if received_on:
        return string_to_utc_datetime(received_on)
    else:
        return None


def get_date_header(request):
    date_header = request.META.get('HTTP_DATE')
    if date_header:
        # comes in as:
        # Mon, 11 Apr 2011 18:24:43 GMT
        # goes out as:
        # 2011-04-11T18:24:43Z
        try:
            date = datetime.strptime(date_header, "%a, %d %b %Y %H:%M:%S GMT")
            date = datetime.strftime(date, "%Y-%m-%dT%H:%M:%SZ")
        except:
            logging.error((
                "Receiver app: incoming submission has a date header "
                "that we can't parse: '%s'"
            ) % date_header)
            date = date_header
        date_header = date
    else:
        date_header = None
    return date_header


def get_submit_ip(request):
    return get_ip(request)


def get_last_sync_token(request):
    return getattr(request, 'last_sync_token', None)


def get_openrosa_headers(request):
    return getattr(request, 'openrosa_headers', None)
