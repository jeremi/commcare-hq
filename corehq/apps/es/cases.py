"""
CaseES
------

Here's an example getting pregnancy cases that are either still open or were
closed after May 1st.

.. code-block:: python

    from corehq.apps.es import cases as case_es

    q = (case_es.CaseES()
         .domain('testproject')
         .case_type('pregnancy')
         .OR(case_es.is_closed(False),
             case_es.closed_range(gte=datetime.date(2015, 05, 01))))
"""
from copy import copy
from datetime import datetime

from . import aggregations, filters
from .client import ElasticDocumentAdapter, create_document_adapter
from .es_query import HQESQuery
from .index.settings import IndexSettingsKey
from .transient_util import get_adapter_mapping


class CaseES(HQESQuery):
    index = 'cases'

    @property
    def builtin_filters(self):
        return [
            opened_range,
            closed_range,
            modified_range,
            server_modified_range,
            case_name,
            is_closed,
            case_type,
            owner,
            owner_type,
            user,
            user_ids_handle_unknown,
            opened_by,
            case_ids,
            active_in_range,
        ] + super(CaseES, self).builtin_filters


class ElasticCase(ElasticDocumentAdapter):

    settings_key = IndexSettingsKey.CASES

    @property
    def mapping(self):
        return get_adapter_mapping(self)

    def from_python(self, case):
        from corehq.form_processor.models.cases import CommCareCase
        if isinstance(case, dict):
            case_dict = copy(case)
        elif isinstance(case, CommCareCase):
            case_dict = case.to_json()
        else:
            raise TypeError(f"Unknown type {type(case)}")
        return self._from_dict(case_dict)

    def _from_dict(self, case):
        """
        Takes in case dict and applies required transformation to make it suitable for ES.
        The function is replica of ``transform_case_for_elasticsearch``
        In future all references to  ``transform_case_for_elasticsearch`` will be replaced by `from_python`

        :param case: an instance of ``dict`` which is ``CommcareCase.to_json()``
        """
        from corehq.pillows.utils import get_user_type

        if not case.get("owner_id"):
            if case.get("user_id"):
                case["owner_id"] = case["user_id"]

        case['owner_type'] = get_user_type(case.get("owner_id", None))
        case['inserted_at'] = datetime.utcnow().isoformat()

        if 'backend_id' not in case:
            case['backend_id'] = 'sql'

        return case.pop('_id'), case


case_adapter = create_document_adapter(
    ElasticCase,
    "hqcases_2016-03-04",
    "case",
)


def opened_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('opened_on', gt, gte, lt, lte)


def closed_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('closed_on', gt, gte, lt, lte)


def modified_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('modified_on', gt, gte, lt, lte)


def server_modified_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('server_modified_on', gt, gte, lt, lte)


def case_name(name):
    return filters.term('name.exact', name)


def is_closed(closed=True):
    return filters.term('closed', closed)


def case_type(type_):
    return filters.term('type.exact', type_)


def owner(owner_id):
    return filters.term('owner_id', owner_id)


def owner_type(owner_type):
    return filters.term('owner_type', owner_type)


def user(user_id):
    return filters.term('user_id', user_id)


def opened_by(user_id):
    return filters.term('opened_by', user_id)


def case_ids(case_ids):
    return filters.term('_id', case_ids)


def active_in_range(gt=None, gte=None, lt=None, lte=None):
    """Restricts cases returned to those with actions during the range"""
    return filters.nested(
        "actions",
        filters.date_range("actions.date", gt, gte, lt, lte)
    )


def user_ids_handle_unknown(user_ids):
    missing_users = None in user_ids

    user_ids = [_f for _f in user_ids if _f]

    if not missing_users:
        user_filter = user(user_ids)
    elif user_ids and missing_users:
        user_filter = filters.OR(
            user(user_ids),
            filters.missing('user_id'),
        )
    else:
        user_filter = filters.missing('user_id')
    return user_filter


def touched_total_aggregation(gt=None, gte=None, lt=None, lte=None):
    return aggregations.FilterAggregation(
        'touched_total',
        filters.AND(
            modified_range(gt, gte, lt, lte),
        )
    )


def open_case_aggregation(name='open_case', gt=None, gte=None, lt=None, lte=None):
    return aggregations.FilterAggregation(
        name,
        filters.AND(
            modified_range(gt, gte, lt, lte),
            is_closed(False),
        )
    )
