from uuid import uuid4
from weakref import WeakKeyDictionary

from django.utils.translation import gettext as _

from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.models import FixtureTypeField
from corehq.apps.fixtures.upload.const import DELETE_HEADER
from corehq.apps.fixtures.upload.failure_messages import FAILURE_MESSAGES
from corehq.apps.fixtures.utils import is_identifier_invalid
from corehq.util.workbook_json.excel import (
    WorkbookJSONError,
    WorksheetNotFound,
)
from corehq.util.workbook_json.excel import get_workbook as excel_get_workbook

from ..models import (
    FieldList,
    FixtureDataItem,
    FixtureDataType,
    FixtureItemField,
)


def get_workbook(file_or_filename):
    return _FixtureWorkbook(file_or_filename)


class _FixtureWorkbook(object):
    """
    Helper class for working with the fixture workbook
    """

    def __init__(self, file_or_filename):
        try:
            self.workbook = excel_get_workbook(file_or_filename)
        except WorkbookJSONError as e:
            raise FixtureUploadError([str(e)])
        self.meta = WeakKeyDictionary()

    def get_types_sheet(self):
        try:
            return self.workbook.get_worksheet(title='types')
        except WorksheetNotFound:
            raise FixtureUploadError([FAILURE_MESSAGES['no_types_sheet']])

    def get_data_sheet(self, data_type_tag):
        return self.workbook.get_worksheet(data_type_tag)

    def get_all_type_sheets(self):
        type_sheets = []
        seen_tags = set()
        for number_of_fixtures, dt in enumerate(self.get_types_sheet()):
            table_definition = _FixtureTableDefinition.from_row(dt)
            if table_definition.table_id in seen_tags:
                raise FixtureUploadError([
                    _(FAILURE_MESSAGES['duplicate_tag'])
                    .format(tag=table_definition.table_id)])

            seen_tags.add(table_definition.table_id)
            type_sheets.append(table_definition)
        return type_sheets

    def iter_tables(self, domain):
        for sheet in self.get_all_type_sheets():
            if sheet.delete:
                yield Deleted(sheet.table_id)
                continue
            yield FixtureDataType(
                _id=uuid4().hex,
                domain=domain,
                tag=sheet.table_id,
                is_global=sheet.is_global,
                fields=sheet.fields,
                item_attributes=sheet.item_attributes,
            )

    def iter_rows(self, data_type, sort_keys):
        data_items = list(self.get_data_sheet(data_type.tag))
        type_fields = data_type.fields
        sort_key = -1
        for i, di in enumerate(data_items):
            sort_key = max(sort_keys.get(di['UID'], i), sort_key + 1)
            item = FixtureDataItem(
                domain=data_type.domain,
                data_type_id=data_type._id,
                fields={
                    field.field_name: _process_item_field(field, di)
                    for field in type_fields
                },
                item_attributes=di.get('property', {}),
                sort_key=sort_key,
            )
            self.meta[item] = di
            yield item

    def get_uid(self, obj):
        return self.meta.get(obj, {}).get('UID')


class Deleted:
    def __init__(self, key):
        self.key = key


class _FixtureTableDefinition(object):

    def __init__(self, table_id, fields, item_attributes, is_global, uid, delete):
        self.table_id = table_id
        self.fields = fields
        self.item_attributes = item_attributes
        self.is_global = is_global
        self.uid = uid
        self.delete = delete

    @classmethod
    def from_row(cls, row_dict):
        tag = row_dict.get('table_id') or row_dict.get('tag')
        if tag is None:
            raise FixtureUploadError([
                _(FAILURE_MESSAGES['has_no_column']).format(column_name='table_id')])
        if is_identifier_invalid(tag):
            raise FixtureUploadError([
                _(FAILURE_MESSAGES['invalid_table_id']).format(tag=tag)
            ])

        field_names = row_dict.get('field')
        item_attributes = row_dict.get('property')

        if field_names is None and item_attributes is None:
            raise FixtureUploadError([_(FAILURE_MESSAGES['neither_fields_nor_attributes']).format(tag=tag)])

        field_names = [] if field_names is None else field_names
        item_attributes = [] if item_attributes is None else item_attributes

        def _get_field_properties(prop_key):
            properties = []
            if prop_key in row_dict and 'property' in row_dict[prop_key]:
                properties = row_dict[prop_key]["property"]
                if not isinstance(properties, list):
                    error_message = _(FAILURE_MESSAGES["wrong_property_syntax"]).format(
                        prop_key=prop_key,
                    )
                    raise FixtureUploadError([error_message])
            return properties

        def _get_field_is_indexed(prop_key):
            is_indexed = False
            if prop_key in row_dict and 'is_indexed' in row_dict[prop_key]:
                is_indexed = row_dict[prop_key]["is_indexed"]
                if not isinstance(is_indexed, bool):
                    error_message = _(FAILURE_MESSAGES["wrong_index_syntax"]).format(
                        prop_key=prop_key,
                    )
                    raise FixtureUploadError([error_message])
            return is_indexed

        def is_number(text):
            text = str(text)
            try:
                float(text)
                return True
            except ValueError:
                return False

        for i, field_name in enumerate(field_names):
            if is_number(field_name):
                message = _(FAILURE_MESSAGES['invalid_field_name_numerical']).format(
                    i=i + 1,
                    val=field_name,
                )
                raise FixtureUploadError([message])

        fields = [
            FixtureTypeField(
                field_name=field,
                properties=_get_field_properties('field {count}'.format(count=i + 1)),
                is_indexed=_get_field_is_indexed('field {count}'.format(count=i + 1)),
            ) for i, field in enumerate(field_names)
        ]

        return cls(
            table_id=tag,
            fields=fields,
            item_attributes=item_attributes,
            is_global=row_dict.get('is_global', False),
            uid=row_dict.get('UID'),
            delete=(row_dict.get(DELETE_HEADER) or '').lower() == 'y',
        )


def _process_item_field(field, data_item):
    """Processes field_list of a data item from fields in the uploaded excel sheet.

    Returns FieldList
    """
    if not field.properties:
        return FieldList(
            field_list=[FixtureItemField(
                # str to cast ints and multi-language strings
                field_value=str(data_item['field'][field.field_name]),
                properties={}
            )]
        )

    field_list = []
    field_prop_combos = data_item['field'][field.field_name]
    prop_combo_len = len(field_prop_combos)
    prop_dict = data_item[field.field_name]
    for x in range(0, prop_combo_len):
        fix_item_field = FixtureItemField(
            field_value=str(field_prop_combos[x]),
            properties={prop: str(prop_dict[prop][x]) for prop in prop_dict}
        )
        field_list.append(fix_item_field)
    return FieldList(field_list=field_list)
