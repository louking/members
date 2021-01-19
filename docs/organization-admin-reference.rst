===========================================
Organization Admin Reference
===========================================

This page gives a reference to all **membertility** views which are available to
:term:`members <member>` who have access to the Organization menu via various :term:`security roles <security role>`.


.. _Members view:

Members view
===============
**Navigation:** Organization > Members

The Members view is used to add new system users, known within this document as :term:`members <member>` to the system,
and to assign their :term:`security roles <security role>` and :term:`interests <interest>`.

When creating a new :term:`member` using this view, click **Create and Send** to send an email may be sent to the
:term:`member's <member>` email address. This email contains a link the :term:`member` can use to reset their
password. Click **Create** to create the new :term:`member` without sending and email.

A reset password email can also be sent to the :term:`member` by clicking **Reset Password** from the edit modal.

.. note::
    This data is in the common database. See :ref:`Single Sign-On` for details about how the common database is used.

..

    :Email:
        email address for the :term:`member`

    :First Name:
        the :term:`member's <member>` first name

    :Full Name:
        the :term:`member's <member>` full name

    :Roles:
        the :term:`security role(s) <security role>` which will be used by the application when this
        :term:`member` is accessing the system

    :Interests:
        (:term:`super admin` only) the :term:`interests <interest>` which will be available to the :term:`member`

        .. note::
            for non :term:`super admin`, when a :term:`member` is created, they will have the :term:`interest` currently
            selected by the :term:`organization admin`.

    :Active:
        if *yes*, the :term:`member` may log in and access the system

.. image:: images/members-view.*
    :align: center

.. image:: images/members-create.*
    :align: center

.. image:: images/members-edit.*
    :align: center


.. _Position Dates view:

Position Dates view
=====================
**Navigation:** Organization > Position Dates

With the Position Dates view, each :term:`term` for which a :term:`member` held/holds a :term:`position` can be viewed or
edited. But please note that the :ref:`Position Wizard` is the easiest way to manipulate this table.

    :Member:
        :term:`member` who holds or held the :term:`position` from **Start Date** to **Finish Date**

    :Position:
        :term:`position` which is held by the :term:`member` from **Start Date** to **Finish Date**

    :Start Date:
        date that the :term:`member` started this :term:`term` of the :term:`position`

    :Finish Date:
        date that the :term:`member` finished this :term:`term` of the :term:`position`. If the
        :term:`member` is currently in this :term:`position`, this should be left blank

The view has the following filters:

    :In Position On:
        date of interest for which :term:`members <member>` hold :term:`positions <position>`

.. image:: images/position-dates-view.*
    :align: center

.. image:: images/position-dates-edit.*
    :align: center


.. _Positions view:

Positions view
==============
**Navigation:** Organization > Positions

The Positions view is used for the following

    * associate :term:`task groups <task group>` to each :term:`position` to follow the :ref:`Task Hierarchy`.
    * identify which :term:`positions <position>` receive :term:`summary emails <summary email>`
      for any *overdue* tasks within specific :term:`task groups <task group>`.
    * identify which :term:`positions <position>` have :term:`meeting` :term:`status reports <status report>`
    * tag :term:`positions <position>` for use within :ref:`Meetings Module` for :term:`invitations <invite>` and
      :term:`voting <vote>`
    * add a heading to group this :term:`position` under for the :term:`meeting` :term:`agenda` and :term:`status report`
      (headings are managed by the :term:`meeting admin` using the :ref:`Agenda Headings view`)

The Positions view defines all of the :term:`positions <position>` within the organization. The
:term:`organization admin` can assign :term:`members <member>` to a position from this view using the
:ref:`Position Wizard` (preferred), or from the :ref:`Position Dates view`.

    :Position:
        name of the position

    :Description:
        describes the position, possibly giving more information than just the name

    :Members:
        list of :term:`members <member>` holding this position. This list is managed using the
        :ref:`Position Wizard` or the :ref:`Position Dates view`

    :Has Status Report:
        indicate whether the :term:`members <member>` in this :term:`position` should be prompted for
        a :term:`status report` about the :term:`position`

    :Tags:
        :term:`tags <tag>` associated with this position. See :ref:`Tags Guide` for more information on
        how :term:`tags <tag>` are used

    :Agenda Heading:
        the heading under which this :term:`position` is shown in the :term:`agenda` and :term:`status report` for
        :term:`meetings <meeting>` which include this :term:`position`

    :Task Groups:
        list of :term:`task groups <task group>` that are associated with the :term:`position` to follow
        the :ref:`Task Hierarchy`

    :Email Groups:
        list of :term:`task groups <task group>` for which :term:`summary emails <summary email>`
        for any *overdue* tasks are sent to supervisory :term:`members <member>` holding this :term:`position`

The view has the following filters:

    :In Position On:
        date of interest for which :term:`members <member>` hold :term:`positions <position>`

.. image:: images/positions-view.*
    :align: center

.. image:: images/positions-edit.*
    :align: center


.. _Position Wizard:

Position Wizard
--------------------
**Navigation:** Organization > Positions > [select position] > **Position Wizard**

The Position Wizard is invoked from the :ref:`Positions view` by selecting a :term:`position` and then clicking
**Position Wizard**. This wizard automatically updates :term:`terms <term>` for :term:`members <member>` for the selected
:term:`position`.

    :Effective Date:
        date at which this change should become effective

    :Members:
        select the :term:`members <member>` which are in the position on the **Effective Date**. When the **Effective Date**
        is chosen, the existing :term:`members <member>` for that :term:`position` on that date are shown.

        Remove :term:`members <member>` who won't remain in the :term:`position` as of the **Effective Date**, and add
        :term:`members <member>` who will be starting the :term:`position` on the **Effective Date**.

        For :term:`members <member>` who will remain in the :term:`position`, leave them selected.

.. hint::
    The result of Position Wizard **Update** can be viewed at :ref:`Position Dates view`.

.. image:: images/positions-wizard.*
    :align: center

.. _Tags view:

Tags view
======================
**Navigation:** Organization > Tags

Tags are used for grouping together :term:`positions <position>` and :term:`members <member>` for various purposes,
e.g., for invitations to be sent for a :term:`meeting`, or to indicate who may :term:`vote` at a :term:`meeting`.
See :ref:`Tags Guide` for a complete list of how :term:`tags <tag>` should be used.

    :Tag:
        name of tag

    :Description:
        description of how the tag is used

    :Positions:
        this tag is attached to these :term:`positions <position>`

    :Members:
        this tag is attached to these :term:`members <member>`

    .. note::
        it is recommended to use the **Positions** field rather than **Members** field because as
        :term:`positions <position>` change, use of **Members** may become out of date

.. image:: images/tags-view.*
    :align: center

.. image:: images/tags-edit.*
    :align: center



