var iteminprogress;
var hasoptions = ['checkbox', 'radio', 'select2'];

function add_fields(e, node, data, items, type) {
    iteminprogress = data;
    for (i=0; i<iteminprogress.addlfields.length; i++) {
        var f = iteminprogress.addlfields[i];
        editor.add({
            name:   f.fieldname,
            data:   f.fieldname,
            label:  f.displaylabel,
            type:   f.inputtype,
            fieldInfo:  f.fieldInfo,
            className:  'addlfield',
            options: hasoptions.includes(f.inputtype) ? f.fieldoptions : null,
            // separator ', ' must match loutilities.tables.SEPARATOR
            // only for checkbox as this is currently only input type which allows multiple selections
            separator: f.inputtype === 'checkbox' ? ', ' : null,
            ajax: f.uploadurl,
            display: (f.inputtype === 'upload') ? renderfileid() : null,
        });
        if (f.inputtype === 'display') {
            editor.set(f.fieldname, f.displayvalue);
        }
    }
}

function clear_fields(e) {
    for (i=0; i<iteminprogress.addlfields.length; i++) {
        var f = iteminprogress.addlfields[i];
        editor.clear( f.fieldname )
    }
}

function add_field_vals(data, justtypes, showdisplay) {
    iteminprogress = data;
    for (i=0; i<iteminprogress.addlfields.length; i++) {
        var f = iteminprogress.addlfields[i];

        // don't show display-only data
        if (showdisplay == undefined && f.inputtype == 'display') { continue; }

        if (justtypes == undefined || justtypes.includes(f.inputtype)) {
            // only add display if data was entered previously
            if (f.hasOwnProperty('value')) {
                var fieldname = f.fieldname + '-val';
                editor.add({
                    name:   fieldname,
                    data:   f.fieldname,
                    label:  f.displaylabel + ' (last entry)',
                    type:   f.inputtype !== 'upload' && f.inputtype !== 'display' ? 'readonly' : 'display',
                    fieldInfo:  f.fieldInfo,
                    className:  'addlfield',
                    options: hasoptions.includes(f.inputtype) ? f.fieldoptions : null,
                    // separator ', ' must match loutilities.tables.SEPARATOR
                    // only for checkbox as this is currently only input type which allows multiple selections
                    separator: f.inputtype === 'checkbox' ? ', ' : null,
                })
                editor.set(fieldname, f.value);
                if (f.inputtype === 'display') {
                    editor.set(fieldname, f.displayvalue);
                }
            }
        }

    }
}

function clear_field_vals(e, justtypes, showdisplay) {
    for (i=0; i<iteminprogress.addlfields.length; i++) {
        var f = iteminprogress.addlfields[i];

        // don't show display-only data
        if (showdisplay == undefined && f.inputtype == 'display') { continue; }

        if (justtypes == undefined || justtypes.includes(f.inputtype)) {
            // was only added if data was entered previously
            if (f.hasOwnProperty('value')) {
                var fieldname = f.fieldname + '-val';
                editor.clear(fieldname)
            }
        }
    }
}

function set_field_vals() {
    for (i = 0; i < iteminprogress.addlfields.length; i++) {
        var f = iteminprogress.addlfields[i];
        // upload field value has url, so need to substitute fileid
        if (!f.hasOwnProperty('fileid')) {
            if (f.inputtype !== 'display') {
                editor.set(f.fieldname, f.value);
            } else {
                editor.set(f.fieldname, f.displayvalue);
            }
        } else {
            editor.set(f.fieldname, f.fileid);
        }
    }
}

// note this is only called from Task Summary
function add_fields_and_set_vals(e, node, data, items, type) {
    add_fields(e, node, data, items, type);
    set_field_vals();
}

/**
 * reset datatable data based on effective date
 *
 * @param effective_date_id - element for datepicker to hold effective date, e.g., '#effective-date'
 * @param todays_date_id - button to reset datepicker to today, e.g., '#todays-date-button'
 */
