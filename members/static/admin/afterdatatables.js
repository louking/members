function afterdatatables() {
    console.log('afterdatatables()');

    // only register group for editor if needed
    if (
        // these pages don't have interest translation
        !location.pathname.includes('/inputtypes')
    ) {
        // handle editor substitution before submitting
        register_group_for_editor('interest', '#metanav-select-interest');
    }

}