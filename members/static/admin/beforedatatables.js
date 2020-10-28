$( function () {
    // if groups are being used, need to set up translation variables before datatables is initialized
    // required for datatables option {serverside:true}
    register_group_for_datatable('interest', '#metanav-select-interest');
});

// This represents the toolbar in #279
// copied from ckeditor build's sample.html
ClassicEditor.defaultConfig = {
    toolbar: {
        items: [
            'heading',
            '|',
            'bold',
            'italic',
            'underline',
            'link',
            'bulletedList',
            'numberedList',
            'alignment',
            'strikethrough',
            'removeFormat',
            '|',
            'indent',
            'outdent',
            '|',
            'blockQuote',
            'insertTable',
            'undo',
            'redo'
        ]
    },
    language: 'en',
    table: {
        contentToolbar: [
            'tableColumn',
            'tableRow',
            'mergeTableCells',
            'tableCellProperties',
            'tableProperties'
        ]
    },
    licenseKey: '',

}

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

/**
 * handles Send Reminders button from Meeting view
 *
 * @param ed - editor instance
 * @returns {fn} - button action
 */
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

/**
 * handles Generate Docs button from Meeting view
 *
 * @param url - rest url to generate the documents
 * @returns {fn} - button action
 */
function meeting_generate_docs(url) {
    fn = function() {
        var that = this;
        var formerror;
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
            close: function(event, ui) {
                that.processing(false);
            },
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
                            if (textStatus === "success") {
                                if (data.status === "success") {
                                    form.dialog('close');
                                } else {
                                    formerror.text(data.error);
                                    formerror.show();
                                }
                            } else {
                                formerror.text('error occurred: ' + textStatus);
                                formerror.show();
                            }
                        });
                    },
                },
                {
                    text: 'Cancel',
                    click: function() {
                        form.dialog('close');
                    }
                },
            ]
        });

        // need to create formerror div after dialog shown
        $('.ui-dialog-buttonpane').append($('<div>', {id: 'form-error', 'class': 'DTE_Form_Error'}))
        formerror = $('.ui-dialog-buttonpane #form-error');
        formerror.hide();
    }
    return fn;
}

/**
 * handles Send Mail button from Meeting view
 *
 * @param url - rest url to send the mail
 * @returns {fn} - button action
 */
function meeting_send_email(url) {
    fn = function() {
        var that = this;
        var formerror;
        that.processing(true);

        // allUrlParams() picks up at least meeting_id
        var form = $('<form>', {id: 'doc-form', action: url + '?' + setParams(allUrlParams()), method:'POST'})
        var subjectdiv = $('<div>', {class: 'DTE_Field field_req'});
        form.append(subjectdiv);
        subjectdiv.append($('<label>', {for: 'subject', text: 'Subject', class: 'DTE_Label'}));
        var subject = $('<input>', {type: 'text', id:  'subject', name: 'subject', class: 'form-input DTE_Field_Input'});
        subject.val('[' + $('#meeting_purpose').text() + ' ' + $('#meeting_date').text() + '] ');
        subjectdiv.append(subject);
        form.append($('<br>'));
        var messagediv = $('<div>', {class: 'DTE_Field field_req'});
        form.append(messagediv);
        messagediv.append($('<label>', {for: 'message', text: 'Message'}));
        messagediv.append($('<br>'));
        messagediv.append($('<div>', {id:  'message', name: 'message', width: 'auto'}).addClass('form-input'));
        var msgeditor;
        ClassicEditor
            .create( form.find('#message')[0] )
            .then( function( newEditor) {
                msgeditor = newEditor;
            })
            .catch( function(error) {
                    console.error(error)
            });

        // adapted from https://www.tjvantoll.com/2013/07/10/creating-a-jquery-ui-dialog-with-a-submit-button/
        form.dialog({
            title: 'Send Email to Invitees',
            modal: true,
            minWidth: 600,
            height: 'auto',
            close: function(event, ui) {
                that.processing(false);
            },
            buttons: [
                {
                    text: 'Submit',
                    click: function() {
                        var url = form.attr( "action" );
                        var terms = {};
                        var inputs = form.find('.form-input');
                        inputs.each(function() {
                            // .val() works for input, .getData() works for ckeditor content
                            if ($(this).hasClass('ck-content')) {
                                terms[$(this).attr('name')] = msgeditor.getData();
                            } else {
                                terms[$(this).attr('name')] = $(this).val();
                            }
                        });
                        var post = $.post(url, terms, function(data, textStatus, jqXHR) {
                            if (textStatus === "success") {
                                if (data.status === "success") {
                                    form.dialog('close');
                                    var confirmation = $('<div>', {title: 'Sent mail to'});
                                    var tolist = $('<ul>').appendTo(confirmation);
                                    if (data.sent_to.length > 0) {
                                        $.each(data.sent_to, function (ndx, val) {
                                            $('<li>', {text: val}).appendTo(tolist)
                                        })
                                    } else {
                                        $('<li>', {text: 'No mail sent - use Send Invites before Send Email'}).appendTo(tolist)
                                    }
                                    confirmation.dialog({
                                        modal: true,
                                        minWidth: 600,
                                        height: 'auto',
                                        buttons: {
                                            OK: function() {
                                                $(this).dialog('close');
                                            }
                                        }
                                    });

                                } else {
                                    formerror.text(data.error);
                                    formerror.show();
                                }
                            } else {
                                formerror.text('error occurred: ' + textStatus);
                                formerror.show();
                            }
                        });
                    },
                },
                {
                    text: 'Cancel',
                    click: function() {
                        form.dialog('close');
                    }
                },
            ]
        });

        // need to create formerror div after dialog shown
        $('.ui-dialog-buttonpane').append($('<div>', {id: 'form-error', 'class': 'DTE_Form_Error'}))
        formerror = $('.ui-dialog-buttonpane #form-error');
        formerror.hide();
    }
    return fn;
}

