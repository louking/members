===========================================
Meetings Admin Guide
===========================================

This guide describes the concepts of the membertility Meetings Module.

The general work flow for :term:`meetings <meeting>` is

* admin creates meeting, indicating who would be invited, date, and purpose of the meeting
* admin causes invitation for the meeting to be sent
* in the invitation, the leadership member is given a link to click

    * member is shown any outstanding action items they're responsible for
    * member clicks link and can indicate if attending the meeting
    * member can also give status report
    * member can add any discussion items for meeting
    * member can update action item status

* as members add discussion items, the meeting agenda is being built
* when ready admin can generate a status report

    * this can create a word doc or go to a g suite drive location
    * if a g suite file is created, it is updated nightly as members continue to add or update status reports, or the
      admin can cause it to be updated on demand
    * the g suite status report is generated to a well known location initially, but due to the way g suite works, can
      safely be moved to the desired folder

* additional emails can be sent to the meeting group if needed, e.g., with links to documents which should be read to
  prepare for the meeting
* during the meeting, the admin can do the following, which forms the minutes for the meeting

    * update attendee list (who actually came)
    * add discussion about each agenda item
    * add action items under agenda item
    * add motions under agenda item
    * tally vote for any motions
    * create new agenda items (for unplanned discussion)

* after the meeting, the admin can make any adjustments to the notes which were taken, and when satisfied, generate the
  minutes (again word doc or g suite drive location)

    * when minutes from the last meeting are voted on, changes are rarely required. But if changes are required, the
      admin can go into the last meeting's view, make the changes, and generate the minutes again
    * g suite minutes are generated to a well known location but can safely be moved to the desired folder

* action items, motions / votes, minutes are available to the members through the system immediately after the meeting
* members receive reminder emails about outstanding action items

Meeting Data Model
======================

..
   see https://www.graphviz.org/
   see http://graphs.grevian.org/

.. graphviz::

   digraph records {
        graph [fontname = "helvetica"];
        node [fontname = "helvetica"];
        edge [fontname = "helvetica"];
        "member 1" -> "position report 1";
        "member 2" -> "position report 1";
        "member 3" -> "position report 2";
        "member 4" -> "position report 3";
        "member 4" -> "ad hoc report 4";
        "meeting admin 1" -> "agenda item 4";
        "position report 1" -> "discussion/agenda item 1";
        "position report 1" -> "discussion/agenda item 2";
        "position report 2" -> "discussion/agenda item 3";
        "discussion/agenda item 1" -> "action item 1";
        "discussion/agenda item 2" -> "motion 1";
        "motion 1" -> "motion vote tally 1";
        { rank=same; "member 1", "member 2", "member 3", "member 4", "meeting admin 1" };
        { rank=same; "position report 1", "position report 2", "position report 3", "ad hoc report 4" };
        { rank=same; "discussion/agenda item 1", "discussion/agenda item 2", "discussion/agenda item 3", "agenda item 4" };
        { rank=same; "action item 1", "motion 1" };
    }

