===========================================
Meetings Admin Reference
===========================================

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

    :Attended:
        indication of whether the :term:`member` attended the meeting, *yes* or *no*

    :RSVP:
        the :term:`member's <member>` :term:`rsvp` response when invited to the :term:`meeting`

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

In addition to the **New**, **Edit**, **Delete** buttons, there are three action buttons.

    :Send Invites:
        use this to send the initial :term:`invitation <invite>` to the meeting, or if any positions have been updated
        which affect the meeting attendance

        :Subject:
            default subject is provided by the system, but can be changed if desired

        :Message:
            add additional message to the invitiation if desired

        :From:
            defaults to the email address of the :term:`meeting` **Organizer**, but can be updated if desired

        :option checkboxes:
            * check **Request Status Report** if the text in the email should mention that a status report is needed
            * check **Show Action Items** if outstanding action items should be shown in the email

        .. note::
            if any positions which affect meeting attendance have been updated, a nightly job will take care of
            sending additional :term:`invitations <invite>`

    :Generate Docs:
        use this to generate documents associated with the meeting

        .. note::
            the status report document is automatically created and updated as people write or update
            their status reports

        .. note::
            for upcoming meetings, a nightly process regenerates documents which were previously generated, in case changes
            are made which would affect those documents. This does not apply to minutes since these are normally
            generated after the meeting


    :Send Email:
        use this to send email to the :term:`members <member>` on the :term:`meeting` :term:`invite` list. Note the
        default email subject contains the meeting purpose and date, and can be edited


.. image:: images/meeting-view.*
    :align: center

.. image:: images/meeting-edit.*
    :align: center

.. image:: images/meeting-send-invites.*
    :align: center

.. image:: images/meeting-generate-docs.*
    :align: center

.. image:: images/meeting-send-email.*
    :align: center


.. _Meetings view:

Meetings view
=================
**Navigation:** Meetings > Meetings

This is the main view for managing :term:`meetings <meeting>`. The meeting can be created or edited. Once created
this view is used to navigate to the individual meeting for administration purposes.

    :Purpose:
        short name of the meeting, e.g., Board Meeting

    :Date:
        date the meeting will take place

    :Time:
        time of the meeting

    :Location:
        location of the meeting, either a physical address, a URL (e.g., for Google Meet), or "by email"

    :Show Actions Since:
        action items are shown in agenda, minutes, etc. Any action items which have been updated after this
        date will be shown associated with this meeting

    :Organizer:
        the meeting organizer. When emails are sent from this view, the **From** address will default to this
        :term:`member's <member>` email address. This defaults to the currently logged in member

    :Agenda:
        if agenda has been generated to Google Workplace, this is the link to the file

    :Status Report:
        if status report has been generated to Google Workplace, this is the link to the file

    :Minutes:
        if minutes has been generated to Google Workplace, this is the link to the file

    :Invite Tags:
        members who are associated with these tags through their position will be invited to the meeting

    :Vote Tags:
        members who are associated with these tags through their position will be invited to the meeting

In addition to the **New**, **Edit**, **Delete** buttons, there are two navigation buttons.

    :View Meeting:
        this is the edit view for the meeting which is used during the meeting, brings up :ref:`Meeting view`

    :Meeting Status:
        this gives status of the meeting for use prior to the meeting, showing missing and entered status reports. This
        brings up :ref:`Meeting Status view`

    :Their Status Report:
        this allows the :term:`meeting admin` to :term:`RSVP <rsvp>` and enter :term:`status reports <status report>`
        on behalf of another :term:`member`. This brings up :ref:`Their Status Report view`

.. image:: images/meetings-view.*
    :align: center

.. image:: images/meetings-edit.*
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


.. _Tags view:

Tags view
======================
**Navigation:** Meetings > Tags

Tags are used for grouping together :term:`positions <position>` and :term:`members <member>` for various purposes,
e.g., for invitations to be sent for a :term:`meeting`, or to indicate who may :term:`vote` at a :term:`meeting`.

    :Tag:
        name of tag

    :Description:
        description of how the tag is used

    :Positions:
        this tag resolves to these :term:`positions <position>`

    :Members:
        this tag resolves to these :term:`members <member>`

        .. note::
            it is recommended to only use the **Positions** field because as :term:`positions <position>` change
            use of **Members** may become out of date

.. image:: images/tags-view.*
    :align: center

.. image:: images/tags-edit.*
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
