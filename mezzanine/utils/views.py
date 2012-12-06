
from datetime import datetime, timedelta

from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.template import RequestContext
from django.template.response import TemplateResponse

from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module

from mezzanine.conf import settings
from mezzanine.utils.sites import has_site_permission


def is_editable(obj, request):
    """
    Returns ``True`` if the object is editable for the request. First
    check for a custom ``editable`` handler on the object, otherwise
    use the logged in user and check change permissions for the
    object's model.
    """
    if hasattr(obj, "is_editable"):
        return obj.is_editable(request)
    else:
        perm = obj._meta.app_label + "." + obj._meta.get_change_permission()
        return (request.user.is_authenticated() and
                has_site_permission(request.user) and
                request.user.has_perm(perm))


def load_request_filter(path):
    i = path.rfind('.')
    module, attr = path[:i], path[i + 1:]
    try:
        mod = import_module(module)
    except ImportError as e:
        raise ImproperlyConfigured(
                'Error importing content filter %s: "%s"' % (path, e))
    except ValueError:
        raise ImproperlyConfigured(
                'Error importing content filters. ' +
                'Is REQUEST_FILTERS a correctly defined list or tuple?')
    try:
        cls = getattr(mod, attr)
    except AttributeError:
        raise ImproperlyConfigured(
                'Module "%s" does not define a "%s" content filter' % (
                        module, attr))
    return cls()


def get_request_filters():
    request_filters = []
    for request_filter_path in settings.REQUEST_FILTERS:
        request_filters.append(load_request_filter(
                request_filter_path))
    return request_filters


def is_spam(request, form, url):
    for filter in get_request_filters():
        if filter.is_spam(request, form, url):
            return True


def paginate(objects, page_num, per_page, max_paging_links):
    """
    Return a paginated page for the given objects, giving it a custom
    ``visible_page_range`` attribute calculated from ``max_paging_links``.
    """
    paginator = Paginator(objects, per_page)
    try:
        page_num = int(page_num)
    except ValueError:
        page_num = 1
    try:
        objects = paginator.page(page_num)
    except (EmptyPage, InvalidPage):
        objects = paginator.page(paginator.num_pages)
    page_range = objects.paginator.page_range
    if len(page_range) > max_paging_links:
        start = min(objects.paginator.num_pages - max_paging_links,
            max(0, objects.number - (max_paging_links / 2) - 1))
        page_range = page_range[start:start + max_paging_links]
    objects.visible_page_range = page_range
    return objects


def render(request, templates, dictionary=None, context_instance=None,
           **kwargs):
    """
    Mimics ``django.shortcuts.render`` but uses a TemplateResponse for
    ``mezzanine.core.middleware.TemplateForDeviceMiddleware``
    """
    dictionary = dictionary or {}
    if context_instance:
        context_instance.update(dictionary)
    else:
        context_instance = RequestContext(request, dictionary)
    return TemplateResponse(request, templates, context_instance, **kwargs)


def set_cookie(response, name, value, expiry_seconds=None, secure=False):
    """
    Set cookie wrapper that allows number of seconds to be given as the
    expiry time, and ensures values are correctly encoded.
    """
    if expiry_seconds is None:
        expiry_seconds = 365 * 24 * 60 * 60
    expires = datetime.strftime(datetime.utcnow() +
                                timedelta(seconds=expiry_seconds),
                                "%a, %d-%b-%Y %H:%M:%S GMT")
    value = value.encode("utf-8")
    response.set_cookie(name, value, expires=expires, secure=secure)
