*******************************************
Racing Team Admin Reference
*******************************************

This page gives a reference to all **membertility** views which are available to
:term:`members <member>` who have the :term:`racingteam admin` :term:`security role`.


.. _Racing Team Applications view:

Racing Team Applications view
===============================
**Navigation:** Racing Team > Applications

    :Timestamp:
        date and time the application was submitted

    :Name:
        applicant's name

    :Gen:
        applicant's gender

    :DOB:
        applicant's date of birth

    :Email:
        applicant's email address

    :Type:
        type of application, one of *new*, *renewal*

    :Comments:
        any comments the applicant entered. If there are ellipses at the end, hovering over this field will display 
        the full comment
    
    :Race 1/2:
        name of submitted race 1/2

        .. note::
            detailed application results can be found in :ref:`Racing Team Application Results view`

    :R1/2 Date:
        date of submitted race 1/2

    :R1/2 AG:
        age grade for submitted race 1/2

.. image:: images/racing-team-applications-view.*
    :align: center


.. _Racing Team Application Results view:

Racing Team Application Results view
=======================================
**Navigation:** Racing Team > Application Results

    :Timestamp:
        date and time the application was submitted

    :Name:
        applicant's name

    :Email:
        applicant's email address

    :Event Date:
        date for this result submission
    
    :Age:
        applicant's age on **Event Date**
    
    :Event Name:
        name of the race

    :Distance:
        race distance

    :Units:
        units of race distance, one of *miles*, *km*

    :Age Grade:
        age grade for this result
    
    :Results Link:
        link to official results (optional)

.. image:: images/racing-team-application-results-view.*
    :align: center


.. _Racing Team Config view:

Racing Team Config view
===============================
**Navigation:** Racing Team > Config

    :Open Behavior:
        one of *auto*, *open*, or *closed*. This defines whether racing team applications are open.
        In practice, this should be set to *auto* to use the date ranges to automatically allow applications only
        during the specified ranges. To allow applications outside of the date ranges, set this to *open*. 
        To turn off applications within the date ranges set to *closed*.

    :Date Ranges:
        list of date ranges as configured on the :ref:`Racing Team Date Range view`. Applications are allowed automatically 
        during the dates in these ranges if **Open Behavior** is set to *auto*.

    :From Email:
        email address which racing team emails are sent from

    :Info Form CC Email:
        list of email addresses which are copied when a :term:`racingteam member` submits the Racing Team Information Form

    :Application Form CC Email:
        list of email addresses which are copied when someone submits the Racing Team Application Form

.. note::
    do not create more than one row per interest. If more than one row is created the results will be unpredictable.

.. image:: images/racing-team-config-view.*
    :align: center

.. image:: images/racing-team-config-edit.*
    :align: center


.. _Racing Team Date Range view:

Racing Team Date Range view
===============================
**Navigation:** Racing Team > Date Range

    :Range Name:
        name of date range, e.g., 'summer', 'winter'

    :Start Month:
        month of year this date range starts

    :Start Date of Month:
        date of **Start Month** this date range starts

    :End Month:
        month of year this date range ends

    :End Date of Month:
        date of **End Month** this date range ends

.. image:: images/racing-team-date-range-view.*
    :align: center

.. image:: images/racing-team-date-range-edit.*
    :align: center


.. _Racing Team Info Results view:

Racing Team Info Results view
=======================================
**Navigation:** Racing Team > Info Results

    :Timestamp:
        date and time the result was submitted

    :Name:
        :term:`member's<member>` name

    :Event Date:
        date for this result submission
    
    :Age:
        :term:`member's<member>` age on **Event Date**
    
    :Event Name:
        name of the race

    :Distance:
        race distance

    :Units:
        units of race distance, one of *miles*, *km*

    :Age Grade:
        age grade for this result
    
    :Awards:
        awards achieved (optional)

.. image:: images/racing-team-info-results-view.*
    :align: center


.. _Racing Team Info Volunteer view:

Racing Team Info Volunteer view
=======================================
**Navigation:** Racing Team > Info Volunteer

    :Timestamp:
        date and time the volunteer activity was submitted

    :Name:
        :term:`member's<member>` name

    :Event Date:
        date for this volunteer activity submission
    
    :Hours:
        number of hours being reported
    
    :Comment:
        any additional comments (optional)

.. image:: images/racing-team-info-volunteer-view.*
    :align: center


.. _Racing Team Members view:

Racing Team Members view
===============================
**Navigation:** Racing Team > Members

    :Member:
        :term:`member` which is on the racing team

    :Gender:
        :term:`members <member>` gender

    :DOB:
        :term:`members <member>` date of birth
    
    :Active:
        if *yes*, indicates :term:`member` is currently on the racing team

The view has the following filters:

    :Show inactive members:
        check this to see inactive members. This allows old members to be added back to
        the racing team by checking this then setting the old member's **Active** to *yes*

.. note::
    before using this view, new :term:`members <member>` needs to be created on the :ref:`Members view`, and 
    assigned :term:`racingteam member` :term:`security role` there

.. image:: images/racing-team-members-view.*
    :align: center

.. image:: images/racing-team-members-edit.*
    :align: center