/**
 * handles RSVP button from My Status Report view
 *
 * @param url - rest url
 * @returns {fn} - button action
 */
function mystatus_rsvp(url) {
    fn = function() {
        var that = this;
        var formerror;
        that.processing(true);

        // url is preset including invitekey
        var get = $.get(url, function(data, textStatus, jqXHR) {
            if (textStatus === "success") {
                if (data.status === "success") {
                    var form = $('<form>', {id: 'doc-form', action: url, method:'POST'})
                    var responsediv = $('<div>', {class: 'DTE_Field field_req'});
                    form.append(responsediv);
                    responsediv.append($('<label>', {for: 'response', text: 'RSVP', class: 'DTE_Label'}));
                    var attending = $('<select>', {id:  'response', name: 'response', class: 'form-input DTE_Field_Input',
                                                   style: 'width: 80%;'});
                    responsediv.append(attending);
                    for (var i=0; i<data.options.length; i++) {
                        attending.append($('<option>', {value: data.options[i], text: data.options[i]}));
                    }
                    attending.val(data.response);
                    attending.select2({
                        minimumResultsForSearch: Infinity
                    });

                    // adapted from https://www.tjvantoll.com/2013/07/10/creating-a-jquery-ui-dialog-with-a-submit-button/
                    form.dialog({
                        title: 'RSVP',
                        modal: true,
                        minWidth: 400,
                        height: 'auto',
                        close: function(event, ui) {
                            that.processing(false);
                        },
                        buttons: [
                            {
                                text: 'Save',
                                click: function() {
                                    var url = form.attr( "action" );
                                    var formfields = {};
                                    var inputs = form.find('.form-input');
                                    inputs.each(function() {
                                        formfields[$(this).attr('name')] = $(this).val();
                                    });
                                    var post = $.post(url, formfields, function(data, textStatus, jqXHR) {
                                        if (textStatus === "success") {
                                            if (data.status === "success") {
                                                form.dialog('close');
                                            } else {
                                                formerror.text(data.error);
                                                formerror.show();
                                            }
                                        } else {
                                            formerror.text('error occurred: ' + textStatus);
                                            formerror.show();
                                        }
                                    });
                                },
                            },
                            {
                                text: 'Cancel',
                                click: function() {
                                    form.dialog('close');
                                }
                            },
                        ]
                    });
            
                    // need to create formerror div after dialog shown
                    $('.ui-dialog-buttonpane').append($('<div>', {id: 'form-error', 'class': 'DTE_Form_Error'}))
                    formerror = $('.ui-dialog-buttonpane #form-error');
                    formerror.hide();

                } else {
                    var buttonerror = $('#mystatus_button_error');
                    buttonerror.text(data.error);
                    buttonerror.show();
                    that.processing(false);
                }
            } else {
                var buttonerror = $('#mystatus_button_error');
                buttonerror.text('error occurred: ' + textStatus);
                buttonerror.show();
                that.processing(false);
            }
        });

    }
    return fn;
}

/**
 * handles Instructions button for My Status Report view
 *
 * @returns {fn}
 */
function mystatus_instructions() {
    fn = function() {
        var instructions = $('#mystatus-instructions');
        instructions.dialog({
            title: 'Instructions',
            modal: false,
            minWidth: 600,
            height: 'auto',
            buttons: {
                OK: function() {
                    $(this).dialog('close');
                }
            }
        });
    }
    return fn
}

