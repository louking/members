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

function add_field_vals(data, justtypes) {
    iteminprogress = data;
    for (i=0; i<iteminprogress.addlfields.length; i++) {
        var f = iteminprogress.addlfields[i];

        // don't show display-only data
        if (f.inputtype == 'display') { continue; }

        if (justtypes == undefined || justtypes.includes(f.inputtype)) {
            // only add display if data was entered previously
            if (f.hasOwnProperty('value')) {
                var fieldname = f.fieldname + '-val';
                editor.add({
                    name:   fieldname,
                    data:   f.fieldname,
                    label:  f.displaylabel + ' (last entry)',
                    type:   f.inputtype !== 'upload' ? 'readonly' : 'display',
                    fieldInfo:  f.fieldInfo,
                    className:  'addlfield',
                    options: hasoptions.includes(f.inputtype) ? f.fieldoptions : null,
                    // separator ', ' must match loutilities.tables.SEPARATOR
                    // only for checkbox as this is currently only input type which allows multiple selections
                    separator: f.inputtype === 'checkbox' ? ', ' : null,
                })
                editor.set(fieldname, f.value);
            }
        }

    }
}

function clear_field_vals(e, justtypes) {
    for (i=0; i<iteminprogress.addlfields.length; i++) {
        var f = iteminprogress.addlfields[i];

        // don't show display-only data
        if (f.inputtype == 'display') { continue; }

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
            editor.set(f.fieldname, f.value);
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

    // handle editor substitution before submitting
    register_group_for_editor('interest', '#metanav-select-interest');

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

    // special processing for task summary
    } else if (location.pathname.includes('/tasksummary')) {
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

        // add and clear additional fields appropriately
        editor.on('initEdit', function (e, node, data, items, type) {
            add_field_vals(data, ['upload']);
            add_fields_and_set_vals(e, node, data, items, type);
        });
        editor.on('close', function (e) {
            clear_field_vals(e, ['upload']);
            clear_fields(e);
        });

    // special processing for task field configuration
    } else if (location.pathname.includes('/taskfields')) {
        editor.dependent( 'inputtype', function(val, data, callback) {
            // show field options only if inputtype is one of the following values
            return hasoptions.includes(val) ?
                { show: 'fieldoptions' } :
                { hide: 'fieldoptions' }
        } )

        // force update of options
        editor.on('initEdit', function(e, node, data, items, type) {
            editor.field('fieldoptions').update(data.fieldoptions);
            editor.field('fieldoptions').val(data.fieldoptions);
        })
    }
}