import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest import mock

from django.test import TestCase

from couchdbkit import ResourceConflict

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.tests.utils import create_enterprise_permissions
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, UserReportingMetadataStaging, WebUser
from corehq.apps.users.tasks import (
    apply_correct_demo_mode_to_loadtest_user,
    update_domain_date,
)
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es import case_search_adapter
from corehq.form_processor.models import CommCareCase
from corehq.apps.users.tasks import (
    _process_reporting_metadata_staging,
    remove_users_test_cases,
)
from corehq.apps.reports.util import domain_copied_cases_by_owner
from corehq.apps.hqcase.case_helper import CaseCopier


class TasksTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()

        # Set up domains
        cls.domain = create_domain('test')
        cls.mirror_domain = create_domain('mirror')
        create_enterprise_permissions('web@web.com', 'test', ['mirror'])

        # Set up user
        cls.web_user = WebUser.create(
            domain='test',
            username='web',
            password='secret',
            created_by=None,
            created_via=None,
        )

        cls.today = datetime.today().date()
        cls.last_week = cls.today - timedelta(days=7)

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.domain.delete()
        cls.mirror_domain.delete()
        super().tearDownClass()

    def _last_accessed(self, user, domain):
        domain_membership = user.get_domain_membership(domain, allow_enterprise=False)
        if domain_membership:
            return domain_membership.last_accessed
        return None

    def test_update_domain_date_web_user(self):
        self.assertIsNone(self._last_accessed(self.web_user, self.domain.name))
        update_domain_date(self.web_user.user_id, self.domain.name)
        self.web_user = WebUser.get_by_username(self.web_user.username)
        self.assertEqual(self._last_accessed(self.web_user, self.domain.name), self.today)

    def test_update_domain_date_web_user_mirror(self):
        # Mirror domain access shouldn't be updated because user doesn't have a real membership
        self.assertIsNone(self._last_accessed(self.web_user, self.mirror_domain.name))
        update_domain_date(self.web_user.user_id, self.mirror_domain.name)
        self.web_user = WebUser.get_by_username(self.web_user.username)
        self.assertIsNone(self._last_accessed(self.web_user, self.mirror_domain.name))


class TestLoadtestUserIsDemoUser(TestCase):

    def test_set_loadtest_factor_on_demo_user(self):
        with _get_user(loadtest_factor=5, is_demo_user=True) as user:
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertTrue(user.is_demo_user)
            self.assertFalse(user.is_loadtest_user)

    def test_set_loadtest_factor_on_non_demo_user(self):
        with _get_user(loadtest_factor=5, is_demo_user=False) as user:
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertTrue(user.is_demo_user)
            self.assertTrue(user.is_loadtest_user)

    def test_unset_loadtest_factor_on_demo_user(self):
        with _get_user(loadtest_factor=None, is_demo_user=True) as user:
            self.assertFalse(user.is_loadtest_user)
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertTrue(user.is_demo_user)
            self.assertFalse(user.is_loadtest_user)

    def test_unset_loadtest_factor_on_non_demo_user(self):
        with _get_user(loadtest_factor=None, is_demo_user=False) as user:
            user.is_loadtest_user = True
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertFalse(user.is_demo_user)
            self.assertFalse(user.is_loadtest_user)


@contextmanager
def _get_user(loadtest_factor, is_demo_user):
    domain_name = 'test-domain'
    domain_obj = create_domain(domain_name)
    just_now = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    user = CommCareUser.wrap({
        'domain': domain_name,
        'username': f'testy@{domain_name}.commcarehq.org',
        'loadtest_factor': loadtest_factor,
        'is_demo_user': is_demo_user,
        'user_data': {},
        'date_joined': just_now,
    })
    user.save()
    try:
        yield user

    finally:
        user.delete(domain_name, None)
        domain_obj.delete()


@es_test(requires=[case_search_adapter])
class TestRemoveUsersTestCases(TestCase):

    domain = "test-domain"

    @classmethod
    def setUpClass(cls):
        super()
        cls.user = CommCareUser.create(cls.domain, 'user', 'password', None, None)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=None, deleted_by=None)
        super()

    def test_only_copied_cases_gets_removed(self):
        _ = self._send_case_to_es(owner_id=self.user.user_id)
        test_case = self._send_case_to_es(owner_id=self.user.user_id, is_copy=True)

        remove_users_test_cases(self.domain, [self.user.user_id])
        case_ids = domain_copied_cases_by_owner(self.domain, self.user.user_id)

        self.assertEqual(case_ids, [test_case.case_id])

    def _send_case_to_es(
        self,
        owner_id=None,
        is_copy=False,
    ):
        case_json = {}
        if is_copy:
            case_json[CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME] = 'case_id'

        case = CommCareCase(
            case_id=uuid.uuid4().hex,
            domain=self.domain,
            owner_id=owner_id,
            type='case_type',
            case_json=case_json,
            modified_on=datetime.utcnow(),
            server_modified_on=datetime.utcnow(),
        )
        case.save()

        case_search_adapter.index(case, refresh=True)
        return case


@mock.patch.object(UserReportingMetadataStaging, 'process_record')
class TestProcessReportingMetadataStaging(TestCase):

    def test_record_is_deleted_if_processed_successfully(self, mock_process_record):
        record = UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')
        self.assertTrue(UserReportingMetadataStaging.objects.get(id=record.id))

        _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 1)
        self.assertEqual(UserReportingMetadataStaging.objects.all().count(), 0)

    def test_record_is_not_deleted_if_not_processed_successfully(self, mock_process_record):
        record = UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')
        mock_process_record.side_effect = Exception

        _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 1)
        self.assertTrue(UserReportingMetadataStaging.objects.get(id=record.id))

    def test_process_record_is_retried_if_resource_conflict_raised(self, mock_process_record):
        """
        I'm not sure why this is necessary, but the original introduction of this links back to
        https://github.com/dimagi/commcare-hq/pull/27138 which also doesn't have context since
        all of the related links are no longer accessible. If we are able to remove this, that
        would be great.
        """
        # Simulate the scenario where the first attempt to process a record raises ResourceConflict
        # but the next attempt succeeds
        mock_process_record.side_effect = [ResourceConflict, None]
        UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')

        _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 2)
        self.assertEqual(UserReportingMetadataStaging.objects.all().count(), 0)

    def test_processed_records_are_limited_to_chunk_size(self, mock_process_record):
        for _ in range(5):
            UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')

        _process_reporting_metadata_staging(chunk_size=3)

        # 5 records were created, 3 were processed, 2 should be left over
        self.assertEqual(mock_process_record.call_count, 3)
        self.assertEqual(UserReportingMetadataStaging.objects.all().count(), 2)

    def test_subsequent_records_are_still_processed_if_general_exception_encountered(self, mock_process_record):
        for _ in range(2):
            UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')
        # raise exception first to ensure subsequent record(s) are processed
        mock_process_record.side_effect = [Exception, None]

        _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 2)
        self.assertEqual(UserReportingMetadataStaging.objects.all().count(), 1)

    def setUp(self):
        super().setUp()
        self.user = CommCareUser.create('test-domain', 'test-username', 'abc123', None, None)
        self.addCleanup(self.user.delete, 'test-domain', deleted_by=None)
