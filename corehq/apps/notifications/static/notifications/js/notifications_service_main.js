/**
 * Document ready handling for pages that use notifications/js/notifications_service.js
 */

hqDefine('notifications/js/notifications_service_main', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'notifications/js/notifications_service',
    'analytix/js/google',
], function (
    $,
    initialPageData,
    notificationsService,
    googleAnalytics
) {
    var initNotifications = function () {
        var url;
        try {
            url = initialPageData.reverse('notifications_service');
        } catch (e) {
            // if URL isn't provided, bail
            return;
        }

        var csrfToken = $("#csrfTokenContainer").val();
        notificationsService.setRMI(url, csrfToken);
        notificationsService.initService('#js-settingsmenu-notifications');
        notificationsService.relativelyPositionUINotify('.alert-ui-notify-relative');
        notificationsService.initUINotify('.alert-ui-notify');

        $(document).on('click', '.notification-link', function () {
            googleAnalytics.track.event('Notification', 'Opened Message', this.href);
        });
        googleAnalytics.track.click($('#notification-icon'), 'Notification', 'Clicked Bell Icon');
    };
    $(document).ready(initNotifications);
    return {
        'initNotifications': initNotifications,
    };
});
