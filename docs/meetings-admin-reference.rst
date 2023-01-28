*******************************************
Meetings Admin Reference
*******************************************

This page gives a reference to all **membertility** views which are available to
:term:`members <member>` who have the :term:`meeting admin` :term:`security role`.

.. _Action Items view:

Action Items view
======================

:term:`Action Items <action item>` can be accessed from :ref:`Meeting view` or from the top level menu.
:term:`Action Items <action item>` are normally generated from :ref:`Meeting view`, but all action items can
be seen from the top level menu.

    :Action:
        text of the action item describing the action to be done

    :Assignee:
        who is responsible for taking care of the action item

    :Status:
        current action item status: *open*, *inprogress*, *closed*

    :Comments:
        updates on progress or how the action item was completed

Meeting Action Items
---------------------
**Navigation:** [:ref:`Meeting view`] > [select agenda item] > **Edit**

.. note::
    all action items since **Show Actions Since** date can be viewed or edited under the automatically created
    *Action Items* agenda item

.. image:: images/meeting-action-items-view.*
    :align: center

.. image:: images/meeting-action-items-edit.*
    :align: center

All Action Items
--------------------
**Navigation:** Meetings > Action Items

Additional fields shown in the All Action Items view

    :Meeting:
        :term:`meeting` at which this action item was created

    :Date:
        date for :term:`meeting` that this action was created

The view has the following filters:

    :Date:
        date range of interest

    :Assignee:
        who is responsible for taking care of the action item

    :Status:
        current **Status** of interest

.. image:: images/action-items-view.*
    :align: center

.. image:: images/action-items-edit.*
    :align: center


.. _Agenda Headings view:

Agenda Headings view
======================
**Navigation:** Meetings > Agenda Headings