function render_month_date(data, type, row, meta) {
    if (data) {
        return data.slice(-5)
    } else {
        return data
    }
}

/**
 * handles View Member button from Member Summary view
 * @param e
 * @param dt
 * @param node
 * @param config
 */
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

/**
 * handles View Meeting button from Meetings view
 * @param e
 * @param dt
 * @param node
 * @param config
 */
function meetings_details(e, dt, node, config) {
    var args = allUrlParams();
    var meetingid = dt.rows({selected:true}).data()[0].rowid;
    args.meeting_id = meetingid;
    var newsearch = $.param(args);
    var newloclist = window.location.pathname.split('/').slice(0, -1);
    newloclist.push('meeting');
    var newloc = newloclist.join('/') + '?' + newsearch;
    window.location.href = newloc;
}

/**
 * handles Meeting Status button from Meetings view
 * @param e
 * @param dt
 * @param node
 * @param config
 */
function meetings_status(e, dt, node, config) {
    var args = allUrlParams();
    var meetingid = dt.rows({selected:true}).data()[0].rowid;
    args.meeting_id = meetingid;
    var newsearch = $.param(args);
    var newloclist = window.location.pathname.split('/').slice(0, -1);
    newloclist.push('meetingstatus');
    var newloc = newloclist.join('/') + '?' + newsearch;
    window.location.href = newloc;
}

/**
 * handles Their Status Report button from Meetings view
 * @param e
 * @param dt
 * @param node
 * @param config
 */
function meetings_theirstatusreport(e, dt, node, config) {
    var args = allUrlParams();
    var meetingid = dt.rows({selected: true}).data()[0].rowid;
    args.meeting_id = meetingid;
    var newsearch = $.param(args);
    var newloclist = window.location.pathname.split('/').slice(0, -1);
    newloclist.push('theirstatusreport');
    var newloc = newloclist.join('/') + '?' + newsearch;
    window.location.href = newloc;
}

/**
 * handles View Status Report button from My Status Reports view
 * @param e
 * @param dt
 * @param node
 * @param config
 */
function mystatus_statusreport(e, dt, node, config) {
    var args = allUrlParams();
    var invitekey = dt.rows({selected:true}).data()[0].invitekey;
    args.invitekey = invitekey;
    var newsearch = $.param(args);
    var newloclist = window.location.pathname.split('/').slice(0, -1);
    newloclist.push('memberstatusreport');
    var newloc = newloclist.join('/') + '?' + newsearch;
    window.location.href = newloc;
}

/**
 * handles New button from My Status Reports view
 * @param e
 * @param dt
 * @param node
 * @param config
 */
function mystatus_create(e, dt, node, config) {
    var that = this;
    var show_editor = function() {
        dt.editor()
            .title('Add ad hoc status report')
            .buttons('Save')
            .create();
    }
    var missing_reports = [];
    var reports = dt.data();
    for (var i=0; i<reports.length; i++) {
        var report = reports[i];
        if (report.position_id !== "" && (report.statusreport === null || report.statusreport === "")) {
            missing_reports.push(report.title);
        }
    }
    if (missing_reports.length != 0) {
        var messagediv = $('<div>',
            {
                class: 'DTE_Field field_req',
                title: 'WARNING!'
            });
        messagediv.append($('<p>', {
            text: 'Creating a "New" status report starts a report for a topic outside your assigned position(s), which ' +
                'is fine, but may not be what you want to do. Please use the preassigned Position status report(s) to ' +
                'report on your assigned role(s). '
        }));
        messagediv.append($('<p>', {text: 'Empty Position reports:'}))
        var list = messagediv.append($('<ul>'));
        for (var i=0; i<missing_reports.length; i++) {
            list.append('<li>'+ missing_reports[i] + '</li>');
        }
        messagediv.append($('<p>', {text: 'Continue to create a new ad hoc report'}));
        messagediv.append($('<p>', {text: 'Cancel to edit your Position reports'}));
        messagediv.dialog({
            modal: true,
            minWidth: 400,
            height: 'auto',
            dialogClass: 'new-challenge',
            buttons: [
                {
                    text: 'Continue',
                    click: function () {
                        $(this).dialog('close');
                        show_editor();
                    },
                },
                {
                    text: 'Cancel',
                    click: function () {
                        $(this).dialog('close');
                    }
                }

            ],
        });
        // #ffc107 from https://getbootstrap.com/docs/4.0/utilities/colors/
        $('.new-challenge').children('.ui-dialog-titlebar')
            .prepend('<span style="float: left;">&nbsp;</span>')
            .prepend('<i class="fa fa-exclamation-circle" style="color: #ffc107; font-size: 125%; float: left;">');
    } else {
        show_editor();
    }
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


