import functools
import hashlib
import inspect
from inspect import isfunction
import logging
from django.core.cache import get_cache
from corehq.util.soft_assert.api import soft_assert

logger = logging.getLogger('quickcache')


class TieredCache(object):
    """
    Tries a number of caches in increasing order.
    Caches should be ordered with faster, more local caches at the beginning
    and slower, more shared caches towards the end

    Relies on each of the caches' default timeout;
    TieredCache.set doesn't accept a timeout parameter

    """
    def __init__(self, caches):
        self.caches = caches

    def get(self, key, default=None):
        missed = []
        for cache in self.caches:
            content = cache.get(key, default=Ellipsis)
            if content is not Ellipsis:
                for missed_cache in missed:
                    missed_cache.set(key, content)
                logger.debug('missed caches: {}'.format([c.__class__.__name__
                                                         for c in missed]))
                logger.debug('hit cache: {}'.format(cache.__class__.__name__))
                return content
            else:
                missed.append(cache)
        return default

    def set(self, key, value):
        for cache in self.caches:
            cache.set(key, value)

    def delete(self, key):
        for cache in self.caches:
            cache.delete(key)


class QuickCache(object):
    def __init__(self, fn, vary_on, cache):
        self.fn = fn
        self.cache = cache
        self.prefix = '{}.{}'.format(
            fn.__name__[:40] + (fn.__name__[40:] and '..'),
            self._hash(inspect.getsource(fn), 8)
        )

        arg_names = inspect.getargspec(self.fn).args
        if not isfunction(vary_on):
            vary_on = [part.split('.') for part in vary_on]
            vary_on = [(part[0], tuple(part[1:])) for part in vary_on]
            for arg, attrs in vary_on:
                if arg not in arg_names:
                    raise ValueError(
                        'We cannot vary on "{}" because the function {} has '
                        'no such argument'.format(arg, self.fn.__name__)
                    )

        self.encoding_assert = soft_assert(
            to=['{}@{}'.format('skelly', 'dimagi.com')],
            fail_if_debug=False,
            skip_frames=5,
        )

        self.vary_on = vary_on

    def __call__(self, *args, **kwargs):
        logger.debug('checking caches for {}'.format(self.fn.__name__))
        key = self.get_cache_key(*args, **kwargs)
        logger.debug(key)
        content = self.cache.get(key, default=Ellipsis)
        if content is Ellipsis:
            logger.debug('cache miss, calling {}'.format(self.fn.__name__))
            content = self.fn(*args, **kwargs)
            self.cache.set(key, content)
        return content

    def clear(self, *args, **kwargs):
        key = self.get_cache_key(*args, **kwargs)
        self.cache.delete(key)

    @staticmethod
    def _hash(value, length=32):
        return hashlib.md5(value).hexdigest()[-length:]

    def _serialize_for_key(self, value):
        if isinstance(value, basestring):
            # Unicode and string values should generate the same key since users generally
            # intend them to mean the same thing. If a use case for differentiating
            # them presents itself add a 'lenient_strings=False' option to allow
            # the user to explicitly request the different behaviour.
            if isinstance(value, unicode):
                encoded = value.encode('utf-8')
            else:
                try:
                    encoded = value.decode('utf-8').encode('utf-8')
                except UnicodeDecodeError:
                    self.encoding_assert(False, 'Non-utf8 encoded string used as cache vary on')
                    encoded = value
            return 'u' + self._hash(encoded)
        elif isinstance(value, bool):
            return 'b' + str(int(value))
        elif isinstance(value, (int, long, float)):
            return 'n' + str(value)
        elif isinstance(value, (list, tuple)):
            return 'L' + self._hash(
                ','.join(map(self._serialize_for_key, value)))
        elif isinstance(value, set):
            return 'S' + self._hash(
                ','.join(sorted(map(self._serialize_for_key, value))))
        else:
            raise ValueError('Bad type "{}": {}'.format(type(value), value))

    def get_cache_key(self, *args, **kwargs):
        callargs = inspect.getcallargs(self.fn, *args, **kwargs)
        values = []
        if isfunction(self.vary_on):
            values = self.vary_on(*args, **kwargs)
        else:
            for arg_name, attrs in self.vary_on:
                value = callargs[arg_name]
                for attr in attrs:
                    value = getattr(value, attr)
                values.append(value)
        args_string = ','.join(self._serialize_for_key(value)
                               for value in values)
        if len(args_string) > 150:
            args_string = 'H' + self._hash(args_string)
        return 'quickcache.{}/{}'.format(self.prefix, args_string)


def quickcache(vary_on, timeout=None, memoize_timeout=None, cache=None,
               helper_class=QuickCache):
    """
    An easy "all-purpose" cache decorator

    Examples:
        - caching a singleton function, refresh every 5 minutes

            @quickcache([], timeout=5 * 60)
            def get_config_from_db():
                # ...

        - vary on the arguments of a function

            @quickcache(['request.couch_user._rev'], timeout=24 * 60 * 60)
            def domains_for_user(request):
                return [Domain.get_by_name(domain)
                        for domain in request.couch_user.domains]

          now as soon as request.couch_user._rev has changed,
          the function will be recomputed

    Features:
        - In addition to caching in the default shared cache,
          quickcache caches in memory for 10 seconds
          (conceptually the length of a single request).
          This can be overridden to a different number with memoize_timeout.

        - In addition to varying on the arguments and the name of the function,
          quickcache will also make sure to vary
          on the _source code_ of your function.
          That way if you change the behavior of the function, there won't be
          any stale cache when you deploy.

        - Can vary on any number of the function's parameters

        - Does not by default vary on all function parameters.
          This is because it is not in general obvious what it means
          to vary on an object, for example.

        - Allows you to vary on an attribute of an object,
          multiple attrs of the same object, attrs of attrs of an object, etc

    """
    if cache and timeout:
        raise ValueError('You can only use timeout '
                         'when not overriding the cache')

    timeout = timeout or 5 * 60
    memoize_timeout = memoize_timeout or 10

    if cache is None:
        cache = TieredCache([get_cache('locmem://', timeout=memoize_timeout),
                             get_cache('default', timeout=timeout)])

    def decorator(fn):
        helper = helper_class(fn, vary_on=vary_on, cache=cache)

        @functools.wraps(fn)
        def inner(*args, **kwargs):
            return helper(*args, **kwargs)

        inner.clear = helper.clear
        inner.get_cache_key = helper.get_cache_key
        inner.prefix = helper.prefix

        return inner

    return decorator
