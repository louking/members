===========================================
Meetings Member Guide
===========================================

This document gives guidance on the :term:`meeting` work flow for :term:`members <member>`.

Meeting Invitation and Status Report Request
================================================
When you are invited to a :term:`meeting`, you will receive an email with the invitation, worded something like
this.

    You have been invited to the <meeting> on <date and time>.

    Location / URL

    <location>

    Please RSVP and update your status report by clicking `here <http://www.example.com>`__.

    Your outstanding action items are listed below. You can update the action item status by
    clicking `here <http://www.example.com>`__.

    +------------------+-----------+
    | Action Item      | Status    |
    +==================+===========+
    | action 1         | open      |
    +------------------+-----------+
    | new action item  | open      |
    +------------------+-----------+
    | test action item | inprogress|
    +------------------+-----------+

You can see that there are two links in the email, each under the word "here" in different paragraphs.

The first link brings you to the :ref:`My Status Report view` for this meeting. The :ref:`My Status Report view` allows
you to :term:`rsvp` to the meeting, and to enter your :term:`status report(s) <status report>`.

The second link brings you to your :ref:`My Action Items view`. The :ref:`My Action Items view` allows you to update
status and provide comments for any :term:`action items <action item>` you've been assigned.

.. warning::
    The links in this email are constructed specifically for you, for this meeting. Please do not forward this
    email to anyone else as it would give them access to your account without needing your password.


.. _My Meetings view:

My Meetings view
======================
**Navigation:** Meetings > My Meetings

The My Meetings view can be used to see a summary of :term:`meetings <meeting>` you were :term:`invited <invite>` to,
or to navigate to the :ref:`My Status Report view` for a particular meeting.

This view shows your :term:`RSVP <rsvp>` response, whether you attended, and gives links to any reports which have been
generated about the meeting.

To navigate to the :ref:`My Status Report view`, where you can :term:`RSVP <rsvp>` and enter your
:term:`status reports <status report>`,

* select the meeting
* click **My Status Report**

.. image:: images/my-meetings-view.*
    :align: center


.. _My Status Report view:

My Status Report view
======================
**Navigation:** Meetings > My Meetings > [select meeting] > **My Status Report** (or via the link in the emailed
:term:`invitation <invite>`)

You will see a table similar to the following, with a button for your :term:`RSVP <rsvp>` and a row for each of your
:term:`position` based :term:`status reports <status report>`.

.. image:: images/my-status-report-view.*
    :align: center

.. important::
    * to *view* the contents of a row, use |icon-expand| to expand, |icon-collapse| to collapse
    * to *edit* a row, first select the row by clicking on the text to the right of |icon-expand| or |icon-collapse|
      under **Report Title**, then click the **Edit** button at the top of the table

.. |icon-expand| image:: images/icon-expand.*
.. |icon-collapse| image:: images/icon-collapse.*

RSVP for the meeting
------------------------
First you need to record whether you plan to come to the :term:`meeting` or not

* click the **RSVP** button

This opens a form for your :term:`RSVP <rsvp>`:

.. image:: images/my-status-report-edit-rsvp.*
    :align: center

* next to **RSVP** select your response, one of *attending*, *not attending*
* click **Save**

Update your status report(s)
--------------------------------
Now you can enter your :term:`status report(s) <status report>`.

* select the row for the :term:`status report` you want to enter
* click **Edit** at the top of the table

This opens an Edit form for this :term:`status report`:

.. image:: images/my-status-report-edit-status.*
    :align: center

* enter your status for this :term:`position`
* click **Save**

.. note::
    :term:`Status reports <status report>` are by :term:`position`. So if there is more than one :term:`member` in the
    same :term:`position`, they will see the same :term:`status report` for that :term:`position`. If one :term:`member`
    edits the report the other :term:`member(s) <member>` will be able to see the edits when they open the
    :term:`position` row. So if the position is shared, there needs to be coordination for producing the
    :term:`status report`.

.. _add discussion item:

Optionally add discussion items for the meeting
----------------------------------------------------
If a topic needs to be discussed at the meeting, a :term:`discussion item` must be created. This adds the topic
to the :term:`meeting` :term:`agenda`.

* select the row for the :term:`status report` you want to enter a :term:`discussion item` about
* click **Edit** at the top of the table

This opens an Edit form for this :term:`status report`:

.. image:: images/my-status-report-edit-status.*
    :align: center

* under **Discussion Items**, click **New**

This opens a Create form for the :term:`discussion item`:

.. image:: images/my-status-report-discussion-create.*
    :align: center

* fill in a concise, descriptive title under **Discussion Title**
* use **Discussion Details** to give more details of what the discussion is about, what decisions might be taken,
  options, etc.
* click **Create**

You can edit the discussion item up until the meeting.

* select the row for the :term:`status report` which holds the :term:`discussion item`
* click **Edit** at the top of the table
* under **Discussion Items**, select the :term:`discussion item` to be edited
* under **Discussion Items**, click **Edit**
* make the desired edits to **Discussion Details**
* click **Save**

.. note::
    The :term:`meeting` :term:`agenda item` is created when you click **Create** for the :term:`discussion item`. While
    you can edit the **Discussion Details** up until the start of the :term:`meeting`, there's no way for you to
    update the title used in the :term:`meeting` for the :term:`agenda item`. However, your updates to the
    **Discussion Title** will be saved in the :term:`Status Report <status report>` document.

Optionally create ad hoc status for areas not covered by one of your positions
--------------------------------------------------------------------------------
Occasionally, there might be a need to create a :term:`status report` or :term:`discussion item` which
doesn't neatly fit under one of your positions.

* above the Status Report table, click **New**

This opens a Create form for the :term:`status report`:

.. image:: images/my-status-report-create.*
    :align: center

* give the report a clear, concise **Report Title**
* put details into the **Status Report** field
* click **Create**

If an item about this report needs to be added to the :term:`meeting` :term:`agenda`, create a
:term:`discussion item`.

* select the new :term:`status report` you just created
* above the Status Report table, click **Edit**
* add the :term:`discussion item` as described in :ref:`add discussion item`


.. _My Action Items view:

My Action Items view
======================
**Navigation:** Meetings > My Action Items (or via the link in the emailed :term:`invitation <invite>`)

To see what :term:`action items <action item>` you have outstanding, or update the status or progress for any of these,
you can use the My Action Items view. (Hopefully your action items are written more clearly than what you see here,
but of course these are what was being used for system testing.)

.. image:: images/my-action-items-view.*
    :align: center

As you can see, the table shows when the :term:`action item` was first created, what the action is, the current
status (*open*, *inprogress*, *closed*), when it was last updated and who made the last update.

You can see more details and make updates by opening the Edit form.

* select an :term:`action item`
* click **Edit**

This opens the Edit form for the :term:`action item`:

.. image:: images/my-action-items-edit.*
    :align: center

Here you can see the :term:`agenda item` under which the :term:`action item` was created, which might give you
additional context of what is needed. You can also change the **Status** and make updates to the **Progress / Resolution**
field.

* update the **Status** to *inprogress* or *closed* if appropriate
* add information about your progress, or how this was resolved to the top of **Progress / Resolution**
* click **Update**

.. note::
    If **Progress / Resolution** has been updated multiple times, it makes sense to add the date of
    each update, with the latest update being at the top.


..
    .. _My Discussion Items view:

    My Discussion Items view
    =============================
    **Navigation:** Meetings > My Discussion Items