function set_effective_date(effective_date_id, todays_date_id) {
    var effectivedate = $(effective_date_id);
    var todaysdate = $(todays_date_id);

    // set initial filter to today
    var today = new Date();
    today = today.toISOString().substr(0,10);

    // effective date is datepicker; todays date is button
    effectivedate.datepicker({dateFormat: 'yy-mm-dd'});
    effectivedate.val(today);
    todaysdate.button();

    // handle change of effective date by setting column filters appropriately
    effectivedate.change(function(e) {
        var ondate = effectivedate.val();
        var urlparams = allUrlParams();
        urlparams.ondate = ondate;
        resturl = window.location.pathname + '/rest?' + setParams(urlparams);
        _dt_table.one('draw.dt', function(e, settings) {
             $( '#spinner' ).hide();
        });
        $( '#spinner' ).show();
        // WARNING: nonstandard/nonpublic use of settings information
        var serverSide = _dt_table.settings()[0]['oFeatures']['bServerSide'];
        if (serverSide) {
            // add updated urlparams (with ondate) before sending the ajax request
            _dt_table.one('preXhr.dt', function(e, settings, data) {
                Object.assign(data, urlparams);
            });
            _dt_table.ajax.reload();
        } else {
            refresh_table_data(_dt_table, resturl);
        }
       
    });

    // reset the effective date
    todaysdate.click(function(e) {
        // reset today because window may have been up for a while
        today = new Date();
        today = today.toISOString().substr(0,10);
        effectivedate.val(today);
        effectivedate.change();
    })
}

