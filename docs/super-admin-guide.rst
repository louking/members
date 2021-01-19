===========================================
Super Admin Guide
===========================================

:term:`Members <member>` of a club’s leadership team are required to complete various :term:`tasks <task>` in
support of the on-boarding process. E.g., the member needs to gain access to the club's documents, read certain
policies, complete training courses, etc. Some of these :term:`tasks <task>` need to be renewed periodically. The
:ref:`Task Module` of the **membertility** system is designed to define these :term:`tasks <task>` and
track the :term:`members' <member>` completion records.

This guide describes the concepts of the **membertility** Leadership Task Module, as well as gives guidance for
how to configure the items accessible to the superadmin.

.. _Single Sign-On:

Single Sign-On
================
**membertility** is the first **loutilities** application which supports a common database for User administration
and password management. The tables in the common database are

* User - user management (email, password, name) for :term:`members <member>`

  .. note::
      In **membertility**, users are known as :term:`members <member>`

* Application - identifies the **loutilities** application (in this case, *members*)
* Role - :term:`security roles <security role>` are used to give permissions by application which can be associated to
  users/:term:`members <member>`
* Interest - interests are used to partition most database tables. These are by application and can be associated to
  users/:term:`members <member>`

Each application that supports Single Sign-On has access to these tables, and also has local user and interest
tables. When users or interests are updated from the application, the local tables are refreshed.

.. list-table:: common database tables are accessed through these views
    :header-rows: 0
    :stub-columns: 0
    :align: center

    *   - **table**
        - **view**
    *   - User
        - :ref:`Members view`
    *   - Application
        - :ref:`Applications view`
    *   - Role
        - :ref:`Roles view`
    *   - Interest
        - :ref:`Interests view`

.. warning::
    If a change is made to a user or interest from an application, the local tables at the other applications
    may not get refreshed. In this case, the :term:`super admin` must force the update of any entry in the common User or
    Interest table from the application which was not updated automatically, to force the refresh of its local table.

Reset Member Password
=======================
The :ref:`Members view` can be used to generate a password reset email to the :term:`member`. This does not invalidate
the current password, but does give the :term:`member` a link to get to the password reset view and change their
password.

Interest Attributes
=====================
There are certain attributes which are maintained in the application local database (not
the common database) which are associated with :term:`interests <interest>`. These are
accessed via the :ref:`Interest Attributes view`.

Email Setup
==============
The system sends emails periodically about :term:`tasks <task>` which are *overdue* or *expiring soon*. The contents
of these emails can be configured using the :ref:`Email Templates view`.

File Naming and Storage
==========================
Files are named on upload but stored based on a system-created file id. This allows multiple files with the same name to
exist separately within the system. The association between filename and file id can be seen using the :ref:`Files view`.

New Member Instructions
=========================
.. this section is duplicated between organization-guide and super-admin-guide, and should be kept consistent

When someone new needs to be added to the system, the following should be done:

* send suitable welcome message which describes the system, why they're being added, and that they'll be receiving
  password reset instructions
* create the member using :ref:`Members view`, assigning appropriate roles and interests
* give new member their position(s) using :ref:`Position Wizard`
