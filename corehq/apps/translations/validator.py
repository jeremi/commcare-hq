from __future__ import absolute_import
from __future__ import unicode_literals

import ghdiff
from memoized import memoized
from six.moves import zip

from corehq.apps.translations.app_translations import (
    get_bulk_app_sheet_headers,
    get_bulk_app_sheet_rows,
    get_unicode_dicts,
)
from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.translations.generators import SKIP_TRANSFEX_STRING, AppTranslationsGenerator

COLUMNS_TO_COMPARE = {
    'module_and_form': ['Type', 'sheet_name'],
    'module': ['case_property', 'list_or_detail'],
    'form': ['label'],
}
# return from ghdiff in case of no differences
NO_GHDIFF_MESSAGE = ghdiff.diff([], [], css=False)


class UploadedTranslationsValidator(object):
    """
    this compares the excel sheet uploaded with translations with what would be generated
    with current app state and flags any discrepancies found between the two
    """
    def __init__(self, app, uploaded_workbook, lang_prefix='default_'):
        self.app = app
        self.uploaded_workbook = uploaded_workbook
        self.headers = None
        self.expected_rows = None
        self.lang_prefix = lang_prefix
        self.default_language_column = self.lang_prefix + self.app.default_language
        self.app_translation_generator = AppTranslationsGenerator(
            self.app.domain, self.app.get_id, None, self.app.default_language, self.app.default_language,
            self.lang_prefix)

    def _generate_expected_headers_and_rows(self):
        self.headers = {h[0]: h[1] for h in get_bulk_app_sheet_headers(self.app)}
        self.expected_rows = get_bulk_app_sheet_rows(
            self.app,
            exclude_module=lambda module: SKIP_TRANSFEX_STRING in module.comment,
            exclude_form=lambda form: SKIP_TRANSFEX_STRING in form.comment
        )

    @memoized
    def _get_header_index(self, sheet_name, header):
        for index, _column_name in enumerate(self.headers[sheet_name]):
            if _column_name == header:
                return index

    def _filter_rows(self, for_type, expected_rows, sheet_name):
        if for_type == 'form':
            return self.app_translation_generator._filter_invalid_rows_for_form(
                expected_rows,
                self.app_translation_generator.sheet_name_to_module_or_form_type_and_id[sheet_name].id,
                self._get_header_index(sheet_name, 'label')
            )
        elif for_type == 'module':
            return self.app_translation_generator._filter_invalid_rows_for_module(
                expected_rows,
                self.app_translation_generator.sheet_name_to_module_or_form_type_and_id[sheet_name].id,
                self._get_header_index(sheet_name, 'case_property'),
                self._get_header_index(sheet_name, 'list_or_detail'),
                self._get_header_index(sheet_name, self.default_language_column)
            )
        elif for_type == 'module_and_form':
            return expected_rows
        assert False, "Unexpected type"

    def _compare_sheet(self, sheet_name, uploaded_rows, for_type):
        """
        :param uploaded_rows: dict
        :param for_type: type of sheet, module_and_forms, module, form
        :return: diff generated by ghdiff or None
        """
        columns_to_compare = COLUMNS_TO_COMPARE[for_type] + [self.default_language_column]
        expected_rows = self._filter_rows(for_type, self.expected_rows[sheet_name], sheet_name)

        iterate_on = [expected_rows, uploaded_rows]
        parsed_expected_rows = []
        parsed_uploaded_rows = []
        for i, (expected_row, uploaded_row) in enumerate(zip(*iterate_on), 2):
            parsed_expected_row = [uploaded_row.get(column_name) for column_name in columns_to_compare]
            parsed_uploaded_row = [expected_row[self._get_header_index(sheet_name, column_name)]
                                   for column_name in columns_to_compare]
            parsed_expected_rows.append(parsed_expected_row)
            parsed_uploaded_rows.append(parsed_uploaded_row)
        expected_rows_as_string = '\n'.join([', '.join(row) for row in parsed_expected_rows])
        uploaded_rows_as_string = '\n'.join([', '.join(row) for row in parsed_uploaded_rows])
        diff = ghdiff.diff(expected_rows_as_string, uploaded_rows_as_string, css=False)
        if diff == NO_GHDIFF_MESSAGE:
            return None
        return diff

    def compare(self):
        msgs = {}
        self._generate_expected_headers_and_rows()
        for sheet in self.uploaded_workbook.worksheets:
            sheet_name = sheet.worksheet.title
            # if sheet is not in the expected rows, ignore it. This can happen if the module/form sheet is excluded
            # from transifex integration
            if sheet_name not in self.expected_rows:
                continue
            rows = get_unicode_dicts(sheet)
            if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
                error_msgs = self._compare_sheet(sheet_name, rows, 'module_and_form')
            elif 'module' in sheet_name and 'form' not in sheet_name:
                error_msgs = self._compare_sheet(sheet_name, rows, 'module')
            elif 'module' in sheet_name and 'form' in sheet_name:
                error_msgs = self._compare_sheet(sheet_name, rows, 'form')
            else:
                raise Exception("Got unexpected sheet name %s" % sheet_name)
            if error_msgs:
                msgs[sheet_name] = error_msgs
        return msgs