function afterdatatables() {
    console.log('afterdatatables()');

    // handle group substitution before submitting
    register_group_for_editor('interest', '#metanav-select-interest', editor);
    // required for serverside -> register_group_for_datatable() is in beforedatatables.js

    // always make sure embedded links in input field open in a new tab
    editor.on('opened', function(e, type){
        $('.DTE_Field_Input a').attr('target', '_blank');
    });

    // special processing for task checklist
    var pathname = location.pathname;
    var interest = get_group_val();
    if (location.pathname.includes('/taskchecklist'))
    {
        // handle effective date update by retrieving data by /rest and refreshing table
        set_effective_date('#effective-date', '#todays-date-button');

        // add and clear additional fields appropriately
        editor.on('initEdit', function(e, node, data, items, type) {
            add_field_vals(data);
            add_fields(e, node, data, items, type);
        });
        editor.on('close', function (e) {
            clear_field_vals(e);
            clear_fields(e);
        });
        onclick_trigger(_dt_table, 'td.view-task', 'view-task');

    // special processing for task details
    } else if (location.pathname.includes('/taskdetails')) {
        // handle effective date update by retrieving data by /rest and refreshing table
        set_effective_date('#effective-date', '#todays-date-button');

        // set up registered filters (id, default for local storage, transient => don't update local storage
        fltr_register('members-external-filter-members', null, true);
        fltr_register('members-external-filter-positions-by-member', null, true);
        fltr_register('members-external-filter-taskgroups-by-member', null, true);
        fltr_register('members-external-filter-tasks', null, true);
        fltr_register('members-external-filter-taskgroups-by-task', null, true);
        fltr_register('members-external-filter-statuses', null, true);
        fltr_register('members-external-filter-completed', null, true);
        fltr_register('members-external-filter-expires', null, true);

        // initialize all the filters
        fltr_init();

        // check if member filter required; only do this if we just arrived at the page
        var member = urlParam('member');
        if (member) {
            var membercol = get_yadcf_col('members-external-filter-members');
            yadcf.exFilterColumn(_dt_table, [[membercol, member]]);
        }

        // add and clear additional fields appropriately
        editor.on('initEdit', function (e, node, data, items, type) {
            add_field_vals(data, ['upload']);
            add_fields_and_set_vals(e, node, data, items, type);
        });
        editor.on('close', function (e) {
            clear_field_vals(e, ['upload']);
            clear_fields(e);
        });

    // special processing for member summary
    } else if (location.pathname.includes('/membersummary')) {
        // set up registered filters (id, default for local storage, transient => don't update local storage
        fltr_register('members-external-filter-members', null, true);
        fltr_register('members-external-filter-positions-by-member', null, true);
        fltr_register('members-external-filter-taskgroups-by-member', null, true);

        // initialize all the filters
        fltr_init();

     // special processing for task field configuration
    } else if (location.pathname.includes('/taskfields')) {
        editor.dependent( 'inputtype', function(val, data, callback) {
            var show = [];
            var hide = [];

            // show fieldoptions only if inputtype is one of the values in hasoptions
            if (hasoptions.includes(val)) {
                show.push('fieldoptions');
            } else {
                hide.push('fieldoptions');
            }

            // display only field specifics
            if (val === 'display') {
                show.push('displayvalue');
                hide.push('fieldinfo');
            } else {
                hide.push('displayvalue');
                show.push('fieldinfo');
            }

            // datetime field specifics
            if (val === 'datetime') {
                show.push('override_completion');
            } else {
                hide.push('override_completion');
            }

            return { show: show, hide: hide }
        } )

        // force update of options
        editor.on('initEdit', function(e, node, data, items, type) {
            editor.field('fieldoptions').update(data.fieldoptions);
            editor.field('fieldoptions').val(data.fieldoptions);
        })

    // special processing for history
    } else if (location.pathname.includes('/history')) {
        // add and clear additional fields appropriately
        editor.on('initEdit', function(e, node, data, items, type) {
            add_field_vals(data, null, true);
        });
        editor.on('close', function (e) {
            clear_field_vals(e, null, true);
        });

        // set up registered filters (id, default for local storage, transient => don't update local storage
        fltr_register('members-external-filter-update-time', null, true);
        fltr_register('members-external-filter-updated-by', null, true);
        fltr_register('members-external-filter-members', null, true);
        fltr_register('members-external-filter-tasks', null, true);
        fltr_register('members-external-filter-completed', null, true);

        // initialize all the filters
        fltr_init();

    // special processing for meeting
    } else if (pathname == `/admin/${interest}/meeting`) {
        // https://stackoverflow.com/questions/19237235/jquery-button-click-event-not-firing/19237302
        meeting_invites_editor = new $.fn.dataTable.Editor({
            fields: [
                {name: 'invitestates', data: 'invitestates', label: invitation_text + ' Status', type: 'display',
                    className: 'field_req full block'},
                {name: 'subject', data: 'subject', label: 'Subject', type: 'text', className: 'field_req full block'},
                {name: 'message', data: 'message', label: 'Message', type: 'ckeditorClassic',
                    className: 'full block'},
                {name: 'from_email', data: 'from_email', label: 'From', type: 'text', className: 'field_req full block'},
                // {name: 'options', data: 'options', label: '', type: 'checkbox', className: 'full block',
                //     options: [
                //         {label: 'Request Status Report', value: 'statusreport'},
                //         {label: 'Show Action Items', value: 'actionitems'},
                //     ],
                //     separator: ',',
                // }
            ],
        });

        // buttons needs to be set up outside of ajax call (beforedatatables.js meeting_sendinvites()
        // else the button action doesn't fire (see https://stackoverflow.com/a/19237302/799921 for ajax hint)
        meeting_invites_editor
            .buttons([
                {
                    'text': 'Send ' + invitations_text,
                    'action': function () {
                        this.submit( null, null, function(data){
                            var that = this;
                        });
                    }
                },
                {
                    'text': 'Cancel',
                    'action': function() {
                        this.close();
                    }
                }
            ])

        // need to redraw after invite submission in case new Attendees row added to table
        meeting_invites_editor.on('submitComplete closed', function(e) {
            _dt_table.draw();
        });

        // https://stackoverflow.com/questions/19237235/jquery-button-click-event-not-firing/19237302
        meeting_email_editor = new $.fn.dataTable.Editor({
            fields: [
                {name: 'invitestates', data: 'invitestates', label: 'To', type: 'display',
                    className: 'field_req full block'},
                {name: 'subject', data: 'subject', label: 'Subject', type: 'text', className: 'field_req full block'},
                {name: 'message', data: 'message', label: 'Message', type: 'ckeditorClassic',
                    className: 'full block'},
                {name: 'from_email', data: 'from_email', label: 'From', type: 'text', className: 'field_req full block'},
            ],
        });

        // buttons needs to be set up outside of ajax call (beforedatatables.js meeting_sendinvites()
        // else the button action doesn't fire (see https://stackoverflow.com/a/19237302/799921 for ajax hint)
        meeting_email_editor
            .buttons([
                {
                    'text': 'Send Email',
                    'action': function () {
                        this.submit( null, null, function(data){
                            var that = this;
                        });
                    }
                },
                {
                    'text': 'Cancel',
                    'action': function() {
                        this.close();
                    }
                }
            ])

        motion_evote_saeditor.init();
        meeting_discussion_saeditor.init();

        // only show hidden_reason field if is_hidden is true (yes)
        editor.dependent('is_hidden', function(val, data, callback) {
            return val === 'no' ?
                { hide: 'hidden_reason', animate: false } :
                { show: 'hidden_reason', animate: false }
        });

        /**
         * url hook gets called from within groups.js translate_datatable_group() anon fn
         *
         * @param url
         * @returns {string}
         */
        function filter_hidden(url) {
            // split out query parameters, and collect in object
            var urlsplit = url.split('?');
            var urlparams = allUrlParams();

            // remove show_hidden if not needed, else set appropriately
            delete urlparams['show_hidden']
            if ($('#show-hidden-status').prop('checked') == true) {
                urlparams['show_hidden'] = true;
            }
            url = urlsplit[0] + '?' + setParams(urlparams);
            return url;
        }
        dt_add_url_hook(filter_hidden);
        $('#show-hidden-status').change(function() {
            _dt_table.draw();
        });

        /**
         * on draw event, check if table has any rows, and hide the table if no rows
         *
         * @param dt - table to check
         */
        function childrow_check_hide_table(dt, ed) {
            // see https://datatables.net/forums/discussion/comment/84133/#Comment_84133
            dt._cr_redrawing = false;
            dt.on('draw', function(e, settings) {
                // prevent infinite loop
                if (dt._cr_redrawing) return;

                // no rows in table? hide it
                if (dt.rows().count() == 0) {
                    // don't show table, search box, or header
                    $(dt.table().node()).css('display', 'none');
                    $(dt.table().container()).find('.dataTables_filter').css('display', 'none');
                    $(dt.table().header()).css('display', 'none');
                    // don't show table label if not in editor
                    if (!ed) {
                        $(dt.table().container()).prev('.childrow-table-label').css('display', 'none')
                    }

                // some rows in table? show it
                } else {
                    // show table, search box, and header
                    $(dt.table().node()).css('display', 'block');
                    $(dt.table().container()).find('.dataTables_filter').css('display', 'block');
                    $(dt.table().header()).css('display', '');
                    $(dt.table().container()).prev('.childrow-table-label').css('display', 'block')
                    // need to adjust column sizes and redraw; dt._cr_redrawing prevents infinite draw event loop
                    dt._cr_redrawing = true;
                    dt.columns.adjust().draw();
                    dt._cr_redrawing = false;
                }
            });
        };
        // hide table when empty for actionitems, motions in childrow
        childrow_add_postcreate_hook('actionitems', function(dt, ed) {
            childrow_check_hide_table(dt, ed);
        });
        childrow_add_postcreate_hook('motions', function(dt, ed) {
            childrow_check_hide_table(dt, ed);
        });

    // special processing for meetingstatus
    } else if (location.pathname.includes('/meetingstatus')) {
        // https://stackoverflow.com/questions/19237235/jquery-button-click-event-not-firing/19237302
        meeting_reminders_editor = new $.fn.dataTable.Editor({
            fields: [
                {name: 'invitestates', data: 'invitestates', label: 'Invitation Status', type: 'display',
                    className: 'field_req full block'},
                {name: 'subject', data: 'subject', label: 'Subject', type: 'text', className: 'field_req full block'},
                {name: 'message', data: 'message', label: 'Message', type: 'ckeditorClassic',
                    className: 'full block'},
                {name: 'from_email', data: 'from_email', label: 'From', type: 'text', className: 'field_req full block'},
                // {name: 'options', data: 'options', label: '', type: 'checkbox', className: 'full block',
                //     options: [
                //         {label: 'Request Status Report', value: 'statusreport'},
                //         {label: 'Show Action Items', value: 'actionitems'},
                //     ],
                //     separator: ',',
                // }
            ],
        });

        // buttons needs to be set up outside of ajax call (beforedatatables.js meeting_sendinvites()
        // else the button action doesn't fire (see https://stackoverflow.com/a/19237302/799921 for ajax hint)
        meeting_reminders_editor
            .buttons([
                {
                    'text': 'Send Reminders',
                    'action': function () {
                        this.submit( null, null, function(data){
                            var that = this;
                        });
                    }
                },
                {
                    'text': 'Cancel',
                    'action': function() {
                        this.close();
                    }
                }
            ]);
        _dt_table.button('send-reminders:name').disable();


        // need to redraw after reminder submission to update status
        meeting_reminders_editor.on('submitSuccess', function(e, json, data, action) {
            if (json.error == "") {
                // update the returned rows
                for (i = 0; i < json.length; i++) {
                    var retrow = json[i];
                    if (_dt_table.row('#' + retrow.rowid)) {
                        _dt_table.row('#' + retrow.rowid).data(retrow);
                    }
                }
                _dt_table.draw();
            }
        });

        // todo: remove as part of fix for #391
        _dt_table.on('select deselect', function(e, dt, type, indexes) {
            var ids = _dt_table.rows({selected:true}).ids();
            if (ids.length == 0) {
                _dt_table.button('send-reminders:name').disable();
            } else {
                _dt_table.button('send-reminders:name').enable();
            }
        });

    // special processing for memberstatusreport, theirstatusreport
    } else if (location.pathname.includes('/memberstatusreport') || location.pathname.includes('/theirstatusreport')) {
        // update 'needsedit' class depending on value of statusreport field
        editor.on('preEdit', function(e, json, data, id) {
            $($(editor.s.table).DataTable().row('#'+id).node()).removeClass('needsedit');
        });
        onclick_trigger(_dt_table, 'td.edit-control', 'editRefresh');

    // special processing for mymeetings
    } else if (location.pathname.includes('/mymeetings')) {
        onclick_trigger(_dt_table, 'td.view-control', 'view-status');

    // special processing for mymotionvotes
    } else if ((pathname == `/admin/${interest}/mymotionvotes`)) {
        onclick_trigger(_dt_table, 'td.view-control', 'view-motionvote');

    // special processing for positiondates
    } else if (location.pathname.includes('/positiondates')) {
        // set initial filter to today
        var today = new Date();
        today = today.toISOString().substr(0,10);
        var startdate = _dt_table.column('startdate:name').index();
        yadcf.exFilterColumn(_dt_table,[[startdate, today]]);

        // disable user and position fields before edit
        editor.on('initEdit', function(e, node, data, items, type) {
            editor.field('user.id').disable();
            editor.field('position.id').disable();
        });
        // enable user and position fields before create
        editor.on('initCreate', function(e, json, data, id) {
            editor.field('user.id').enable();
            editor.field('position.id').enable();
        })

        // special processing for positions
    } else if (location.pathname.includes('/positions')) {
        // handle effective date update by retrieving data by /rest and refreshing table
        set_effective_date('#effective-date', '#todays-date-button');

        // https://stackoverflow.com/questions/19237235/jquery-button-click-event-not-firing/19237302
        position_wizard_editor = new $.fn.dataTable.Editor({
            fields: [
                {name: 'position', data:'position', label: 'Position', type: 'display'},
                {name: 'position_id', data: 'position_id', label: 'Position ID', type: 'hidden'},
                {name: 'effective', data: 'effective', label: 'Effective Date', type: 'datetime',
                 fieldInfo: 'select the date you want to view / have changes be effective'
                },
                {name: 'qualifier', data:'qualifier', label: 'Qualifier', 
                 fieldInfo: 'normally not needed, but can qualify the position -- e.g., interim'
                },
                {name: 'members', data: 'members', label: 'Members', type: 'select2',
                 fieldInfo: 'pick the members you want in this position on the Effective Date',
                 onFocus: 'focus',
                 // separator must match organization_admin.PositionWizardApi.post()
                 separator: ', ',
                 opts: {
                     multiple: true,
                     minimumResultsForSearch: 0,
                 },
                },
            ],
        });
        _dt_table.button('position-wizard:name').disable();

        // buttons needs to be set up outside of ajax call (beforedatatables.js meeting_sendinvites()
        // else the button action doesn't fire (see https://stackoverflow.com/a/19237302/799921 for ajax hint)
        position_wizard_editor
            .buttons([
                {
                    'text': 'Update',
                    'action': function () {
                        this.submit( null, null, function(data){
                            var that = this;
                        });
                    }
                },
                {
                    'text': 'Cancel',
                    'action': function() {
                        this.close();
                    }
                }
            ])
        
        _dt_table.on('select deselect', function(e, dt, type, indexes) {
            var ids = _dt_table.rows({selected:true}).ids();
            if (ids.length == 0) {
                _dt_table.button('position-wizard:name').disable();
            } else {
                _dt_table.button('position-wizard:name').enable();
            }
        });

        // need to refresh and redraw after wizard in case position changes should be visible
        position_wizard_editor.on('submitComplete closed', function(e) {
            var effectivedate = $('#effective-date');
            effectivedate.change();
        });

    // special processing for distribution
    } else if (location.pathname.includes('/distribution')) {
        // handle effective date update by retrieving data by /rest and refreshing table
        set_effective_date('#effective-date', '#todays-date-button');

    // special processing for meetings
    } else if (pathname == `/admin/${interest}/meetings`) {
        editor.dependent('meetingtype.id', {
            url: `/admin/${interest}/_meetingtypeparms/rest`,
        });

        // don't show some fields in form
        editor
            .hide('gs_agenda')
            .hide('gs_minutes')
            .hide('gs_status')
            // this gets shown when renew button is used
            .hide('renewoptions');

        // // initialize all the filters [only required for persistent filters]
        // fltr_register('meetings-external-filter-membertype', null, true);
        // fltr_init();

    // special processing for meetingtypes
    } else if (pathname == `/admin/${interest}/meetingtypes`) {
        editor.on('submitSuccess', function(e, json, data, action) {
           var urlparams = allUrlParams();
           resturl = window.location.pathname + '/rest?' + setParams(urlparams);
           refresh_table_data(_dt_table, resturl);
        });

    // special processing for members
    } else if (pathname == `/${interest}/members`) {
        set_effective_date('#effective-date', '#todays-date-button');
    } else if (pathname == `/admin/${interest}/members`) {
        set_effective_date('#effective-date', '#todays-date-button');
    } else if (pathname == `/admin/${interest}/expired_members`) {
        set_effective_date('#effective-date', '#todays-date-button');

    // special processing for rt_members
    } else if (pathname == `/admin/${interest}/rt_members`) {
        var activecol = get_yadcf_col('active-filter');
        yadcf.exFilterColumn(_dt_table, [[activecol, 'yes']]);

        $('#show-inactive-status').change(function() {
            if ($('#show-inactive-status').is(':checked')) {
                yadcf.exResetAllFilters(_dt_table, [activecol])
            } else {
                yadcf.exFilterColumn(_dt_table, [[activecol, 'yes']]);
            }
        });
    }
}
