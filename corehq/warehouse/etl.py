import os

from django.db import connections
from django.conf import settings
from django.template import Context, engines

from corehq.warehouse.utils import django_batch_records
from corehq.sql_db.routers import db_for_read_write


class CustomSQLETLMixin(object):

    @classmethod
    def dependencies(cls):
        raise NotImplementedError

    @classmethod
    def load(cls):
        '''
        Bulk loads records for a dim or fact table from
        their corresponding dependencies
        '''
        database = db_for_read_write(cls)
        with connections[database].cursor() as cursor:
            cursor.execute(cls._sql_query_template(cls.slug))

    @classmethod
    def _table_context(cls):
        '''
        Get a dict of slugs to table name mapping
        :returns: Dict of slug to table_name
        {
            <slug>: <table_name>,
            ...
        }
        '''
        from corehq.warehouse.models import get_cls_by_slug

        context = {cls.slug: cls._meta.db_table}
        for dep in cls.dependencies():
            dep_cls = get_cls_by_slug(dep)
            context[dep] = dep_cls._meta.db_table
        return context

    @classmethod
    def _sql_query_template(cls, template_name):
        path = os.path.join(
            settings.BASE_DIR,
            'corehq',
            'warehouse',
            'transforms',
            'sql',
            '{}.sql'.format(template_name),
        )

        return _render_template(path, cls._table_context())


class CouchToDjangoETLMixin(object):

    @classmethod
    def field_mapping(cls):
        # Map source model fields to staging table fields
        # ( <source field>, <staging field> )
        raise NotImplementedError

    @classmethod
    def record_iter(cls, start_datetime, end_datetime):
        raise NotImplementedError

    def load(cls, start_datetime, end_datetime):
        record_iter = cls.raw_record_iter(start_datetime, end_datetime)

        django_batch_records(cls, record_iter, cls.field_mapping())


def _render_template(path, context):
    with open(path) as f:
        template_string = f.read()

    template = engines['django'].from_string(template_string)
    return template.render(Context(context))
