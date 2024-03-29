$( function () {
    // if groups are being used, need to set up translation variables before datatables is initialized
    // required for datatables option {serverside:true}
    register_group_for_datatable('interest', '#metanav-select-interest');
});

// ckeditor default toolbar
// This represents the toolbar in #414
// copied from ckeditor build's sample.html
// built via https://ckeditor.com/ckeditor-5/online-builder/
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
            'outdent',
            'indent',
            '|',
            'imageUpload',
            'blockQuote',
            'insertTable',
            'undo',
            'redo'
        ]
    },
    image: {
        toolbar: [
            'imageTextAlternative',
            'imageStyle:full',
            'imageStyle:side'
        ]
    },
    simpleUpload: {
        // The URL that the images are uploaded to, must match flask-reuploaded configuration
        uploadUrl: '/admin/uploads',

        // Enable the XMLHttpRequest.withCredentials property.
        withCredentials: true,

        // Headers sent along with the XMLHttpRequest to the upload server.
        headers: {
            'X-CSRF-TOKEN': 'CSRF-Token',
            Authorization: 'Bearer <JSON Web Token>'
        }
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
 * show error message modal
 *
 * @param message - message to display
 */
function showerrorpopup(message) {
    var error = $('<div>');
    error.append(message);
    error.dialog({
        title: 'Error',
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

var meeting_invites_editor;

function meeting_sendinvites(url) {
    fn = function (e, dt, node, config) {
        var that = this;

        // update the url parameter for the create view
        var editorajax = meeting_invites_editor.ajax() || {};
        editorajax.url = url + '?' + setParams(allUrlParams());
        meeting_invites_editor.ajax(editorajax);

        // refresh invites and send mail if successful
        $.ajax( {
            // application specific: my application has different urls for different methods
            url: url + '?' + setParams(allUrlParams()),
            type: 'get',
            dataType: 'json',
            success: function ( json ) {
                // if error, display message - application specific
                if (json.error) {
                    // this is application specific
                    // not sure if there's a generic way to find the current editor instance
                    meeting_invites_editor.error(json.error);
                    showerrorpopup(json.error);

                } else {
                    // create table from json response. for some reason need dummy div element
                    // else html doesn't have <table> in it
                    var invites = $('<div>');
                    var invitestbl = $('<table style="margin-left: 1em">');
                    invites.append(invitestbl);
                    var $th = $('<tr>').append(
                        $('<th>').text('name (email)').attr('align', 'left'),
                        $('<th>').text('state').attr('align', 'left'),
                    ).appendTo(invitestbl);
                    $.each(json.invitestates, function(i, invite) {
                        var $tr = $('<tr>').append(
                            $('<td>').text(invite.name + ' (' + invite.email + ')'),
                            $('<td>').text(invite.state),
                        ).appendTo(invitestbl);
                    });

                    meeting_invites_editor
                        .title('Send ' + invitations_text)
                        .edit(null, false)
                        // no editing id, and don't show immediately
                        .set('invitestates', invites.html())
                        .set('from_email', json.from_email)
                        .set('subject', json.subject)
                        .set('message', json.message)
                        // .set('options', json.options)
                        .open();
                }
            },
            error: function(jqXHR, textStatus, errorThrown) {
                showerrorpopup(textStatus + ' ' + jqXHR.status +' ' + errorThrown);
            }
        } );
    }
    return fn;
}

var meeting_reminders_editor;

/**
 * handles Send Reminders button from Meeting view
 *
 * @param url - url for ajax get / editor submission
 * @returns {fn} - button action
 */
function meeting_sendreminders(url) {
    fn = function (e, dt, node, config) {
        var that = this;

        // Ajax request to refresh the data
        var urlparams = allUrlParams();
        var ids = [];
        var apiids = dt.rows({selected:true}).ids();
        for (i=0; i<apiids.length; i++) {
            ids.push(apiids[i]);
        }
        if (ids.length > 0) {
            urlparams.ids = ids.join(',');
        }

        // update the url parameter for the create view
        var editorajax = meeting_reminders_editor.ajax() || {};
        editorajax.url = url + '?' + setParams(urlparams);
        meeting_reminders_editor.ajax(editorajax);

        // refresh invites and send mail if successful
        $.ajax({
            // application specific: my application has different urls for different methods
            url: url + '?' + setParams(urlparams),
            type: 'get',
            dataType: 'json',
            success: function (json) {
                // if error, display message - application specific
                if (json.error) {
                    // this is application specific
                    // not sure if there's a generic way to find the current editor instance
                    meeting_reminders_editor.error(json.error);
                    showerrorpopup(json.error);

                } else {
                    // create table from json response. for some reason need dummy div element
                    // else html doesn't have <table> in it
                    var invites = $('<div>');
                    if (json.invitestates.reminders.length > 0) {
                        var remindersp = invites.append($('<p>').text('Reminders will be sent to'));
                        var remindersul = $('<ul>');
                        remindersp.append(remindersul);
                        $.each(json.invitestates.reminders, function (i, invite) {
                            remindersul.append($('<li>').text(invite.name + ' (' + invite.email + ')'));
                        });
                    }
                    if (json.invitestates.invites.length > 0) {
                        var invitesp = invites.append($('<p>').text('New ' + invitations_text + ' will be sent to'));
                        var invitesul = $('<ul>');
                        invitesp.append(invitesul);
                        $.each(json.invitestates.invites, function (i, invite) {
                            invitesul.append($('<li>').text(invite.name + ' (' + invite.email + ')'));
                        });
                    }

                    meeting_reminders_editor
                        .title('Send Reminders')
                        .edit(null, false)
                        // no editing id, and don't show immediately
                        .set('invitestates', invites.html())
                        .set('from_email', json.from_email)
                        .set('subject', json.subject)
                        .set('message', json.message)
                        .open();
                }
            },
            error: function(jqXHR, textStatus, errorThrown) {
                showerrorpopup(textStatus + ' ' + jqXHR.status +' ' + errorThrown);
            }
        });
    }
    return fn;
}

var meeting_discussion_saeditor = new SaEditor({
    title: 'Send Discussion Request',
    fields: [
                {name: 'invitestates', data: 'invitestates', label: 'Send to', type: 'display',
                    className: 'field_req full block'},
                {name: 'subject', data: 'subject', label: 'Subject', type: 'text', className: 'field_req full block'},
                {name: 'message', data: 'message', label: 'Message', type: 'ckeditorClassic',
                    className: 'full block'},
                {name: 'from_email', data: 'from_email', label: 'From', type: 'text', className: 'field_req full block'},
            ],
    buttons: [
                'Send Discussion Request',
                {
                    text: 'Cancel',
                    action: function() {
                        this.close();
                    }
                }
            ],
    get_urlparams: function(e, dt, node, config) {
        return {}
    },
    form_values: function(json) {
        // create table from json response. for some reason need dummy div element
        // else html doesn't have <table> in it
        var invites = $('<div>');
        var invitestbl = $('<table style="margin-left: 1em">');
        invites.append(invitestbl);
        var $th = $('<tr>').append(
            $('<th>').text('name (email)').attr('align', 'left'),
            $('<th>').text('state').attr('align', 'left'),
        ).appendTo(invitestbl);
        $.each(json.invitestates, function(i, invite) {
            var $tr = $('<tr>').append(
                $('<td>').text(invite.name + ' (' + invite.email + ')'),
                $('<td>').text(invite.state),
            ).appendTo(invitestbl);
        });

        return {
            invitestates: invites.html(),
            from_email: json.from_email,
            subject: json.subject,
            message: json.message,
        }
    },
});

// need to create this function because of some funkiness of how eval works from the python interface
var meeting_send_discussion_req = function(url) {
    return meeting_discussion_saeditor.edit_button_hook(url);
}

var motion_evote_saeditor = new SaEditor({
    title: 'Send eVote Requests',
    fields: [
                {name: 'evotes', data: 'evotes', label: 'Send to', type: 'display',
                    className: 'field_req full block'},
                {name: 'subject', data: 'subject', label: 'Subject', type: 'text', className: 'field_req full block'},
                {name: 'message', data: 'message', label: 'Message', type: 'ckeditorClassic',
                    className: 'full block'},
                {name: 'from_email', data: 'from_email', label: 'From', type: 'text', className: 'field_req full block'},
            ],
    buttons: [
                'Send eVote Requests',
                {
                    text: 'Cancel',
                    action: function() {
                        this.close();
                    }
                }
            ],
    get_urlparams: function(e, dt, node, config) {
        return {
            motion_id: dt.rows({selected: true}).ids()[0]
        }
    },
    form_values: function(json) {
        // create table from json response. for some reason need dummy div element
        // else html doesn't have <table> in it
        var evotes = $('<div>');
        var evotestbl = $('<table style="margin-left: 1em">');
        evotes.append(evotestbl);
        var $th = $('<tr>').append(
            $('<th>').text('name (email)').attr('align', 'left'),
        ).appendTo(evotestbl);
        $.each(json.tolist, function(i, evote) {
            var $tr = $('<tr>').append(
                $('<td>').text(evote),
            ).appendTo(evotestbl);
        });

        return {
            evotes: evotes.html(),
            from_email: json.from_email,
            subject: json.subject,
            message: json.message,
        }
    },
});

// need to create this function because of some funkiness of how eval works from the python interface
var motion_send_evote_req = function(url) {
    return motion_evote_saeditor.edit_button_hook(url);
}

var position_wizard_editor;

function position_wizard(url) {
    fn = function (e, dt, node, config) {
        var that = this;

        // update the url parameter for the create view
        var editorajax = position_wizard_editor.ajax() || {};
        editorajax.url = url + '?' + setParams(allUrlParams());
        position_wizard_editor.ajax(editorajax);
        // clear and reset dependency
        position_wizard_editor.undependent('effective');
        position_wizard_editor.dependent('effective', {
            url: url + '?' + setParams(allUrlParams()),
            type: 'get',
            dataType: 'json',
        });
        // use the currently selected position id (note only one row can be selected)
        var postion_id = _dt_table.rows({selected:true}).ids()[0];
        var position = _dt_table.rows({selected:true}).data()[0].position;
        position_wizard_editor
            .title('Position Wizard')
            .edit(null, false)
            .set('position', position)
            .set('position_id', postion_id)
            .open();
    }
    return fn;
}

/**
 * action for meeting renew button
 * @returns {function(*, *, *, *): void}
 */
function meeting_renew_button(newdataurl) {
    return function ( e, dt, node, config ) {
        // similar to https://editor.datatables.net/examples/api/duplicateButton.html,
        // but need to recreate the data because otherwise dependence() won't pick up defaults
        var data = dt.rows( {selected: true} ).data()[0];
        $.ajax({
            url: newdataurl + '?meeting_id=' + data.rowid,
            success: function(newdata, textStatus, jqXHR) {
                if (newdata.error) {
                    showerrorpopup(newdata.error);

                } else {
                    // show renewoptions just for this form
                    dt.editor()
                        .show('renewoptions')
                        .disable('meetingtype.id');
                    dt.editor().one('close', function () {
                        dt.editor()
                            .hide('renewoptions')
                            .enable('meetingtype.id');
                    });

                    dt.editor()
                        .create(false, {
                            title: 'Renew',
                            buttons: [
                                {
                                    label: 'Renew Meeting',
                                    action: function () {
                                        this.submit(null, null, function (submitdata) {
                                            submitdata.renew = true;
                                            submitdata.renewid = data.rowid;
                                        })
                                    }
                                },
                                {
                                    text: 'Cancel',
                                    action: function () {
                                        this.close();
                                    }
                                }
                            ]
                        })
                        .set(newdata)
                        .open();
                }
            },
        })
    }
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
        // names must match reports.meeting_reports (python)
        var form = $('<form>', {id: 'doc-form', action: url + '?' + setParams(allUrlParams()), method:'POST'})
        form.append($('<input>', {type: 'checkbox', id:  'agenda', name: 'agenda'}));
        form.append($('<label>', {for: 'agenda', text: 'Agenda'}));
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
 * define editor for send email button
 */
var meeting_email_editor;
/**
 * handles Send Mail button from Meeting view
 *
 * @param url - rest url to send the mail
 * @returns {fn} - button action
 */
function meeting_send_email(url) {
    fn = function (e, dt, node, config) {
        var that = this;

        // Ajax request to refresh the data
        var urlparams = allUrlParams();

        // update the url parameter for the create view
        var editorajax = meeting_email_editor.ajax() || {};
        editorajax.url = url + '?' + setParams(urlparams);
        meeting_email_editor.ajax(editorajax);

        // refresh invites and send mail if successful
        $.ajax({
            // application specific: my application has different urls for different methods
            url: url + '?' + setParams(urlparams),
            type: 'get',
            dataType: 'json',
            success: function (json) {
                // if error, display message - application specific
                if (json.error) {
                    // this is application specific
                    // not sure if there's a generic way to find the current editor instance
                    meeting_email_editor.error(json.error);
                    showerrorpopup(json.error);

                } else {
                    // create table from json response. for some reason need dummy div element
                    // else html doesn't have <table> in it
                    var emaildiv = $('<div>');
                    if (json.invitestates.length > 0) {
                        var emailul = $('<ul style="list-style-type:none;">');
                        emaildiv.append(emailul);
                        $.each(json.invitestates, function (i, invite) {
                            emailul.append($('<li>').text(invite.name + ' (' + invite.email + ')'));
                        });
                    }

                    meeting_email_editor
                        .title('Send Email')
                        .edit(null, false)
                        // no editing id, and don't show immediately
                        .set('invitestates', emaildiv.html())
                        .set('from_email', json.from_email)
                        .set('subject', json.subject)
                        .open();
                }
            },
            error: function(jqXHR, textStatus, errorThrown) {
                showerrorpopup(textStatus + ' ' + jqXHR.status +' ' + errorThrown);
            }
        });
    }
    return fn;
}

function meetings_statusreportwording(meeting) {
    return _.startCase(meeting.statusreportwording);
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
                    var dtebody = $('<div>', {class: 'DTE_Body'});
                    var dtebodycontent = $('<div>', {class: 'DTE_Body_Content'});
                    dtebody.append(dtebodycontent);
                    var form = $('<form>', {id: 'doc-form', action: url, method:'POST'})
                    dtebodycontent.append(form);
                    var responsediv = $('<div>', {class: 'DTE_Field field_req'});
                    form.append(responsediv);
                    responsediv.append($('<label>', {for: 'response', text: 'RSVP', class: 'DTE_Label'}));
                    var attending = $('<select>', {id:  'response', name: 'response', class: 'form-input DTE_Field_Input',
                                                   style: 'width: 60%;'});
                    responsediv.append(attending);
                    for (var i=0; i<data.options.length; i++) {
                        attending.append($('<option>', {value: data.options[i], text: data.options[i]}));
                    }
                    attending.val(data.response);
                    attending.select2({
                        minimumResultsForSearch: Infinity
                    });

                    var attend_typediv = $('<div>', {class: 'DTE_Field field_req'});
                    form.append(attend_typediv);
                    attend_typediv.append($('<label>', {for: 'attend_type', text: 'in person/virtual', class: 'DTE_Label'}));
                    var attend_type = $('<select>', {id:  'attend_type', name: 'attend_type', class: 'form-input DTE_Field_Input',
                                                   style: 'width: 60%;'});
                    attend_typediv.append(attend_type);
                    for (var i=0; i<data.attend_type_options.length; i++) {
                        attend_type.append($('<option>', {value: data.attend_type_options[i], text: data.attend_type_options[i]}));
                    }
                    attend_type.val(data.attend_type);
                    attend_type.select2({
                        minimumResultsForSearch: Infinity
                    });

                    // set default attend_type to the top option if not already set
                    if (attend_type.val() == null) {
                        // see https://stackoverflow.com/a/42898862/799921
                        attend_type.val(attend_type[0][0].value).trigger('change');
                    }

                    // show attend_type only when attending shows user is actually attending the meeting
                    function check_attending() {
                        if (attending.val() == 'attending') {
                            attend_typediv.show();
                        } else {
                            attend_typediv.hide();
                        }
                    }
                    $(attending).change(function(){
                        check_attending();
                    });
                    check_attending();

                    // adapted from https://www.tjvantoll.com/2013/07/10/creating-a-jquery-ui-dialog-with-a-submit-button/
                    dtebody.dialog({
                        title: 'RSVP',
                        modal: true,
                        width: 600,
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
                                    // post and handle acknowledgement
                                    var post = $.post(url, formfields, function(data, textStatus, jqXHR) {
                                        if (textStatus === "success") {
                                            if (data.status === "success") {
                                                // need to remove no response indicator from button, unless they hit
                                                // save without changing anything
                                                if (formfields.response != 'response pending') {
                                                    $('.rsvp-noresponse').removeClass('rsvp-noresponse');
                                                }
                                                dtebody.dialog('close');
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
                                    dtebody.dialog('close');
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
    // only one row can be selected
    var row = dt.rows({selected:true}).data()[0];
    if (!row.hideviewicon) {
        var args = allUrlParams();
        var invitekey = row.invitekey;
        args.invitekey = invitekey;
        var newsearch = $.param(args);
        var newloclist = window.location.pathname.split('/').slice(0, -1);
        newloclist.push('memberstatusreport');
        var newloc = newloclist.join('/') + '?' + newsearch;
        window.location.href = newloc;
    }
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
            .title('Add ad hoc ' + statusreport_text)
            .buttons('Create')
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

/**
 * return function handles View Motion Vote button from My Motion Votes view
 *
 * @param url - url to navigate to
 * @returns {function(e, dt, node, config): void}
 */
function mymotionvote_motionvote(url) {
    return function(e, dt, node, config) {
        var args = allUrlParams();
        var motionvotekey = dt.rows({selected:true}).data()[0].motionvotekey;
        args.motionvotekey = motionvotekey;
        var newsearch = $.param(args);
        var newloc = url + '?' + newsearch;
        window.location.href = newloc;
    }
}

