===========================================
Membership Admin Reference
===========================================

The club's membership committee needs access to certain club-related data in order to perform their jobs. The
"membership module" of the **membertility** system is designed to provide access to this data.

.. _Club Members view:

Club Members view
====================

The Club Members view can be used to view or download club member records. Separate club member records are 
maintained for contiguous membership records (see :ref:`Memberships view`).

To show the members as of a particular date, set the **As Of** date.

To download the filtered spreadsheet of members, click the **CSV** button.

.. note::
    To download all of the members with the **CSV** button, you need to set **Show** to *all*.

The view has the following filters:

    :As Of:
        chooses the date for which memberships are shown


.. image:: images/club-members-view.*
    :align: center


.. _Expired Members view:

Expired Members view
===========================
**Navigation:** Members > Expired Members

The Expired Members view is used to determine members who have expired since a specific date. The members which have 
memberships expired on or after the **Since** date and before the current date are shown.

The view has the following filters:

    :Since:
        chooses the date on or after which the members memberships have expired

.. image:: images/expired-members-view.*
    :align: center


.. _Facebook Aliases view:

Facebook Aliases view
===========================
**Navigation:** Members > Facebook Aliases

The Facebook Aliases view is used to view and update the Facebook alias which might exist for any given
member. If present, this is displayed at the :ref:`Club Members view`.

    :Member:
        the :term:`member's <member>` name with birth date (to avoid ambiguity)

    :Alias:
        the name used on Facebook for this :term:`member's <member>`

.. image:: images/facebook-aliases-view.*
    :align: center

.. image:: images/facebook-aliases-edit.*
    :align: center


.. _Memberships view:

Memberships view
====================

The Memberships view can be used to view or download membership records. A membership record is created by the registration provider 
(e.g., RunSignUp) each time a member renews their membership. This is typically every year, but there are also multiyear memberships 
available. This view shows these individual memberships.

To download the filtered spreadsheet of memberships, click the **CSV** button.

.. note::
    To download all of the memberships with the **CSV** button, you need to set **Show** to *all*. This can take a while to
    load.

.. image:: images/memberships-view.*
    :align: center


.. _Membership Stats view:

Membership Stats view
==========================

The Membership Stats view gives a graphic view of year on year membership numbers. Hover the mouse over the chart (or if using a phone or tablet, touch the 
chart) to see the counts on a particular date.

This view is publicly available.

The view has the following filters:

    :Num Years:
        choose the number of years of data to show, or *all*

.. image:: images/membership-stats-view.*
    :align: center
