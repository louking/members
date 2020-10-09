===========================================
Leadership Task Admin Guide
===========================================

:term:`Members <member>` of a club’s leadership team are required to complete various :term:`tasks <task>` in
support of the on-boarding process. E.g., the member needs to gain access to the club's documents, read certain
policies, complete training courses, etc. Some of these :term:`tasks <task>` need to be renewed periodically. The
"leadership task module" of the **membertility** system is designed to define these :term:`tasks <task>` and
track the :term:`members' <member>` completion records.

This guide describes the concepts of the membertility Leadership Task Module, as well as gives guidance for
how to configure the items in the :ref:`Task Hierarchy`.

.. _Task Hierarchy:

Task Hierarchy
===================
To facilitate :term:`task` assignment to :term:`members <member>`, a task hierarchy is defined. The
:term:`leadership admin` creates :term:`positions <position>` and :term:`task groups <task group>` to facilitate
management of sets of :term:`tasks <task>`.

* each :term:`task` may be assigned to one or more :term:`task groups <task group>`
* each :term:`task group` may be assigned to one or more :term:`positions <position>`
* each :term:`position` maybe be assigned to one or more :term:`members <member>`
* :term:`tasks <task>` which follow the :term:`member` -> :term:`position` -> :term:`task group` -> :term:`task`
  tree are displayed on that :term:`member's <member>` :ref:`Task Checklist view`

..
   see https://www.graphviz.org/
   see http://graphs.grevian.org/

.. graphviz::

   digraph records {
        graph [fontname = "helvetica"];
        node [fontname = "helvetica"];
        edge [fontname = "helvetica"];
        "member 1" -> "position 1";
        "member 2" -> "position 1";
        "member 2" -> "position 2";
        "member 3" -> "position 2";
        "position 1" -> "task group 1";
        "position 1" -> "task group 3";
        "position 2" -> "task group 2";
        "position 2" -> "task group 4";
        "task group 3" -> "task group 2";
        "task group 1" -> "task 1";
        "task group 2" -> "task 1";
        "task group 2" -> "task 2";
        "task group 3" -> "task 1";
        "task group 4" -> "task 2";
        "task group 4" -> "task 3";
        { rank=same; "member 1", "member 2", "member 3" };
        { rank=same; "position 1", "position 2" };
        { rank=same; "task group 1", "task group 3", "task group 4" };
        { rank=same; "task 1", "task 2", "task 3" };
    }


Tasks
===================
The system keeps track of a list of :term:`tasks <task>` for each :term:`member`, and that
:term:`member's <member>` indication that they have completed each of a list of the
:term:`tasks <task>`, and when it was completed.

* :term:`tasks <task>` are displayed to :term:`member` via the :ref:`Task Checklist view`

* using the :ref:`Task Checklist view`, the :term:`member` can select a :term:`task`, open an "view task" window, and
  click a button to mark the :term:`task` as completed

* :term:`leadership admin` sets the attributes for :term:`task` (e.g., conflict of interest may be required every
  other year, safe sport every year), to control the :term:`task` :term:`status` and expiration behavior, as
  defined in :ref:`Task Configuration Guide`

* :term:`tasks <task>` are generally displayed by urgency, e.g., if the :term:`task` expires sooner it will be
  displayed closer to the top, but there is also a priority, which controls the order of display all things being equal

.. _Task Configuration Guide:

Task Configuration Guide
--------------------------

The :ref:`Tasks view` is used to configure :term:`task` behavior.

:term:`Task <task>` :term:`status` and expiration is controlled using the attributes

* **Period** - how long after the :term:`task's <task>` completion date when it become *overdue*
* **Date of Year** - :term:`task` becomes *overdue* on a date of year (e.g., March 3) if not marked completed
* **Overdue Starts** - task remains *up to date* after **Date of Year** for this duration. Only applicable when **Date of Year** is set
* **Expires Soon** - how long before :term:`task` expires that the status shows up as *expires soon*
* **Optional Task** - if set to *yes*, :term:`task` is suggested but not required, and does not expire

.. Padding. See https://github.com/sphinx-doc/sphinx/issues/2258#issuecomment-532109217

To configure a :term:`task` to be required periodically, but not on any specified date, set

* **Period** to the duration after completion that the :term:`task` before the task expires
* **Expires Soon** to the duration in advance of Expiration Date that the :term:`task` should start showing *expires soon*
* **Optional Task** to *no*
* leave **Date of Year** and **Overdue Starts** unset

To configure a :term:`task` to be required periodically by a specified date, set

* **Date of Year** to the date the :term:`task` must be completed by
* **Overdue Starts** to the duration after **Date of Year** during which the :term:`task` remains *up to date*
* **Expires Soon** to the duration in advance of Expiration Date that the :term:`task` should start showing *expires soon*
* **Optional Task** to *no*
* leave **Period** unset

To configure a :term:`task` to be required but done only once, set

* **Optional Task** to *no*
* leave **Period**, **Date of Year**, **Expires Soon**, and **Overdue Starts** unset

To configure a :term:`task` to be optional, set

* **Optional Task** to *yes*
* leave **Period**, **Date of Year**, **Expires Soon**, and **Overdue Starts** unset



Task Groups
=================
To facilitate assignment of sets of :term:`tasks <task>` to individual :term:`members <member>`, :term:`tasks <task>` are assigned into one or more
:term:`task groups <task group>`.

.. note::

    Preference is to assign :term:`member` to :term:`position`, and let the :term:`task groups <task group>` follow
    from the :term:`position`. However the system does allow direct association between :term:`member` and
    :term:`task group`.

Admin Tracking
===========================
The :term:`leadership admin` needs to be able to see summaries of what :term:`tasks <task>` are outstanding in total and for
individual :term:`members <member>`.

* :ref:`Member Summary view` - shows a summary of :term:`task` completion by :term:`member`
* :ref:`Task Details view` - shows the details of :term:`task` completion by all :term:`members <member>`, with
  appropriate filters for individual :term:`members <member>`, :term:`status`, etc.

Member Summary
---------------
The :ref:`Member Summary view` shows a summary of the :term:`task` :term:`status` for each :term:`member`. From this
view, the :term:`leadership admin` can select a :term:`member`, then view that :term:`member's <member>` details
using the :ref:`Task Details view`.

Task Details
----------------
Each :term:`member` is shown :term:`tasks <task>` they are responsible for on their :ref:`Task Checklist view`. The
:term:`tasks <task>` which each :term:`member` is responsible for can be viewed by the :term:`leadership admin`
on the :ref:`Task Details view`.



Task Status / Expiration Date
------------------------------
When using :ref:`Member Summary view` or :ref:`Task Details view`, the task :term:`status` is displayed. These
may be one of the following.

    :overdue: :term:`task` should have been done by now, and needs to be completed
    :expires soon: :term:`task` will be becoming overdue shortly
    :optional: :term:`task` can be completed, but isn't required
    :up to date: required :term:`task` has been completed, and does not need to be done until :term:`expiration date`
    :done: optional :term:`task` has been completed

Task Reminder Emails
----------------------
For those :term:`members <member>` who have not completed all their :term:`tasks <task>`, emails will be sent
periodically to remind them what :term:`tasks <task>` are outstanding.

* individual emails are sent to :term:`members <member>` who have overdue or upcoming :term:`tasks <task>`
* :term:`leadership admin` receives a summary email, separate from the individual emails mentioned above
* the emails are sent every two weeks
