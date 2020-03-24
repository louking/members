function afterdatatables() {
    console.log('afterdatatables()');

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
                })
            }
        }
        function clear_fields(e) {
            for (i=0; i<iteminprogress.addlfields.length; i++) {
                var f = iteminprogress.addlfields[i];
                editor.clear( f.fieldname )
            }
        }
        editor.on('initEdit', add_fields)
        editor.on('close', clear_fields)
        // editor.on('submitSuccess', function(e, data, action, xhr) {
        //
        // })
    }
}