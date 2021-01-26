===========================================
Task Admin Reference
===========================================

This page gives a reference to all **membertility** views which are available to
:term:`members <member>` who have the :term:`leadership admin` :term:`security role`.

.. _History view:

History view
================
**Navigation:** Tasks > Task Fields

The History view can be used to see the history of :term:`tasks <task>` which have been marked completed.
Since :term:`tasks <task>` can be marked completed by :term:`leadership admins <leadership admin>` as well
as the :term:`member` to which the :term:`task` was assigned, the History view shows who marked this
:term:`task` as completed and at what time it was marked.

Currently the History view does not keep track of the :term:`task` :term:`fields <field>` which were set
at the time of the update, but that may change in the future.

The view has the following filters:

    :Update Time:
        chooses range of Update Times to show

    :Updated By:
        chooses which :term:`member(s) <member>` who made the update to show

    :Member:
        chooses which :term:`member(s)' <member>` :term:`tasks <task>` to show

    :Task:
        chooses which :term:`task(s) <task>` to show

    :Completed:
        chooses range of Date Completed to show

.. image:: images/history-view.*
    :align: center

.. image:: images/history-edit.*
    :align: center


.. _Member Summary view:

Member Summary view
===================
**Navigation:** Tasks > Member Summary

The Member Summary view gives an overview of each :term:`member`, showing the number of :term:`tasks <task>` in
each :term:`status`. Additionally this view shows the :term:`positions <position>` each member holds, and the
:term:`task groups <task group>` implied by those positions.

If an individual :term:`member` is selected, you can click on the **View Member** member, to get to a filtered
:ref:`Task Details view` of the :term:`member's <member>` :term:`tasks <task>`.

The view has the following filters:

    :Member:
        chooses which :term:`member(s) <member>` to show

    :Members in Positions:
        chooses which :term:`position(s) <position>` to show

    :Members in Task Groups:
        chooses which :term:`task group(s) <task group>` to show

.. image:: images/member-summary-view.*
    :align: center



.. _Tasks view:

Tasks view
===========
**Navigation:** Tasks > Tasks

The Tasks view is used to define the :term:`tasks <task>` which are done within the organization.

This view is where the :term:`tasks <task>` in the :ref:`Task Hierarchy` are defined.

See the :ref:`Task Configuration Guide` for details on how :term:`tasks <task>` should be configured.

    :Task:
        name of the task

    :Priority:
        the display priority of the :term:`task`, all other things being equal

    :Display:
        description of the task which needs to be done. This accepts plain text or
        Markdown (see https://daringfireball.net/projects/markdown/syntax for information on Markdown
        syntax)

    :Task Groups:
        select the :term:`task groups <task group>` the :term:`task` is in. This can also be defined
        in the :ref:`Task Groups view`

    :Expires Soon:
        this is the time period before which the :term:`task` becomes *overdue* for :term:`tasks <task>`
        which have **Optional Task** set to *no* (i.e., required tasks)

    :Fields:
        if the :term:`task` needs to collect information from the :term:`member` at the time it is marked
        complete, one or more :term:`fields <field>` may be chosen here. :term:`Fields <field>` are defined
        in the :ref:`Task Fields view`.

        The validation which is performed on the :ref:`Task Checklist view` Task form is defined by the text before
        the :term:`field` name in this selection.

            * required - :term:`field` must be filled in
            * oneof - if there are several *oneof* :term:`fields <field>`, at least one of these must be filled in
            * optional - optional :term:`fields <field>` do not need to be filled in

    :Period:
        this is the time period after a :term:`task` is marked complete when it will become *overdue* again. This
        is for :term:`tasks <task>` which must be done periodically, meaning the next Expiration Date depends on when
        the :term:`task` was last marked complete. For :term:`tasks <task>` which must be done repeatedly, either
        **Period** or **Date of Year** must be entered.

    :Date of Year:
        this is the date of year after which a :term:`task` becomes *overdue*. This is for :term:`tasks <task>` which
        must be done by a certain date of the year.  For :term:`tasks <task>` which must be done repeatedly, either
        **Period** or **Date of Year** must be entered.

    :Overdue Starts:
        this is the time period after **Date of Year** for which the :term:`task` remains *up to date* if marked
        completed. This is only used if **Date of Year** is specified.

    :Optional Task:
        indicates if the task is optional or required. If this is set to *yes*, **Expires Soon**, **Period**,
        **Date of Year**, and **Overdue Starts** should be left blank

.. image:: images/tasks-view.*
    :align: center

.. image:: images/tasks-create.*
    :align: center

.. image:: images/tasks-edit.*
    :align: center


.. _Task Details view:

Task Details view
=================
**Navigation:** Tasks > Task Details

The Task Details view gives the :term:`leadership admin` full visibility into all of the :term:`tasks <task>` in
the system. Each :term:`task` is on a separate line, and can be viewed in more detail by selecting it and clicking
**View**.

From the :term:`task` pop-up, the :term:`leadership admin` can see details about the :term:`task`, including
the contents of any :term:`fields <field>` which have been entered by the :term:`member` when the :term:`task`
was marked complete.

