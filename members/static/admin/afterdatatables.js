function afterdatatables() {
    console.log('afterdatatables()');
    var hasoptions = ['checkbox', 'radio', 'select2'];

    // handle editor substitution before submitting
    register_group_for_editor('interest', '#metanav-select-interest');

    // special processing for taskchecklist
    if (location.pathname.includes('/taskchecklist')) {
        var iteminprogress;
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
                })
            }
        }
        function clear_fields(e) {
            for (i=0; i<iteminprogress.addlfields.length; i++) {
                var f = iteminprogress.addlfields[i];
                editor.clear( f.fieldname )
            }
        }

        // add and clear additional fields appropriately
        editor.on('initEdit', add_fields)
        editor.on('close', clear_fields)

        // make sure embedded links open in a new tab
        editor.on('opened', function(e, type){
            $('.DTE_Field_Input a').attr('target', '_blank');
        })
        // editor.on('submitSuccess', function(e, data, action, xhr) {
        //
        // })

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