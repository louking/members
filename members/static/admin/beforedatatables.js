$( function () {
    // if groups are being used, need to set up translation variables before datatables is initialized
    // required for datatables option {serverside:true}
    register_group_for_datatable('interest', '#metanav-select-interest');
});

function set_cell_status_class(row, data, displayNum, displayIndex, dataIndex) {
    // the keys for classes need to match the values in viewhelpers(.py).STATUS_DISPLAYORDER
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

function dismiss_button() {
    this.close();
}

function submit_button() {
    this.submit();
}

function meeting_sendreminders(ed) {
    fn = function() {
        var that = this;
        that.processing(true);
        ed.one('postEdit', function(e, json, data, id) {
            that.processing(false);
            var message = $('<div>', {title: 'Generated reminders'});
            var popuphtml = $('<ul>').appendTo(message);
            if (json.newinvites.length > 0) {
                var newinvites = $('<p>', {html: 'new invites sent to'}).appendTo(popuphtml);
                var newinvitesul = $('<ul>').appendTo(newinvites);
                for (var i=0; i<json.newinvites.length; i++) {
                    $('<li>', {html: json.newinvites[i]}).appendTo(newinvitesul);
                }
            }
            if (json.reminded.length > 0) {
                var reminders = $('<p>', {html: 'reminders sent to'}).appendTo(popuphtml);
                var remindersul = $('<ul>').appendTo(reminders);
                for (var i=0; i<json.reminded.length; i++) {
                    $('<li>', {html: json.reminded[i]}).appendTo(remindersul);
                }
            }
            message.dialog({
                modal: true,
                minWidth: 200,
                height: 'auto',
                buttons: {
                    OK: function() {
                        $(this).dialog('close');
                    }
                }
            });
        })
        // selected rows, false means don't display form
        ed.edit({selected:true}, false).submit();
    }
    return fn;
}

function meeting_generate_docs(url) {
    fn = function() {
        var that = this;
        that.processing(true);

        // allUrlParams() picks up at least meeting_id
        var form = $('<form>', {id: 'doc-form', action: url + '?' + setParams(allUrlParams()), method:'POST'})
        form.append($('<input>', {type: 'checkbox', id:  'agenda', name: 'agenda'}));
        form.append($('<label>', {for: 'agenda', text: 'Agenda'}));
        form.append($('<br>'));
        form.append($('<input>', {type: 'checkbox', id:  'status-report', name: 'status-report'}));
        form.append($('<label>', {for: 'status-report', text: 'Status Report'}));
        form.append($('<br>'));
        form.append($('<input>', {type: 'checkbox', id:  'minutes', name: 'minutes'}));
        form.append($('<label>', {for: 'minutes', text: 'Minutes'}));

        // adapted from https://www.tjvantoll.com/2013/07/10/creating-a-jquery-ui-dialog-with-a-submit-button/
        form.dialog({
            title: 'Generate Documents',
            modal: true,
            minWidth: 200,
            height: 'auto',
            buttons: [
                {
                    text: 'Submit',
                    click: function() {
                        var url = form.attr( "action" );
                        var terms = {};
                        var checkboxes = form.find('input');
                        checkboxes.each(function() {
                            terms[$(this).attr('name')] = $(this).is(":checked");
                        });
                        var post = $.post(url, terms, function(data, textStatus, jqXHR) {
                            form.dialog('close');
                            that.processing(false);
                        });
                    },
                },
                {
                    text: 'Cancel',
                    click: function() {
                        form.dialog('close');
                        that.processing(false);
                    }
                },
            ]
        });

    }
    return fn;
}

function render_month_date(data, type, row, meta) {
    if (data) {
        return data.slice(-5)
    } else {
        return data
    }
}

// view member from member summary view
function member_details(e, dt, node, config) {
    var args = allUrlParams();
    var member = dt.rows({selected:true}).data()[0].member;
    args.member = member;
    var newsearch = $.param(args);
    var newloclist = window.location.pathname.split('/').slice(0, -1);
    newloclist.push('taskdetails');
    var newloc = newloclist.join('/') + '?' + newsearch;
    window.location.href = newloc;
}

// view meeting from meetings view
function meeting_details(e, dt, node, config) {
    var args = allUrlParams();
    var meetingid = dt.rows({selected:true}).data()[0].rowid;
    args.meeting_id = meetingid;
    var newsearch = $.param(args);
    var newloclist = window.location.pathname.split('/').slice(0, -1);
    newloclist.push('meeting');
    var newloc = newloclist.join('/') + '?' + newsearch;
    window.location.href = newloc;
}

// view meeting from meetings view
function meeting_status(e, dt, node, config) {
    var args = allUrlParams();
    var meetingid = dt.rows({selected:true}).data()[0].rowid;
    args.meeting_id = meetingid;
    var newsearch = $.param(args);
    var newloclist = window.location.pathname.split('/').slice(0, -1);
    newloclist.push('meetingstatus');
    var newloc = newloclist.join('/') + '?' + newsearch;
    window.location.href = newloc;
}

// view status report from my status reports view
function mymeeting_statusreport(e, dt, node, config) {
    var args = allUrlParams();
    var invitekey = dt.rows({selected:true}).data()[0].invitekey;
    args.invitekey = invitekey;
    var newsearch = $.param(args);
    var newloclist = window.location.pathname.split('/').slice(0, -1);
    newloclist.push('memberstatusreport');
    var newloc = newloclist.join('/') + '?' + newsearch;
    window.location.href = newloc;
}

// hide/show fields for discussionitems child table
function discussionitems_postcreate(dt, ed) {
    if (ed) {
        // only show hidden_reason field if is_hidden is true (yes)
        ed.dependent('hidden_reason', function(val, data, callback) {
            return val === '' ?
                { hide: 'hidden_reason', animate: false } :
                { show: 'hidden_reason', animate: false }
        });
    }
}