Further, the :term:`leadership admin` has the ability to update :term`fields <field>` and change the completion
date, if needed.

.. Note::
    Some date fields are used to override the Last Completed date from the :term:`member's <member>`
    :ref:`Task Checklist view`. However, from the Task Details view, these must be set independently.

The view has the following filters:

    :Member:
        chooses the :term:`member(s) <member>` to show

    :Members in Positions:
        chooses the :term:`member(s) <member>` in selected :term:`position(s) <position>`

    :Members in Task Groups:
        chooses the :term:`member(s) <member>` in selected :term:`task groups(s) <task group>`

    :Task:
        chooses the :term:`task(s) <task>` to show

    :Tasks in Task Groups:
        chooses the :term:`tasks(s) <task>` in selected :term:`task groups(s) <task group>`

    :Last Completed:
        chooses the date range for the completion date, can set start, finish or both

    :Expiration Date:
        chooses the date range for the expiration date, can set start, finish or both

    :In Position On:
        date of interest for which :term:`members <member>` hold :term:`positions <position>`

.. image:: images/task-details-view.*
    :align: center

.. image:: images/task-details-edit.*
    :align: center


.. _Task Fields view:

Task Fields view
=================
**Navigation:** Tasks > Task Fields

Some :term:`tasks <task>` may require additional :term:`fields <field>` to be displayed/collected on the
:ref:`Task Checklist view` Task form. These must be configured here.

    :Field:
        this will be the name of the field seen on the :ref:`Tasks view`, for selection onto the
        :term:`task's <task>` form

    :Priority:
        this defines the display order on the :ref:`Task Checklist view` Task form. Lower numbers are
        displayed earlier

    :Field Label:
        this text is placed on the :ref:`Task Checklist view` Task form on the left side

    :Input Type:
        several input types are defined. This controls the behavior of the :term:`field` on the
        :ref:`Task Checklist view` form

            * checkbox - :term:`field` will show a set of checkboxes, which will allow the :term:`member` to
              select one or more options. **Options** is displayed on this form
            * datetime - :term:`field` will show a date picker. **Override Completion** is displayed
              on this form
            * display - :term:`field` is display only. **Field Value** is displayed on this form
            * radio - :term:`field` will show a set of radio buttons, which will allow the :term:`member` to
              select one of the options. **Options** is displayed on this form
            * select2 - :term:`field` will show a select pulldown, which will allow the :term:`member` to
              select one of the options. **Options** is displayed on this form
            * text - :term:`field` will show a one line text box
            * textarea - :term:`field` will show an expandable text field
            * upload - :term:`field` will show widget for uploading a file

    :Options:
        only shown when **Input Type** is *checkbox*, *radio*, or *select2*. You can enter the required
        options by typing in the **Options** field and use carriage return to accept each option.

    :Field Hint:
        only shown if **Input Type** is not *display*. This is shown under the :term:`field` input
        on the :ref:`Task Checklist view` form to give the :term:`member` a hint on how the :term:`field`
        should be filled in

    :Field Value:
        only shown when **Input Type** is *display*. This is the text to be displayed on the
        :ref:`Task Checklist view` form to give the :term:`member` instructions, etc. This accepts
        plain text or Markdown (see https://daringfireball.net/projects/markdown/syntax for information on
        Markdown syntax)

    :Override Completion:
        only shown when **Input Type** is *datetime*. If this is set to *yes*, the contents of this
        :term:`field` will override the completion date normally generated automatically by the system
        when the :term:`member` clicks **Mark Complete** on the :ref:`Task Checklist view` form

    :Field Name:
        generated by the system, and only used internally

    :Upload URL:
        generated by the system, and only used internally

.. image:: images/task-fields-view.*
    :align: center

.. image:: images/task-fields-create.*
    :align: center

Some examples of how the form changes with different **Input Type** selections

.. image:: images/task-fields-create-checkbox.*
    :align: center

.. image:: images/task-fields-create-datetime.*
    :align: center


.. _Task Groups view:

Task Groups view
=================
**Navigation:** Tasks > Task Groups

The Task Groups view is used to define how :term:`tasks <task>` are grouped within the organization.

This view is where :term:`tasks <task>` are associated with the :term:`task group` to
follow the :ref:`Task Hierarchy`.

    :Task Group:
        name of the task group

    :Description:
        describes the task group, possibly giving more information than just the name

    :Task Groups:
        list of :term:`task groups <task group>` that are associated below this :term:`task group` to follow
        the :ref:`Task Hierarchy`

    :Tasks:
        list of :term:`tasks <task>` that are associated below this :term:`task group` to follow
        the :ref:`Task Hierarchy`

    :Members:
        list of :term:`members <member>` associated directly with this :term:`task group`. This can be configured
        here or in the :ref:`Positions view`

        .. Note::
            While it is possible to associate the :term:`member` directly with a :term:`task group`, it is recommended
            that this be done only indirectly by :term:`position`

.. image:: images/task-groups-view.*
    :align: center

.. image:: images/task-groups-edit.*
    :align: center



