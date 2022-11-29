from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from pillowtop.tests.utils import TEST_INDEX_INFO

from corehq.apps.es.client import (
    Tombstone,
    create_document_adapter,
    get_client,
    manager,
)
from corehq.apps.es.management.commands.elastic_sync_multiplexed import (
    ESSyncUtil,
    IndexNotMultiplexedException,
    human_readable_seconds,
)
from corehq.apps.es.registry import deregister, register
from corehq.apps.es.tests.utils import TestDoc, TestDocumentAdapter
from corehq.apps.es.transient_util import _DOC_ADAPTERS_BY_INDEX

COMMAND_NAME = 'elastic_sync_multiplexed'


class ReIndexTestHelper:
    index = 'reindex-primary'
    type = 'test_doc'
    alias = 'test_reindex_util'
    secondary_index = 'reindex-secondary'
    cname = 'test_reindex'
    mapping = TestDocumentAdapter.mapping

    def setup_indexes(self):
        if not manager.index_exists(f'test_{self.index}'):
            manager.index_create(f'test_{self.index}')
            manager.index_put_mapping(f'test_{self.index}', self.type, self.mapping)
        # manager.index_put_alias(f'test_{self.index}', self.alias)
        # es = get_client()
        # initialize_index_and_mapping(es, self)
        if not manager.index_exists(f'test_{self.secondary_index}'):
            manager.index_create(f'test_{self.secondary_index}')
            manager.index_put_mapping(f'test_{self.secondary_index}', self.type, self.mapping)

    def remove_index(self):
        manager.index_delete(f'test_{self.index}')
        manager.index_delete(f'test_{self.secondary_index}')


class TestElasticSyncMultiplexedCommand(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.adapter = create_document_adapter(
            TestDocumentAdapter,
            ReIndexTestHelper.index,
            ReIndexTestHelper.type,
            secondary=ReIndexTestHelper.secondary_index
        )

        _DOC_ADAPTERS_BY_INDEX[ReIndexTestHelper.index] = cls.adapter
        cls.es = get_client()
        register(ReIndexTestHelper, ReIndexTestHelper.cname)
        # registering another test index
        register(TEST_INDEX_INFO, TEST_INDEX_INFO.hq_index_name)
        cls.util = ESSyncUtil()

    @classmethod
    def tearDownClass(cls):
        _DOC_ADAPTERS_BY_INDEX.pop(ReIndexTestHelper.index)
        deregister(ReIndexTestHelper.cname)
        deregister(TEST_INDEX_INFO)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        ReIndexTestHelper().setup_indexes()

    def tearDown(self):
        ReIndexTestHelper().remove_index()
        return super().tearDown()

    def test_invalid_index_canonical_raises(self):
        with self.assertRaises(CommandError):
            call_command(COMMAND_NAME, 'start', 'random_alias')

    def test_not_mutliplexed_index_raises(self):
        with self.assertRaises(IndexNotMultiplexedException):
            call_command(COMMAND_NAME, 'start', TEST_INDEX_INFO.hq_index_name)

    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.check_task_progress')
    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.ESSyncUtil.perform_cleanup')
    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.ESSyncUtil.start_reindex_in_es')
    def test_pass_multiplexed_index_raise_no_errors(self, sync_mock, cleanup_mock, _):
        sync_mock.return_value = {
            "task": "task_key"
        }
        call_command(COMMAND_NAME, 'start', 'cases')

    def test_reindex_command_copies_all_documents(self):
        self.adapter.primary.index(TestDoc('key_2', 'val'))
        self.adapter.primary.index(TestDoc('key', 'value'))

        call_command(COMMAND_NAME, 'start', ReIndexTestHelper.cname)
        self.es.indices.refresh(self.adapter.secondary.index_name)

        self.assertEqual(
            self.adapter.secondary.count({}),
            self.adapter.primary.count({})
        )

    def test_get_correct_adapter_with_cname(self):
        adapter = self.util.get_adapter('test_reindex')
        self.assertEqual(adapter.index_name, f"test_{ReIndexTestHelper.index}")

    def test_get_all_tombstones(self):
        _index_tombstones(self.adapter.secondary, 10)
        es_tombstone_ids = self.util._get_tombstone_ids(self.adapter.secondary)
        es_tombstone_ids.sort()
        self.assertEqual(
            [str(i) for i in list(range(1, 10))],
            es_tombstone_ids
        )

    def test_delete_tombstones(self):
        _index_tombstones(self.adapter.secondary, 10)
        self.util.delete_tombstones(self.adapter.secondary)
        self.assertEqual(
            self.util._get_tombstone_ids(self.adapter.secondary),
            []
        )

    def test_human_readable_seconds(self):
        duration = human_readable_seconds(5)
        self.assertEqual(duration, '5 seconds')

        duration = human_readable_seconds(5.1 * 60)
        self.assertEqual(duration, '5 minutes')

        duration = human_readable_seconds(5.8 * 60 * 60)
        self.assertEqual(duration, '5 hours')

        duration = human_readable_seconds(5.1 * 60 * 60 * 24)
        self.assertEqual(duration, '5 days')


def _index_tombstones(secondary_adapter, quantity):
    tombstone_ids = [str(i) for i in list(range(1, quantity))]
    for tombstone_id in tombstone_ids:
        id, doc = secondary_adapter.from_python(Tombstone(tombstone_id))
        secondary_adapter._index(id, doc, True)
