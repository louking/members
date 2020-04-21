===========================================
Leadership Task Admin Guide
===========================================

:term:`Members <member>` of a club’s leadership team are required to complete various :term:`tasks <task>` in
support of the on-boarding process. E.g., the member needs to gain access to the club's documents, read certain
policies, complete training courses, etc. Some of these :term:`tasks <task>` need to be renewed periodically. The
"leadership task module" of the **membertility** system is designed to define these :term:`tasks <task>` and
track the :term:`members' <member>` completion records.

..
   see https://www.graphviz.org/
   see http://graphs.grevian.org/

.. graphviz::

   digraph records {
        "member 1" -> "position 1";
        "member 2" -> "position 1";
        "member 2" -> "position 2";
        "member 3";
        "position 1" -> "task group 1";
        "position 1" -> "task group 2";
        "position 1" -> "task group 3";
        "task group 3" -> "task group 2";
        "task group 2" -> "task 1";
        "task group 2" -> "task 2";
    }

Tasks
===================
The system keeps track of each :term:`member's <member>` indication that they have completed each of a list of
:term:`tasks <task>`, and when this was completed.

* :term:`tasks <task>` are displayed to :term:`member` via the task checklist view
* :term:`task` attributes

  * period (specified in weeks) - how long after :term:`task` is marked completed does it become *overdue*
  * date of year - :term:`task` becomes *overdue* on a date of year (e.g., March 3) if not marked comleted
  * optional - :term:`task` is suggested but not required

* :term:`tasks <task>` are generally displayed by urgency, e.g., if the :term:`task` expires sooner it will be
  displayed closer to the top, but there is also a priority, which controls the order of display all things being equal
* :term:`member` can select a :term:`task`, open an "view task" window, and click a button to mark the :term:`task`
  as completed
* :term:`leadership admin` sets the attributes for :term:`task` (e.g., conflict of interest may be required every
  other year, safe sport every year), after which the :term:`task` is shown once again as *overdue* to the
  :term:`member`

Task Groups
=================
To facilitate assignment of sets of :term:`tasks <task>` to individual :term:`members <member>`, :term:`tasks <task>` are assigned into one or more
task groups, and :term:`members <member>` are assigned one or more :term:`task groups <task group>`.

* :term:`leadership admin` creates :term:`task groups <task group>` to facilitate assignment of groups of :term:`tasks <task>` to leadership-member
  users
* leadership :term:`tasks <task>` may be assigned to one or more leadership task groups
* :term:`members <member>` are assigned one or more :term:`task groups <task group>` which are displayed on their task
  checklist view

Admin Tracking
===========================
The :term:`leadership admin` needs to be able to see summaries of what :term:`tasks <task>` are outstanding in total and for
individual :term:`members <member>`.

* task summary view - shows an overview of :term:`task` completion by all :term:`members <member>`, with
  appropriate filters for individual :term:`members <member>`, :term:`status`, etc.

Task Reminder Emails
======================
For those :term:`members <member>` who have not completed all their :term:`tasks <task>`, emails will be sent periodically to remind them
what :term:`tasks <task>` are outstanding.

* individual emails are sent to :term:`members <member>` who have overdue or upcoming :term:`tasks <task>`
* :term:`leadership admin` receives summary email, separate from the individual emails mentioned above
* the emails are sent every two weeks
