hqDefine("accounting/js/stripe_card_manager", [
    'jquery',
    'knockout',
    'accounting/js/lib/stripe',
], function (
    $,
    ko,
    Stripe
) {
    var newStripeCardModel = function (data, cardManager) {
        var self = {};
        var mapping = {
            observe: ['number', 'cvc', 'expMonth','expYear', 'isAutopay', 'token'],
        };

        self.wrap = function (data) {
            ko.mapping.fromJS(data, mapping, self);
        };
        self.reset = function () {
            self.wrap({'number': '', 'cvc': '', 'expMonth': '', 'expYear': '', 'isAutopay': false, 'token': ''});
        };
        self.reset();

        self.unwrap = function () {
            return {token: self.token(), autopay: self.isAutopay()};
        };

        self.isTestMode = ko.observable(false);
        self.isProcessing = ko.observable(false);
        self.errorMsg = ko.observable('');

        var submit = function () {
            // Sends the new card to HQ
            return $.ajax({
                type: "POST",
                url: data.url,
                data: self.unwrap(),
                success: function (data) {
                    $("#card-modal").modal('hide');
                    $("#success-modal").modal('show');
                    cardManager.wrap(data);
                    self.reset();
                },
            }).fail(function (data) {
                var response = JSON.parse(data.responseText);
                self.errorMsg(response.error);
            }).always(function () {
                self.isProcessing(false);
            });
        };

        var handleStripeResponse = function (status, response) {
            if (response.error) {
                self.isProcessing(false);
                self.errorMsg(response.error.message);
            } else {
                self.errorMsg('');
                self.token(response.id);
                submit();
            }
        };

        var createStripeToken = function () {
            Stripe.card.createToken({
                number: self.number(),
                cvc: self.cvc(),
                exp_month: self.expMonth(),
                exp_year: self.expYear(),
            }, handleStripeResponse);
        };

        self.saveCard = function () {
            self.isProcessing(true);
            createStripeToken();
        };

        return self;
    };

    var stripeCardModel = function (card, baseUrl, cardManager) {
        'use strict';
        var self = {};
        var mapping = {
            include: ['brand', 'last4', 'exp_month','exp_year', 'is_autopay'],
            copy: ['url', 'token'],
        };

        self.wrap = function (data) {
            ko.mapping.fromJS(data, mapping, self);
            self.url = baseUrl + card.token + '/';
        };
        self.wrap(card);

        self.setAutopay = function () {
            cardManager.autoPayButtonEnabled(false);
            self.submit({is_autopay: true}).always(function () {
                cardManager.autoPayButtonEnabled(true);
            });
        };

        self.unSetAutopay = function () {
            cardManager.autoPayButtonEnabled(false);
            self.submit({is_autopay: false}).always(function () {
                cardManager.autoPayButtonEnabled(true);
            });
        };

        self.isDeleting = ko.observable(false);
        self.deleteErrorMsg = ko.observable('');
        self.deleteCard = function (card, button) {
            self.isDeleting(true);
            self.deleteErrorMsg = ko.observable('');
            cardManager.cards.destroy(card);
            $.ajax({
                type: "DELETE",
                url: self.url,
                success: function (data) {
                    cardManager.wrap(data);
                    $(button.currentTarget).closest(".modal").modal('hide');
                    $("#success-modal").modal('show');
                },
            }).fail(function (data) {
                var response = JSON.parse(data.responseText);
                self.deleteErrorMsg(response.error);
                if (response.cards) {
                    cardManager.wrap(response);
                }
            }).always(function () {
                self.isDeleting(false);
            });
        };

        self.submit = function (data) {
            return $.ajax({
                type: "POST",
                url: self.url,
                data: data,
                success: function (data) {
                    cardManager.wrap(data);
                },
            }).fail(function (data) {
                var response = JSON.parse(data.responseText);
                alert(response.error);
            });
        };

        return self;
    };


    var stripeCardManager = function (data) {
        var self = {};
        var mapping = {
            'cards': {
                create: function (card) {
                    return stripeCardModel(card.data, data.url, self);
                },
            },
        };

        self.wrap = function (data) {
            ko.mapping.fromJS(data, mapping, self);
        };
        self.wrap(data);

        self.autoPayButtonEnabled = ko.observable(true);
        self.newCard = newStripeCardModel({url: data.url}, self);

        return self;
    };

    return {
        stripeCardManager: stripeCardManager,
    };
});
