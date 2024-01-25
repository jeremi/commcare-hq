/* globals requirejs */
requirejs.config({
    baseUrl: '/static/',
    paths: {
        "es6": "requirejs-babel7/es6",
        "babel": "@babel/standalone/babel.min",
        "babel-plugin-transform-modules-requirejs-babel": "babel-plugin-transform-modules-requirejs-babel/index",
        "jquery": "jquery/dist/jquery.min",
        "underscore": "underscore/underscore",
        "bootstrap": "bootstrap/dist/js/bootstrap.min",
        "bootstrap5": "bootstrap5/dist/js/bootstrap.bundle.min",
        "knockout": "knockout/build/output/knockout-latest.debug",
        "ko.mapping": "hqwebapp/js/lib/knockout_plugins/knockout_mapping.ko.min",
        "datatables": "datatables.net/js/jquery.dataTables.min",
        "datatables.fixedColumns": "datatables.net-fixedcolumns/js/dataTables.fixedColumns.min",
        "datatables.fixedColumns.bootstrap": "datatables.net-fixedcolumns/js/dataTables.fixedColumns.min",
        "datatables.bootstrap": "datatables.net-bs5/js/dataTables.bootstrap5.min",
        "popper": "@popperjs/core/dist/umd/popper.min",
        "tempus-dominus": "eonasdan/tempus-dominus/dist/js/tempus-dominus.min",
        "datetimepicker": "@eonasdan/tempus-dominus/dist/js/jQuery-provider.min",  // import this if you need jquery plugin of tempus-dominus
    },
    shim: {
        "ace-builds/src-min-noconflict/ace": { exports: "ace" },
        "ko.mapping": { deps: ['knockout'] },
        "hqwebapp/js/bootstrap5/hq.helpers": { deps: ['jquery', 'knockout', 'underscore'] },
        "datatables.bootstrap": { deps: ['datatables'] },
        "datatables.fixedColumns.bootstrap": { deps: ['datatables.fixedColumns'] },
        "jquery.rmi/jquery.rmi": {
            deps: ['jquery', 'knockout', 'underscore'],
            exports: 'RMI',
        },
        "accounting/js/lib/stripe": { exports: 'Stripe' },
        "d3/d3.min": {
            "exports": "d3",
        },
        "nvd3/nv.d3.min": {
            deps: ['d3/d3.min'],
            exports: 'nv',
        },
        "hqwebapp/js/lib/modernizr": {
            exports: 'Modernizr',
        },
        "datetimepicker": {
            deps: ['popper', 'tempus-dominus'],
        },
    },
    packages: [{
        name: 'moment',
        location: 'moment',
        main: 'moment',
    }],
    map: {
        "datatables.fixedColumns": {
            "datatables.net": "datatables",
        },
    },

    // This is really build config, but it's easier to define a js function here than in bootstrap5/requirejs.yml
    // The purpose of this is to replace hqDefine and hqRequire calls, which in a requirejs context are
    // just pass throughs to define and require, with actual calls to define and require. This is needed
    // because r.js's dependency tracing depends on parsing define and require calls.
    onBuildRead: function (moduleName, path, contents) {
        return contents.replace(/\bhqDefine\b/g, 'define').replace(/\bhqRequire\b/g, 'require');
    },
});
