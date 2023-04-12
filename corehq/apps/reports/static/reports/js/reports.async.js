hqDefine("reports/js/reports.async", function () {
    return function (o) {
        'use strict';
        var self = {};
        self.reportContent = $('#report-content');
        self.filterForm = o.filterForm || $('#paramSelectorForm');
        self.loadingIssueModal = $('#loadingReportIssueModal');
        self.issueAttempts = 0;
        self.hqLoading = null;
        self.standardReport = o.standardReport;
        self.filterRequest = null;
        self.reportRequest = null;
        self.hashRequest = null;
        self.loaderClass = '.report-loading';

        self.humanReadableErrors = {
            400: gettext("Please check your Internet connection!"),
            404: gettext("Report Not Found."),
            408: gettext("Request timed out when rendering this report. This might be an issue with our servers" +
                " or with your Internet connection. We encourage you to report an issue to CommCare HQ Support so we" +
                " can look into any possible issues."),
            500: gettext("Problem Rendering Report. Our error monitoring tools have noticed this and we are working quickly to" +
                " resolve this issue as soon as possible. We encourage you to contact CommCare HQ Support" +
                " if this issue persists for more than a few minutes. We appreciate any additional information" +
                " you can give us about this problem so we can fix it immediately."),
            502: gettext("Bad Gateway. Please contact CommCare HQ Support."),
            503: gettext("CommCare HQ is experiencing server difficulties. We're working quickly to resolve it." +
                " Thank you for your patience. We are extremely sorry."),
            504: gettext("Gateway Timeout. Please contact CommCare HQ Support."),
        };

        var loadFilters = function (data) {
            self.filterRequest = null;
            try {
                $('#hq-report-filters').html(data.filters);
                hqImport("reports/js/filters/main").init();
            } catch (e) {
                console.log(e);
            }
            $('#reportFiltersAccordion').removeClass('hide');
            self.standardReport.resetFilterState();
        };

        self.init = function () {
            console.log("init")
            self.reportContent.attr('style', 'position: relative;');
            var init_params = window.location.search.substr(1)
            console.log(init_params)
            if (init_params) {
                console.log("init filter detected")
                self.getQueryHash(init_params, true, self.standardReport.filterSet)
            }
            else {
                console.log("plain url")
                self.updateReport(true, init_params, self.standardReport.filterSet);
            }

            // only update the report if there are actually filters set
            if (!self.standardReport.needsFilters) {
                self.standardReport.filterSubmitButton.addClass('disabled');
            }
            self.filterForm.submit(function () {
                console.log("IMMEDIATELY AFTER SUBMITTING")
                self.getQueryHash(hqImport('reports/js/reports.util').urlSerialize(this), false, true);
                return false;
            });
        };

        self.getQueryHash = function (params, initial_load, setFilters) {
            var hash;
            var pathName = window.location.pathname;
            if (params.includes('hash') && (pathName.includes('case_list_explorer') || pathName.includes('case_list'))) {
                // expectation is that this is only when a hash url is initially entered
                console.log("hash given")
                hash = params.replace('hash=', '') // not this..
                params = ''
                console.log(hash)
            }
            else if (pathName.includes('case_list_explorer') || pathName.includes('case_list')) {
                console.log("no hash - create new")
                console.log(params)
                hash = ''
            }
            self.hashRequest = $.ajax({
                    url: pathName.replace(self.standardReport.urlRoot,
                        self.standardReport.urlRoot + 'get_or_create_hash/'),
                    dataType: 'json',
                    data: {'hash': hash, 'params': params},
                    success: function (data) {
                        console.log("hash success")
                        self.hashRequest = null;
                        console.log(data.hash)
                        console.log(data.query_string)
                        console.log(data.not_found)
                        if (!initial_load) {
                            self.updateFilters(data.query_string);
                        }
                        // hmm I mean not_found = true and !data.query_string kinda go together tho..
                        if (!data.query_string) {
                            setFilters = false
                        }
                        self.updateReport(initial_load, data.query_string, setFilters);
                        if (data.not_found) {
                            console.log("no matches found for given hash")
                            // error banner maybe?
                            history.pushState(null, window.location.title, pathName);
                        }
                        else {
                            history.pushState(null, window.location.title, pathName + '?hash=' + data.hash);
                        }
                    },
                    error: function (data) {
                        // could be any number of couch errors - borrow from the error list above?
                        console.log("Some sort of error... be more concise with it")
                    },
                });
        }

        self.updateFilters = function (form_params) {
            self.standardReport.saveDatespanToCookie();
            self.filterRequest = $.ajax({
                url: window.location.pathname.replace(self.standardReport.urlRoot,
                    self.standardReport.urlRoot + 'filters/') + "?" + form_params,
                dataType: 'json',
                success: loadFilters,
            });
        };

        self.updateReport = function (initial_load, params, setFilters) {
            var process_filters = "";
            if (initial_load) {
                process_filters = "hq_filters=true&";
                if (self.standardReport.loadDatespanFromCookie()) {
                    process_filters = process_filters +
                        "&startdate=" + self.standardReport.datespan.startdate +
                        "&enddate=" + self.standardReport.datespan.enddate;
                }
            }
            if (setFilters != undefined) {
                process_filters = process_filters + "&filterSet=" + setFilters;
            }
            if (setFilters) {
                $(self.standardReport.exportReportButton).removeClass('hide');
                $(self.standardReport.emailReportButton).removeClass('hide');
                $(self.standardReport.printReportButton).removeClass('hide');
            }

            self.reportRequest = $.ajax({
                url: (window.location.pathname.replace(self.standardReport.urlRoot,
                    self.standardReport.urlRoot + 'async/')) + "?" + process_filters + "&" + params,
                dataType: 'json',
                success: function (data) {
                    self.reportRequest = null;
                    if (data.filters) {
                        loadFilters(data);
                    }
                    self.issueAttempts = 0;
                    self.loadingIssueModal.modal('hide');
                    self.hqLoading = $(self.loaderClass);
                    self.reportContent.html(data.report);
                    hqImport('reports/js/charts/main').init();
                    // clear lingering popovers
                    _.each($('body > .popover'), function (popover) {
                        $(popover).remove();
                    });
                    self.reportContent.append(self.hqLoading);
                    self.hqLoading.removeClass('hide');

                    // Assorted UI cleanup/initialization
                    $('.hq-report-time-notice').removeClass('hide');
                    if ($.timeago) {
                        $(".timeago").timeago();
                    }

                    $('.loading-backdrop').fadeOut();
                    self.hqLoading.fadeOut();

                    if (!initial_load || !self.standardReport.needsFilters) {
                        self.standardReport.filterSubmitButton
                            .button('reset');
                        setTimeout(function () {
                            // Bootstrap clears all btn styles except btn on reset
                            // This gets around it by waiting 10ms.
                            self.standardReport.filterSubmitButton
                                .removeClass('btn-primary')
                                .addClass('disabled')
                                .prop('disabled', true);

                        }, 10);
                    } else {
                        self.standardReport.filterSubmitButton
                            .button('reset')
                            .addClass('btn-primary')
                            .removeClass('disabled')
                            .prop('disabled', false);
                    }
                },
                error: function (data) {
                    var humanReadable;
                    self.reportRequest = null;
                    if (data.status != 0) {
                        // If it is a BadRequest allow for report to specify text
                        if (data.status === 400) {
                            humanReadable = data.responseText || self.humanReadableErrors[data.status];
                        } else {
                            humanReadable = self.humanReadableErrors[data.status];
                        }
                        self.loadingIssueModal.find('.report-error-status').html('<strong>' + data.status + '</strong> ' +
                            ((humanReadable) ? humanReadable : ""));
                        if (self.issueAttempts > 0)
                            self.loadingIssueModal.find('.btn-primary').button('fail');
                        self.issueAttempts += 1;
                        self.loadingIssueModal.modal('show');
                    } else {
                        self.hqLoading = $(self.loaderClass);
                        self.hqLoading.find('h4').text("Loading Stopped");
                        self.hqLoading.find('.js-loading-spinner').attr('style', 'visibility: hidden;');
                    }
                },
                beforeSend: function () {
                    self.standardReport.filterSubmitButton.button('loading');
                    $('.loading-backdrop').fadeIn();
                    if (self.hqLoading) {
                        self.hqLoading.attr('style', 'position: absolute; top: 30px; left: 40%;');
                        self.hqLoading.fadeIn();
                    }

                },
            });
        };

        self.loadingIssueModal.on('click', '.try-again', function () {
            self.loadingIssueModal.find('.btn-primary').button('loading');
            self.updateReport(true, window.location.search.substr(1));
        });

        self.loadingIssueModal.on('hide hide.bs.modal', function () {
            if (self.issueAttempts > 0) {
                self.hqLoading = $(self.loaderClass);
                self.hqLoading.find('.js-loading-spinner').addClass('hide');
                self.hqLoading.find('h4').text(gettext('We were unsuccessful loading the report:'))
                    .attr('style', 'margin-bottom: 10px;');
            }
        });

        return self;
    };
});