Agenda Headings can be configured to show context for :term:`agenda items <agenda item>`. An agenda heading must
be configured here before being added to the :term:`agenda items <agenda item>` on :ref:`Meeting view`.

    :Agenda Heading:
        text of heading which will appear in the :term:`Agenda <agenda>` document or the :term:`Minutes <minutes>`
        document

    :Positions:
        (optional) when a :term:`discussion item` is created for one of these :term:`positions <position>`, this
        agenda heading will be used

        .. note::
            if multiple agenda headings share a :term:`position`, the behavior is undefined [#256]

.. image:: images/agenda-headings-view.*
    :align: center

.. image:: images/agenda-headings-edit.*
    :align: center


.. _Invites view:

Invites view
======================
**Navigation:** Meetings > Invites

    :Meeting:
        :term:`meeting` at which this motion was created

    :Date:
        date for :term:`meeting` that this motion created

    :Name:
        name of the :term:`member` invited to the :term:`meeting`

    :Email:
        email address of the :term:`member` invited to the :term:`meeting`

    :RSVP:
        the :term:`member's <member>` :term:`rsvp` response when invited to the :term:`meeting`

    :Attended:
        indication of whether the :term:`member` attended the meeting, *yes* or *no*

    :In person/Virtual:
        if the :term:`meeting` includes the option *RSVP Required*, this shows whether
        the :term:`member` plans to or has attended *in person* or *virtual*

    :Invited:
        generally *yes* but if the :term:`member's <member>` :term:`position` changed after the initial
        :term:`invite` was sent, may be *no*

The view has the following filters:

    :Date:
        date range of interest

    :Name:
        name of :term:`member`

    :Attended:
        attendance value of interest

.. image:: images/invites-view.*
    :align: center

.. image:: images/invites-edit.*
    :align: center


.. _Meeting Status view:

Meeting Status view
======================
**Navigation:** Meetings > Meetings > [select meeting] > **Meeting Status**

The Meeting Status view is used to determine what, if any, status reports are missing, and to send reminders to
chosen positions about the missing status report(s).

    :Position:
        :term:`positions <position>` which are configured to have a status report are listed here

    :Members (last request):
        :term:`member(s) <member>` who hold the position are listed here, along with the date the last request
        for status report was made to that :term:`member`. If a date isn't listed, this means the :term:`member`
        was added to a :term:`position`, but wasn't sent a :term:`meeting` :term:`invite`, which should
        be a transient condition

    :Status Report:
        either *entered* if someone holding this :term:`position` entered a :term:`status report`, or *missing* if no
        :term:`status report` was entered

The view has the following filters:

    :Status:
        the status of whether the :term:`status report` was *entered* or *missing* can be selected here


.. image:: images/meeting-status-view.*
    :align: center

There is one action button.

    :Send Reminders:
        select the row(s) for which a reminder should be sent. The :term:`members <member>` who hold the selected
        :term:`positions <position>` will be sent a reminder.

        :Subject:
            default subject is provided by the system, but can be changed if desired

        :Message:
            add additional message to the reminder if desired

        :From:
            defaults to **From** from the last **Send Invites** or **Send Reminders** (see note), but can be updated
            if desired

        :option checkboxes:
            * check **Request Status Report** if the text in the email should mention that a status report is needed
            * check **Show Action Items** if outstanding action items should be shown in the email

        .. note::
            For best results, set the **Status** filter to *missing* before using **Send Reminders**

        .. note::
            **Message**, **From**, and option checkboxes default from the last **Send Reminders**, or the last
            :ref:`Meeting view`'s **Send Invites** if **Send Reminders** hasn't been used for this meeting

.. image:: images/meeting-status-reminders.*
    :align: center


.. _Meeting view:

Meeting view
======================
**Navigation:** Meetings > Meetings > [select meeting] > **View Meeting**

The meeting view is used to manage the :term:`meeting`. The following can be done from this view

* send :term:`meeting` :term:`invites <invite>`
* create new :term:`agenda` items
* rearrange :term:`agenda` items
* generate documents related to the meeting
* send email to :term:`members <member>` who were :term:`invited <invite>` to the meeting
* tally :term:`meeting` attendance
* record discussion about :term:`agenda` items
* create :term:`action items <action item>`
* create and record votes on :term:`motions <motion>`

Edit of an :term:`agenda` item is inline with the table, with :ref:`Action Items view` and :ref:`Motions view` embedded.

    :Reorder:
        the reorder icon (|reorder-icon|) can be used to grab an :term:`agenda item` and place it where desired in the
        :term:`agenda` order

        .. |reorder-icon| image:: images/reorder-icon.*

    :Title:
        title of the :term:`agenda` item, initialized by the :term:`invitee <invite>` who wrote the discussion item,
        but can be changed

    :Summary:
        summary of the :term:`agenda` item, initialized by the :term:`invitee <invite>` who wrote the discussion item.
        This can be changed, but normally would be left intact except for editorial changes for clarity

    :Discussion:
        discussion which took place at the meeting, if the :term:`meeting admin` wants to record this in the minutes

    :Agenda Heading:
        heading under which this :term:`agenda` item will be shown in the agenda and in the minutes. The Agenda Headings
        are configured under :ref:`Agenda Headings view`

    :Hide:
        if, for some reason, a :term:`discussion item` recorded by an :term:`invitee <invite>` will not be part of the
        :term:`meeting` :term:`agenda`, set **Hide** to *yes* and fill in **Reason for Hiding**

    :Reason for Hiding:
        if **Hide** is set to *yes*, the reason the :term:`agenda` item was hidden should be entered here. The
        :term:`invitee <invite>` will be able to see this from their :ref:`My Status Report view`

In addition to the **New**, **Edit**, **Delete** buttons, there are action buttons. Action buttons are shown or not
depending on which **Meeting Type** was chosen (configured in the :ref:`Meeting Types view`).

    :Send Invitations:
        use this to send the initial :term:`invitations <invite>` to the meeting, or if any positions have been updated
        which affect the meeting attendance. Individual emails are sent which include a link that the :term:`member`
        can use to :term:`RSVP <rsvp>` and/or update their :term:`status reports <status report>`

        :Subject:
            default subject is provided by the system, but can be changed if desired

        :Message:
            add additional message to the invitiation if desired

        :From:
            defaults to the email address of the :term:`meeting` **Organizer**, but can be updated if desired

        .. note::
            if any positions which affect meeting attendance have been updated, a nightly job will take care of
            sending additional :term:`invitations <invite>`

    :Send Discussion Request:
        use this to send a discussion request for the meeting. A single email is sent to the :term:`invitees <invite>`,
        suitable for a *reply/all* discussion

        :Subject:
            default subject is provided by the system, but can be changed if desired

        :Message:
            add additional message to the invitiation if desired

        :From:
            defaults to the email address of the :term:`meeting` **Organizer**, but can be updated if desired

    :Generate Docs:
        use this to generate documents associated with the meeting

        .. note::
            the :term:`status report` document is automatically created and updated as people write or update
            their status reports

        .. note::
            for upcoming meetings, a nightly process regenerates the :term:`agenda`, in case changes
            are made which would affect it. This does not apply to :term:`minutes` since these are normally
            generated after the meeting


    :Send Email:
        use this to send email to the :term:`invitees <invite>`. Note the
        default subject contains the meeting purpose and date, and can be edited

        :Subject:
            default subject is provided by the system, but can be changed if desired

        :Message:
            add message

        :From:
            defaults to the email address which was used during **Send Invites**, but can be updated if desired


.. image:: images/meeting-all-buttons.*
    :align: center

.. image:: images/meeting-view.*
    :align: center

.. image:: images/meeting-send-invites.*
    :align: center

.. image:: images/meeting-send-discussion-req.*
    :align: center

.. image:: images/meeting-generate-docs.*
    :align: center

.. image:: images/meeting-send-email.*
    :align: center

.. image:: images/meeting-edit.*
    :align: center


.. _Meetings view:

Meetings view
=================
**Navigation:** Meetings > Meetings

This is the main view for managing :term:`meetings <meeting>`. The meeting can be created or edited. Once created
this view is used to navigate to the individual meeting for administration purposes.

    :Purpose:
        short name of the meeting, e.g., Board Meeting

    :Meeting Type:
        type of the meeting, as created by :ref:`Meeting Types view`

    :Date:
        date the meeting will take place

    :Time:
        time of the meeting (optional, depending on **Meeting Type**)

    :Location:
        location of the meeting, either a physical address or a URL (e.g., for Google Meet) (optional,
        depending on **Meeting Type**)

    :Show Actions Since:
        action items are shown in agenda, minutes, etc. Any action items which have been updated after this
        date will be shown associated with this meeting (optional, depending on **Meeting Type**)

    :Organizer:
        the meeting organizer. When emails are sent from this view, the **From** address will default to this
        :term:`member's <member>` email address. This defaults to the currently logged in member

    :Invite Tags:
        :term:`members <member>` who are associated with these :term:`tags <tag>` through their :term:`position` will be
        invited to the :term:`meeting`

    :Vote Tags:
        :term:`members <member>` who are associated with these :term:`tags <tag>` through their :term:`position` may
        vote on :term:`motions <motion>` associated with the :term:`meeting`

    :Status Report Tags:
        :term:`members <member>` who are associated with these :term:`tags <tag>` through their :term:`position` will
        be prompted to provide :term:`position` :term:`status reports <status report>`

    :Agenda:
        this is the link to the :term:`agenda` document

    :Status Report:
        this is the link to the :term:`status report` document

    :Minutes:
        this is the link to the :term:`minutes` document

In addition to the **New**, **Edit**, **Delete** buttons, there is one additional meeting creation button

    :Renew:
        this allows the :term:`meeting admin` to create a new :term:`meeting` just like the selected previous meeting, but
        on a different date

and these navigation buttons

    :View Meeting:
        this is the view for the :term:`meeting` which can be used to prepare the :term:`agenda` or during the
        :term:`meeting`, brings up :ref:`Meeting view`

    :Meeting Status:
        this gives status of the :term:`meeting`, showing missing and entered status reports. This
        brings up :ref:`Meeting Status view`

    :Their Status Report:
        this allows the :term:`meeting admin` to :term:`RSVP <rsvp>` and enter :term:`status reports <status report>`
        on behalf of another :term:`member`. This brings up :ref:`Their Status Report view`

The view has the following filters:

    :Meeting Types:
        :term:`meeting types <meeting type>` of interest

.. image:: images/meetings-view.*
    :align: center

.. image:: images/meetings-edit.*
    :align: center

**Renew** allows the :term:`meeting admin` to select options for renewing the meeting. The defaults for these
options are set in :ref:`Meeting Types view`. See :ref:`Meeting Types view` for a description of how these options
work

.. image:: images/meetings-renew.*
    :align: center

.. _Meeting Types view:

Meeting Types view
======================
**Navigation:** Meetings > Meeting Types

The Meeting Types view is used to control the behavior of the :ref:`Meeting view`, and to identify which buttons
should be shown.

    :Meeting Type:
        name of the meeting type

    :Automatic Agenda Item Title:
        if this is specified, when the meeting is created an agenda item will be created in the meeting with this
        title. Note this can include text of the form {{ purpose }} or {{ meetingtype.statusreportwording }} which
        is templated against the meeting record. See the administrator for acceptable template variables.

    :Custom Wording for "meeting":
        if you don't want the text on the page and emails to say something other than "meeting" you can customize that
        here. Use lowercase letters.

    :Custom Wording for "status report":
        if you want the text on the page and emails to say something other than "status report" you can customize that
        here. Use lowercase letters.

    :Custom Wording for "invitation":
        if you want the text on the page and emails to say something other than "invitation" you can customize that
        here. Use lowercase letters.

    :Meeting Options:
        these control the behavior of the :ref:`Meeting view` for meetings of this **Meeting Type**

            * *RSVP Required* - require the :term:`member` to :term:`RSVP <rsvp>` to the meeting
            * *Time Required* - require the :term:`meeting admin` to add **Time** when creating the :term:`meeting`
            * *Location Required* - require the :term:`meeting admin` to add **Location** when creating the :term:`meeting`
            * *Has Status Reports* - the :term:`member` will be shown a page which allows creation of
              :term:`status reports <status report>`
            * *Show Action Items* - require the :term:`meeting admin` to add **Show Actions Since** when creating the :term:`meeting`.
              The :ref:`Meeting view` will show and agenda item with :term:`action items <action item>`
            * *Allow Online Motion/Votes* - the :ref:`Motions view` within a meeting agenda item will have a button
              to **Send eVote Requests**

    :Meeting Button Options:
        these control what buttons to show for the :ref:`Meeting view`. See :ref:`Meeting view` for the description
        of each button's behavior

            * *Send Invitations* - this button should be configured if the **Meeting Options**
              include *RSVP Required* and/or *Has Status Reports*.
            * *Send Discussion Request* - this button should be configured if the **Meeting Options**
              include *Allow Online Motion/Votes*
            * *Generate Docs* - this button should be configured if the :term:`meeting` will include an :term:`agenda`
              or :term:`minutes`
            * *Send Email* - this button should be configured if there will be any need to send email to the
              :term:`invitees <invite>` after invitations are sent out

    :Meeting Renew Options:
        these control how meetings of this type are renewed

            * *Show Actions Since Last Meeting* - if checked, the **Show Actions Since** for the new :term:`meeting`
              will be set to the date of the last meeting
            * *Copy Invite Email* - if checked, the text which was sent in the invite email will be copied from the
              last meeting's
            * *Copy Reminder Email* - if checked, the text which was sent in the reminder email will be copied from
              the last meeting's
            * *Copy Agenda Summary* - if checked, :term:`agenda` titles and summaries will be copied from the last
              meetings's
            * *Copy Agenda Discussion* - if checked, :term:`agenda` titles and discussions from the last meeting will
              be copied into the new meetings agenda summaries

.. image:: images/meeting-types-view.*
    :align: center

.. image:: images/meeting-types-edit.*
    :align: center


.. _Motion Votes view:

Motion Votes view
======================
**Navigation:** Meetings > Motion Votes

:term:`Motion <motion>` :term:`Votes <vote>` can be accessed from :ref:`Meeting view` or from the top level menu.
Motion votes are normally generated from :ref:`Meeting view`, but all motion votes can
be seen from the top level menu.

    :Motion:
        text of the motion. Motions should be specific enough that they capture all relevant details, without
        being too wordy

    :Date:
        date the motion was made

    :Member:
        the :term:`voting member` who made this vote

    :Vote:
        vote talley for each :term:`voting member`, one of *approved*, *rejected*, *abstained*, *novote*.

Meeting Motion Votes
---------------------
**Navigation:** [:ref:`Meeting view`] > [select agenda item] > **Edit**

See :ref:`Meeting Motions` for details.

All Motion Votes
--------------------
**Navigation:** Meetings > Motion Votes


.. image:: images/motion-votes-view.*
    :align: center

.. image:: images/motion-votes-edit.*
    :align: center


.. _Motions view:

Motions view
======================

:term:`Motions <motion>` can be accessed from :ref:`Meeting view` or from the top level menu.
:term:`Motions <motion>` are normally generated from :ref:`Meeting view`, but all motions can
be seen from the top level menu.

    :Motion:
        text of the motion. Motions should be specific enough that they capture all relevant details, without
        being too wordy

    :Mover:
        the person who makes the motion. This must be one of the :term:`voting members <voting member>`

    :Seconder:
        the person who seconds the motion. This must be one of the :term:`voting members <voting member>`

    :Status:
        the result of the motion vote, one of *open*, *tabled*, *approved*, *rejected*. The **Status** should
        not be left *open* after the :term:`meeting`

    :Vote:
        vote talley for each :term:`voting member`, one of *approved*, *rejected*, *abstained*, *novote*.

        .. note::
            :term:`voting members <voting member>` who are not present should be listed as *novote*

.. _Meeting Motions:

Meeting Motions
---------------------
**Navigation:** [:ref:`Meeting view`] > [select agenda item] > **Edit**

**Vote** can be edited by clicking on the :term:`vote` cell, changing it, then clicking off the cell. The
:term:`agenda item` must be in **Edit** mode for the :term:`vote` to be editable

.. note::
    votes are initialized as *approved* for :term:`voting members <voting member>` who are at the meeting at the
    time the :term:`motion` was created, and *novote* for those who were not

.. image:: images/meeting-motions-view.*
    :align: center

.. image:: images/meeting-motions-edit.*
    :align: center


All Motions
--------------------
**Navigation:** Meetings > Motions

.. note::
    motions can only be edited within the meeting context

Additional fields shown in the All Motions view

    :Meeting:
        :term:`meeting` at which this motion was created

    :Date:
        date for :term:`meeting` that this motion created

The view has the following filters:

    :Date:
        date range of interest

.. image:: images/motions-view.*
    :align: center

.. image:: images/motions-expanded.*
    :align: center


.. _Their Status Report view:

Their Status Report view
==============================
**Navigation:** Meetings > Meetings > [select meeting] > **Their Status Report**

This view is used to enter :term:`RSVP <rsvp>` or :term:`status reports <status report>` on behalf of a :term:`member`.
The view is exactly the same as :ref:`My Status Report view`, with the exception that the header above the table allows
the :term:`meeting admin` to choose which :term:`member's <member>` :term:`status report` to work on.

.. image:: images/their-status-report-view.*
    :align: center

See :ref:`My Status Report view` for more details on how to use this view.
