$.fn.dataTable.ext.buttons.newInvites = {
    extend: 'create',
    text: 'Send Invites',
    action: function (e, dt, node, config) {
        var that = this;

        // force translation of group variable, handler is in afterdatatables.js
        config.editor._event( 'preInvites', [dt, config.editor.s.action] )

        // Ajax request to refresh the data for those ids
        $.ajax( {
            // application specific: my application has different urls for different methods
            url: config.editor.ajax().create.url,
            type: 'post',
            dataType: 'json',
            data: {
                // application specific: my application wants 'action' in the POST method data
                action: 'checkinvites',
            },
            success: function ( json ) {
                // if error, display message - application specific
                if (json.error) {
                    // this is application specific
                    // not sure if there's a generic way to find the current editor instance
                    config.editor.error('ERROR retrieving row from server:<br>' + json.error);

                } else {
                    // create table from json response. for some reason need dummy div element
                    // else html doesn't have <table> in it
                    var invitestbl = $('<table>')
                    var invites = $('<div>').append(invitestbl)
                    var $th = $('<tr>').append(
                        $('<th>').text('name').attr('align', 'left'),
                        $('<th>').text('email').attr('align', 'left'),
                        $('<th>').text('state').attr('align', 'left'),
                    ).appendTo(invitestbl);
                    $.each(json.checkinvites, function(i, invite) {
                        var $tr = $('<tr>').append(
                            $('<td>').text(invite.name),
                            $('<td>').text(invite.email),
                            $('<td>').text(invite.state),
                        ).appendTo(invitestbl);
                    });

                    config.editor
                        .message(invites.html())
                        .hide()
                        .create('Meeting Attendees', [
                            {
                                'text': 'Send Invitations',
                                'action': function () {
                                    this.submit( null, null, function(data){
                                        var that = this;
                                        data.action = 'sendinvites'
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
                        // need to set to 'no' else dependent() shows it
                        .field('is_hidden').val('no');

                    // show appropriate fields again after the form closes, based on original option
                    // is there a better way? asked in
                    // https://datatables.net/forums/discussion/64236/how-to-best-determine-original-type-option
                    config.editor.one('submitComplete preClose', function(e) {
                        config.editor.show();
                        var fields = config.editor.order();
                        for (var i=0; i<fields.length; i++) {
                            var field = fields[i];
                            // warning: using editor internals, not from API
                            if (config.editor.s.fields[field].s.opts.type === "hidden") {
                                config.editor.field(field).hide();
                            }
                        }
                    })
                }

            }
        } );
    }
};
