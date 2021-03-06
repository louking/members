===========================================
Super Admin Reference
===========================================

.. _Applications view:

Applications view
====================
**Navigation:** Super > Applications

The Applications view has one entry per **loutilities** application. This should only be changed by the software development team.

.. note::
    This data is in the common database. See :ref:`Single Sign-On` for details about how the common database is used.

.. image:: images/applications-view.*
    :align: center


.. _Email Templates view:

Email Templates view
======================
**Navigation:** Super > Email Templates

The Email Templates view has one entry per system email type. For details of the substitution variable
usage, see the indicated software module(s).

.. list-table:: email types and substitution variables
    :widths: 15 15 40 30
    :header-rows: 0
    :stub-columns: 0
    :align: center

    *   - **module**
        - **email type**
        - **substitution variables**
        - **software module(s)**
    *   - leadership task
        - leader-email
        - members, member.tasks, task.task, task.expires
        - `leadership_emails.py <https://github.com/louking/members/blob/master/members/scripts/leadership_emails.py>`__
    *   - leadership task
        - member-email
        - tasks, task.task, task.status, task.expires
        - `leadership_emails.py <https://github.com/louking/members/blob/master/members/scripts/leadership_emails.py>`__

.. image:: images/email-templates-view.*
    :align: center


.. _Files view:

Files view
=================
**Navigation:** Super Files

The Files view gives the superadmin visibility into the files which were uploaded into the system.

.. image:: images/files-view.*
    :align: center


.. _Interests view:

Interests view
===============
**Navigation:** Super > Interests

The Interests view gives the superadmin control over what :term:`interests <interest>` are available to what
applications, and to control what users/:term:`members <member>` are able to access what :term:`interests <interest>`
(the latter is also available via the :ref:`Members view`).

.. note::
    This data is in the common database. See :ref:`Single Sign-On` for details about how the common database is used.
..

    :Description:
        name of interest, used for the select in the banner in all the views

    :Slug:
        used to identify the :term:`interest` in URLs

    :Public:
        *yes* or *no* for whether this :term:`interest` is visible via the public interface

    :Applications:
        applications within which this :term:`interest` is shown

    :Users:
        users/:term:`members <member>` who are able to use this :term:`interest`

.. image:: images/interests-view.*
    :align: center


.. _Interest Attributes view:

Interest Attributes view
===========================
**Navigation:** Super > Interest Attributes

The Interest Attributes view allows the superadmin to control certain attributes which may be specified by
:term:`interest`.

.. note::
    This data is in the local application database.
..

    :Interest:
        this view is pre-populated with :term:`interests <interest>` which are defined in the :ref:`Interests view`

    :Initial Expiration:
        Expiration Date to be used for :term:`tasks <task>` which have **Period** defined and have not ever been marked
        complete

    :From Email:
        email address to be used as the from address for emails sent by the system

.. image:: images/interest-attributes-view.*
    :align: center


.. _Roles view:

Roles view
=============
**Navigation:** Super > Roles

The Roles view is used to define :term:`security roles <security role>` and assign them to specific applications.
This must be coordinated with the software developement and is therefore best left to the software development
team to configure.

    :Name:
        name of the :term:`security role`, as used by the application internally

    :Description:
        description of the :term:`security role`, i.e., what it means to the user/:term:`member` system capabilities

    :Applications:
        applications which use this :term:`security role`

.. note::
    This data is in the common database. See :ref:`Single Sign-On` for details about how the common database is used.
..

.. image:: images/roles-view.*
    :align: center

