===========================================
Awards Admin Reference
===========================================

This page gives a reference to all **membertility** views which are available to
:term:`members <member>` who have the :term:`awards admin` :term:`security role`.

.. _Award Races view:

Award Races view
===================
**Navigation:** Awards > Races

To create a new race, click the **New** button, enter the race ID from
RunSignup, then click **Create**. The race ID can be determined from the race's
results page URL, e.g., for
https://runsignup.com/Race/Results/61987#resultSetId-566447;perpage:100, the
race ID is 61987.

To see the current awards for this race via the :ref:`race awards view`, select
the race, then click **Awards**.

.. image:: images/award-races-view.*
    :align: center

|

**New**

.. image:: images/award-races-create.*
    :align: center

|

To update race divisions after initial creation, click the **Update** button and
then click **Update**. 

.. warning::
    Do not change the RSU Race ID

.. image:: images/award-races-update.*
    :align: center


.. _Award Divisions view:

Award Divisions view
=====================
**Navigation:** Awards > Races > [select Race] > Divisions

RunSignup cannot automatically compute placements for a division that isn't
split by gender the normal way -- most commonly a non-binary award division,
since RunSignup has no gender option for a non-binary registrant when it
auto-places entrants into divisions. This view lists every division for the
selected race, across all of its events (including past seasons, if the same
RunSignup race ID has been reused year over year), and lets you supply what
RunSignup can't determine on its own.

**Event**, **Division**, **Short Name**, **Priority**, and **# Awards** are
synced from RunSignup and cannot be edited here.

**Placement** shows one of three values:

    :Auto-Placed:
        RunSignup computes this division's placements on its own; nothing to
        do here.

    :Needs Setup:
        RunSignup has no way to auto-place this division and nobody has
        configured it yet. It will never show any award winners in the
        :ref:`race awards view` until **Gender** is set to ``X`` below (and,
        if the division applies to a specific age range, **Min Age**/**Max
        Age** are filled in too).

    :Configured:
        RunSignup still can't auto-place this division, but **Gender** has
        been set to ``X``, so award placements for it are computed
        automatically the same way as any other division.

Once a division is Configured, RunSignup's own **Priority** ranking still
governs it exactly as it does for a normal division -- e.g., if a registrant
qualifies for both an Overall division and an age-banded one, whichever has
the higher priority determines which award they actually win. There's
nothing to configure for this; it just works the same way it already does
for the Male/Female divisions on the same race.

**Gender**, **Min Age**, and **Max Age** are only editable for a division
that needs setup or has been configured -- editing them on a division
RunSignup already auto-places has no effect, since the next **Update** on the
:ref:`award races view` overwrites them from RunSignup.

Use the **Year** filter to limit the view to one season at a time -- by
default only the most recent year found is shown. Use the **Placement**
filter to show only divisions that still need setup.

.. note::
    After clicking **Update** on the :ref:`award races view`, if the
    RunSignup sync found a new division whose name looks non-binary, an alert
    names it so you know to come here and set its age range.

.. image:: images/award-divisions-view.*
    :align: center

|

**Edit**

To set **Gender**, **Min Age**, or **Max Age** for a division, select its row
and click **Edit**.

.. image:: images/award-divisions-edit.*
    :align: center

|


.. _Race Awards view:

Race Awards view
===================
**Navigation:** Awards > Races > [select Race] > Awards

This view is used to view the current award winners, to indicate that the award
has been picked up, and to enter optional notes about the award.

The **Event** filter should be used to select the event which you're interested
in. If the current race has multiple events, you can switch between these
easily using the pull-down, or you can have multiple tabs open in your browser.

There is no need to refresh the page to see changes, as the view is updated
automatically when the awards are updated in RunSignup.

When an award winner picks up their award, click anywhere in the cell to the
left of the |icon-add-comment| icon. The |icon-radio-button-unchecked| will
change to |icon-check-circle| and the cell will turn grey. This indicates that
the award has been picked up.

To find the cell for a specific award winner, use the **Bib** filter to search
for their bib number. To clear the bib filter, click on the |icon-search-off|
icon which appears to the right of the bib filter.

If an award was marked as picked up, but subsequently the results were changed
such that that award had been given to the wrong person, the new award winner
will be displayed and the background for that cell will turn yellow.

If you want to add a note to an award (e.g., "John Doe picked up the award for
Jane"), click on |icon-add-comment|, add the note and then click **Save**.
|icon-insert-comment| will be displayed for awards which have notes. Once a note
has been added, hovering over |icon-insert-comment| will display the note, and
clicking on |icon-insert-comment| will display the note and allow the user to
edit it.

To download the current state of the award distribution, click on the **CSV**
button. The CSV file is described in :ref:`Race Awards CSV file`.

.. note::
    If the divisions are changed in RunSignup after this view is displayed, from
    the :ref:`award races view` click the **Update** button to update the
    divisions in the database, then refresh this view.

.. image:: images/race-awards-view.*
    :align: center

|

.. note::
    On a phone, these will be stacked vertically

.. |icon-add-comment| image:: images/icon-add-comment.*
.. |icon-check-circle| image:: images/icon-check-circle.*
.. |icon-radio-button-unchecked| image:: images/icon-radio-button-unchecked.*
.. |icon-insert-comment| image:: images/icon-insert-comment.*
.. |icon-search-off| image:: images/icon-search-off.*

.. _Race Awards CSV file:

Race Awards CSV file
---------------------
The race awards CSV file contains the following columns:

    :name:
        the name of the awardee

    :bib:
        the bib number of the awardee

    :division:
        the division of the awardee

    :place:
        the place of the awardee within the division

    :status:
        the status of the award, which can be one of:

        - **picked up**: the award has been picked up by the awardee
        - **pending pickup**: the award has not yet been picked up
        - **distribution error**: the award was picked up, but the awardee is not the correct awardee for that award
        - **withdrawn**: the award has been withdrawn from the awardee due to division reconfiguration

    :notes:
        any notes recorded about the award

    :updated:
        the date and time that the award record was last updated, formatted as YYYY-MM-DD HH:mm:ss
