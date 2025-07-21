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
change to |icon-check-circle| and the cell with turn grey. This indicates that
the award has been picked up.

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
button. 

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

