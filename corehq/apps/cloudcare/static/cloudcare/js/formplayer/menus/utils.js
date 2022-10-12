/*global Backbone */

hqDefine("cloudcare/js/formplayer/menus/utils", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        Kissmetrics = hqImport("analytix/js/kissmetrix"),
        ProgressBar = hqImport("cloudcare/js/formplayer/layout/views/progress_bar"),
        QueryView = hqImport("cloudcare/js/formplayer/menus/views/query"),
        Toggles = hqImport("hqwebapp/js/toggles"),
        Utils = hqImport("cloudcare/js/formplayer/utils/utils"),
        Views = hqImport("cloudcare/js/formplayer/menus/views");

    var recordPosition = function (position) {
        sessionStorage.locationLat = position.coords.latitude;
        sessionStorage.locationLon = position.coords.longitude;
        sessionStorage.locationAltitude = position.coords.altitude;
        sessionStorage.locationAccuracy = position.coords.accuracy;
    };

    var handleLocationRequest = function (optionsFromLastRequest) {
        var success = function (position) {
            hqRequire(["cloudcare/js/formplayer/menus/controller"], function (MenusController) {
                FormplayerFrontend.regions.getRegion('loadingProgress').empty();
                recordPosition(position);
                MenusController.selectMenu(optionsFromLastRequest);
            });
        };

        var error = function (err) {
            FormplayerFrontend.regions.getRegion('loadingProgress').empty();
            FormplayerFrontend.trigger('showError',
                getErrorMessage(err) +
                "Without access to your location, computations that rely on the here() function will show up blank.",
                false, false
            );
        };

        var getErrorMessage = function (err) {
            switch (err.code) {
                case err.PERMISSION_DENIED:
                    return "You denied CommCare HQ permission to read your browser's current location. ";
                case err.TIMEOUT:
                    return "Your connection was not strong enough to acquire your location. Please try again later. ";
                case err.POSITION_UNAVAILABLE:
                default:
                    return "Your browser location could not be determined. ";
            }
        };

        if (navigator.geolocation) {
            var progressView = ProgressBar({
                progressMessage: gettext("Fetching your location..."),
            });
            FormplayerFrontend.regions.getRegion('loadingProgress').show(progressView.render());
            navigator.geolocation.getCurrentPosition(success, error, {timeout: 10000});
        }
    };

    var startOrStopLocationWatching = function (shouldWatchLocation) {
        if (navigator.geolocation) {
            var watching = Boolean(sessionStorage.lastLocationWatchId);
            if (!watching && shouldWatchLocation) {
                sessionStorage.lastLocationWatchId = navigator.geolocation.watchPosition(recordPosition);
            } else if (watching && !shouldWatchLocation) {
                navigator.geolocation.clearWatch(sessionStorage.lastLocationWatchId);
                sessionStorage.lastLocationWatchId = '';
            }
        }
    };

    var showBreadcrumbs = function (breadcrumbs) {
        var detailCollection,
            breadcrumbModels;

        breadcrumbModels = _.map(breadcrumbs, function (breadcrumb, idx) {
            return {
                data: breadcrumb,
                id: idx,
            };
        });

        detailCollection = new Backbone.Collection(breadcrumbModels);
        var breadcrumbView = Views.BreadcrumbListView({
            collection: detailCollection,
        });
        FormplayerFrontend.regions.getRegion('breadcrumb').show(breadcrumbView);
    };

    var showLanguageMenu = function (langs) {
        var langModels,
            langCollection;

        FormplayerFrontend.regions.addRegions({
            formMenu: "#form-menu",
        });
        langModels = _.map(langs, function (lang) {
            return {
                lang: lang,
            };
        });

        langCollection = new Backbone.Collection(langModels);
        var formMenuView = Views.FormMenuView({
            collection: langCollection,
        });
        FormplayerFrontend.regions.getRegion('formMenu').show(formMenuView);
    };


    var getMenuView = function (menuResponse) {
        var menuData = {                    // TODO: make this more concise
            collection: menuResponse,
            title: menuResponse.title,
            headers: menuResponse.headers,
            widthHints: menuResponse.widthHints,
            actions: menuResponse.actions,
            pageCount: menuResponse.pageCount,
            currentPage: menuResponse.currentPage,
            styles: menuResponse.styles,
            type: menuResponse.type,
            sessionId: menuResponse.sessionId,
            tiles: menuResponse.tiles,
            numEntitiesPerRow: menuResponse.numEntitiesPerRow,
            maxHeight: menuResponse.maxHeight,
            maxWidth: menuResponse.maxWidth,
            redoLast: menuResponse.redoLast,
            useUniformUnits: menuResponse.useUniformUnits,
            isPersistentDetail: menuResponse.isPersistentDetail,
            sortIndices: menuResponse.sortIndices,
            isMultiSelect: menuResponse.multiSelect,
        };
        var urlObject = Utils.currentUrlToObject();

        sessionStorage.queryKey = menuResponse.queryKey;
        if (menuResponse.type === "commands") {
            return Views.MenuListView(menuData);
        } else if (menuResponse.type === "query") {
            if (Toggles.toggleEnabled('APP_ANALYTICS')) {
                var props = {
                    domain: FormplayerFrontend.getChannel().request('currentUser').domain,
                };
                if (menuResponse.breadcrumbs && menuResponse.breadcrumbs.length) {
                    props.name = menuResponse.breadcrumbs[menuResponse.breadcrumbs.length - 1];
                }
                Kissmetrics.track.event('Case Search', props);
            }
            urlObject.setQueryData({}, false, false);
            return QueryView(menuData);
        } else if (menuResponse.type === "entities") {
            if (Toggles.toggleEnabled('APP_ANALYTICS')) {
                var searchText = urlObject.search;
                var event = "Viewed Case List";
                if (searchText) {
                    event = "Searched Case List";
                }
                var eventData = {
                    domain: FormplayerFrontend.getChannel().request("currentUser").domain,
                    name: menuResponse.title,
                };
                var fields = _.pick(Utils.getCurrentQueryInputs(), function (v) { return !!v; });
                if (!_.isEmpty(fields)) {
                    eventData.searchFields = _.sortBy(_.keys(fields)).join(",");
                }
                Kissmetrics.track.event(event, eventData);
            }
            if (/search_command\.m\d+/.test(menuResponse.queryKey) && menuResponse.currentPage === 0) {
                Kissmetrics.track.event('Started Case Search', {
                    'Split Screen Case Search': Toggles.toggleEnabled('SPLIT_SCREEN_CASE_SEARCH'),
                });
            }
            if (menuResponse.tiles === null || menuResponse.tiles === undefined) {
                if (menuData.isMultiSelect) {
                    return Views.MultiSelectCaseListView(menuData);
                } else {
                    return Views.CaseListView(menuData);
                }
            } else {
                if (menuResponse.numEntitiesPerRow > 1) {
                    return Views.GridCaseTileListView(menuData);
                } else {
                    return Views.CaseTileListView(menuData);
                }
            }
        }
    };

    return {
        getMenuView: getMenuView,
        handleLocationRequest: handleLocationRequest,
        showBreadcrumbs: showBreadcrumbs,
        showLanguageMenu: showLanguageMenu,
        startOrStopLocationWatching: startOrStopLocationWatching,
    };
});
