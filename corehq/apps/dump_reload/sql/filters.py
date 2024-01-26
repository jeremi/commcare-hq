from abc import ABCMeta, abstractmethod

from django.db.models import Q
from django.db.models.fields.related import ForeignKey

from dimagi.utils.chunked import chunked

from corehq.apps.dump_reload.util import get_model_class
from corehq.form_processor.models.cases import CommCareCase
from corehq.sql_db.util import (
    get_db_aliases_for_partitioned_query,
    paginate_query,
)
from corehq.util.queries import queryset_to_iterator


class DomainFilter(metaclass=ABCMeta):
    @abstractmethod
    def get_filters(self, domain_name, db_alias=None):
        """Return a list of filters. Each filter will be applied to a queryset independently
        of the others."""
        raise NotImplementedError()

    def count(self, domain_name):
        return None


class SimpleFilter(DomainFilter):
    def __init__(self, filter_kwarg):
        self.filter_kwarg = filter_kwarg

    def get_filters(self, domain_name, db_alias):
        return [Q(**{self.filter_kwarg: domain_name})]


class ManyFilters(DomainFilter):
    """
    Filter by multiple filter kwargs. Filters are ANDed
    """
    def __init__(self, *filter_kwargs):
        assert filter_kwargs, 'Please set one of more filter_kwargs'
        self.filter_kwargs = filter_kwargs

    def get_filters(self, domain_name, db_alias):
        filter_ = Q(**{self.filter_kwargs[0]: domain_name})
        for filter_kwarg in self.filter_kwargs[1:]:
            filter_ &= Q(**{filter_kwarg: domain_name})
        return [filter_]


class UsernameFilter(DomainFilter):
    def __init__(self, usernames=None):
        self.usernames = usernames

    def count(self, domain_name):
        return len(self.usernames) if self.usernames is not None else None

    def get_filters(self, domain_name, db_alias=None):
        """
        :return: A generator of filters each filtering for at most 500 users.
        """
        from corehq.apps.users.dbaccessors import get_all_usernames_by_domain
        if self.usernames:
            usernames = self.usernames
        else:
            usernames = get_all_usernames_by_domain(domain_name)
        for chunk in chunked(usernames, 500):
            filter = Q()
            for username in chunk:
                filter |= Q(username__iexact=username)
            yield filter


class IDFilter(DomainFilter):
    def __init__(self, field, ids, chunksize=1000):
        self.field = field
        self.ids = ids
        self.chunksize = chunksize

    def count(self, domain_name):
        return len(self.get_ids(domain_name))

    def get_ids(self, domain_name, db_alias=None):
        return self.ids

    def get_filters(self, domain_name, db_alias=None):
        for chunk in chunked(self.get_ids(domain_name, db_alias=db_alias), self.chunksize):
            query_kwarg = '{}__in'.format(self.field)
            yield Q(**{query_kwarg: chunk})


class UserIDFilter(IDFilter):
    def __init__(self, user_id_field, include_web_users=True):
        super().__init__(user_id_field, None)
        self.include_web_users = include_web_users

    def get_ids(self, domain_name, db_alias=None):
        from corehq.apps.users.dbaccessors import get_all_user_ids_by_domain
        return get_all_user_ids_by_domain(domain_name, include_web_users=self.include_web_users)


class CaseIDFilter(IDFilter):
    def __init__(self, model_label, case_field='case'):
        _, self.model_cls = get_model_class(model_label)
        try:
            field_obj, = [f for f in self.model_cls._meta.fields if f.name == case_field]
            assert isinstance(field_obj, ForeignKey)
            assert field_obj.remote_field.model == CommCareCase
        except Exception:
            raise ValueError(
                "CaseIDFilter only supports models with a foreign key relationship to CommCareCase"
            )
        super().__init__(case_field, None, chunksize=500)

    def count(self, domain_name):
        count = 0
        for db in get_db_aliases_for_partitioned_query():
            count += self.model_cls.objects.using(db).filter(case__domain=domain_name).count()
        return count

    def get_ids(self, domain_name, db_alias=None):
        assert db_alias, "Expected db_alias to be defined for CaseIDFilter"
        source = 'dump_domain_data'
        query = Q(domain=domain_name)
        for row in paginate_query(db_alias, CommCareCase, query, values=['case_id'], load_source=source):
            # there isn't a good way to return flattened results
            yield row[0]


class UnfilteredModelIteratorBuilder(object):
    def __init__(self, model_label):
        self.model_label = model_label
        self.domain = self.model_class = self.db_alias = None

    def prepare(self, domain, model_class, db_alias):
        self.domain = domain
        self.model_class = model_class
        self.db_alias = db_alias
        return self

    def _base_queryset(self):
        assert self.domain and self.model_class and self.db_alias, "Unprepared IteratorBuilder"
        objects = self.model_class._default_manager
        return objects.using(self.db_alias)

    def querysets(self):
        yield self._base_queryset()

    def count(self):
        return sum(q.count() for q in self.querysets())

    def iterators(self):
        for queryset in self.querysets():
            yield queryset_to_iterator(queryset, self.model_class, ignore_ordering=True)

    def build(self, domain, model_class, db_alias):
        return self.__class__(self.model_label).prepare(domain, model_class, db_alias)


class FilteredModelIteratorBuilder(UnfilteredModelIteratorBuilder):
    def __init__(self, model_label, filter, paginate_by={}):
        """
        :param paginate_by: optional dictionary of {field: conditional, ...} (e.g., {'username': 'gt'})
        NOTE: the order of keys matters in this dictionary, as it dictates sort order.
        """
        super(FilteredModelIteratorBuilder, self).__init__(model_label)
        self.filter = filter
        self.paginate_by = paginate_by

    def build(self, domain, model_class, db_alias):
        return self.__class__(self.model_label, self.filter).prepare(domain, model_class, db_alias)

    def count(self):
        count = self.filter.count(self.domain)
        if count is not None:
            return count
        return super(FilteredModelIteratorBuilder, self).count()

    def querysets(self):
        queryset = self._base_queryset()
        filters = self.filter.get_filters(self.domain, db_alias=self.db_alias)
        for filter_ in filters:
            yield queryset.filter(filter_)


class UniqueFilteredModelIteratorBuilder(FilteredModelIteratorBuilder):
    def iterators(self):
        def _unique(iterator):
            seen = set()
            for model in iterator:
                if model.pk not in seen:
                    seen.add(model.pk)
                    yield model

        querysets = self.querysets()
        for querysets in querysets:
            yield _unique(querysets)
