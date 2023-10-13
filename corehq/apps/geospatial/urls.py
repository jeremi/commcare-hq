from django.conf.urls import re_path as url

from .dispatchers import CaseManagementMapDispatcher
from .views import (
    GeoPolygonView,
    GeospatialConfigPage,
    GPSCaptureView,
    MapboxOptimizationV2,
    geospatial_default,
    get_paginated_cases_or_users_without_gps,
    get_users_with_gps,
    mapbox_routing_status,
)

urlpatterns = [
    url(r'^$', geospatial_default, name='geospatial_default'),
    url(r'^edit_geo_polygon/$', GeoPolygonView.as_view(),
        name=GeoPolygonView.urlname),
    url(r'^mapbox_routing/$',
        MapboxOptimizationV2.as_view(),
        name=MapboxOptimizationV2.urlname),
    url(r'^mapbox_routing_status/(?P<poll_id>[\w-]+)/',
        mapbox_routing_status,
        name="mapbox_routing_status"),
    url(r'^settings/$', GeospatialConfigPage.as_view(),
        name=GeospatialConfigPage.urlname),
    url(r'^gps_capture/json/$', get_paginated_cases_or_users_without_gps,
        name='get_paginated_cases_or_users_without_gps'),
    url(r'^gps_capture/$', GPSCaptureView.as_view(), name=GPSCaptureView.urlname),
    url(r'^users/json/$', get_users_with_gps, name='get_users_with_gps'),

    CaseManagementMapDispatcher.url_pattern(),
]
