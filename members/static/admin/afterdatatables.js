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
    if (location.pathname.includes('/taskchecklist'))
    {
        // add and clear additional fields appropriately
        editor.on('initEdit', function(e, node, data, items, type) {
            add_field_vals(data);
            add_fields(e, node, data, items, type);
        });
        editor.on('close', function (e) {
            clear_field_vals(e);
            clear_fields(e);
        });

    // special processing for task details
    } else if (location.pathname.includes('/taskdetails')) {
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
    } else if (location.pathname.includes('/meeting') && !location.pathname.includes('/meetings')) {
        // need on 'preInvites' to translate interest for Send Invites button
        editor.on( 'preInvites', translate_editor_group );

    // special processing for history
    } else if (location.pathname.includes('/memberstatusreport')) {
        // for create show all fields except rsvp response
        editor.on('initCreate', function(e) {
            editor.show();
            editor.hide('rsvp_response');
        });

        // for edit add and clear additional fields appropriately
        editor.on('initEdit', function(e, node, data, items, type) {
            editor.show();
            editor.hide('title');
            if (data.is_rsvp) {
                editor.hide('statusreport');
            } else {
                editor.hide('rsvp_response');
            }
        });
    }
}