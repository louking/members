// special processing for taskchecklist
if (location.pathname.includes('/taskchecklist')) {
    function set_cell_status_class(row, data, displayNum, displayIndex, dataIndex) {
        // the keys for classes need to match the values in leadership_tasks_members.get_status.displayorder
        classes = {
            'overdue': 'status-overdue',
            'expires soon': 'status-expires-soon',
            'optional': 'status-optional',
            'up to date': 'status-up-to-date',
            'done': 'status-done',
        }
        // remove all status classes from indicated element
        for (var class_ in classes) {
            $('.status-field', row).removeClass(classes[class_]);
        }
        // add appropriate class based on data value
        $('.status-field', row).addClass(classes[data.status]);
    }
}
