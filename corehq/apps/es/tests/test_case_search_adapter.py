from django.test import TestCase

from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.tests.utils import create_case
from corehq.pillows.case_search import transform_case_for_elasticsearch


@es_test(requires=[case_search_adapter], setup_class=True)
class TestFromPythonInCaseSearch(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'from-python-casesearch-tests'
        cls.case = create_case(cls.domain, save=True)

    def test_from_python_works_with_case_objects(self):
        case_search_adapter.from_python(self.case)

    def test_from_python_works_with_case_dicts(self):
        case_search_adapter.from_python(self.case.to_json())

    def test_from_python_raises_for_other_objects(self):
        self.assertRaises(TypeError, case_search_adapter.from_python, set)

    def test_from_python_is_same_as_transform_case_for_es(self):
        # this test can be safely removed when transform_case_for_elasticsearch is removed
        case_id, case = case_search_adapter.from_python(self.case)
        case['_id'] = case_id
        case.pop('@indexed_on')
        case_transformed_dict = transform_case_for_elasticsearch(self.case.to_json())
        case_transformed_dict.pop('@indexed_on')
        self.assertEqual(case_transformed_dict, case)

    def test_index_can_handle_case_dicts(self):
        case_dict = self.case.to_json()
        case_search_adapter.index(case_dict, refresh=True)
        self.addCleanup(case_search_adapter.delete, self.case.case_id)

        case = case_search_adapter.to_json(self.case)
        case.pop('@indexed_on')
        es_case = case_search_adapter.search({})['hits']['hits'][0]['_source']
        es_case.pop('@indexed_on')
        self.assertEqual(es_case, case)

    def test_index_can_handle_case_objects(self):
        case_search_adapter.index(self.case, refresh=True)
        self.addCleanup(case_search_adapter.delete, self.case.case_id)

        case = case_search_adapter.to_json(self.case)
        case.pop('@indexed_on')
        es_case = case_search_adapter.search({})['hits']['hits'][0]['_source']
        es_case.pop('@indexed_on')
        self.assertEqual(es_case, case)
