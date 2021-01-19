===========================================
Organization Admin Guide
===========================================

This guide describes the concepts of the membertility Organization Module.

.. _Position Management:

Position Management
=============================
:term:`positions <position>` are assigned to :term:`members <member>` for a variety of purposes. **membertility** tracks
who is currently in each :term:`position`, which is used by the :ref:`Meetings Module`, :ref:`Task Module`, etc.

New Member Instructions
---------------------------------
.. this section is duplicated between organization-guide and super-admin-guide, and should be kept consistent

When someone new needs to be added to the system, the following should be done:

* send suitable welcome message which describes the system, why they're being added, and that they'll be receiving
  password reset instructions
* create the member using :ref:`Members view`, assigning appropriate :term:`security roles <security role>` and
  :term:`interests <interest>`
* give new member their position(s) using :ref:`Position Wizard`

Term  Management
---------------------------------
The period during which a :term:`member` spends time in a :term:`position` is known as a :term:`term`. The
:ref:`Position Dates view` has a row for each :term:`term`, with the **Member**, **Position**, **Start Date**, and
**Finish Date** specified. If the :term:`term` is current, no **Finish Date** is specified.

For easy management of :term:`member's <member>` :term:`terms <term>` in :term:`positions <position>`, use the
:ref:`Position Wizard`. With the :ref:`Position Wizard`, you select an **Effective Date** for a change in
:term:`terms <term>` for one or more :term:`members <member>` for a given :term:`position`. The wizard takes care of
updating all the necessary :term:`term` records which can be seen using the :ref:`Position Dates view`.

Task Assignment
=====================
To facilitate assignment of sets of :term:`task groups <task group>` to individual :term:`members <member>`,
:term:`task groups <task group>` may be assigned to one or more :term:`positions <position>` using :ref:`Positions view`,
and in turn :term:`members <member>` are assigned one or more :term:`positions <position>` using :ref:`Position Wizard`.
The :ref:`Task Hierarchy` gives details on these relationships, and the :ref:`Task Module` has complete
details about :term:`task` management.

.. _Tags Guide:

Tags Guide
=============
Tags are used for the following. Tags are defined in the :ref:`Tags view`, assigned in the view in the **Based On**
column below, and used for the **Used For** purpose in the **View** column below.

.. list-table::
    :header-rows: 1
    :stub-columns: 0
    :align: center

    *   - Used For
        - Based On
        - View
    *   - Meeting Invitations
        - :ref:`Tags view`, :ref:`Positions view`
        - :ref:`Meetings view`
    *   - Meeting Voting
        - :ref:`Tags view`, :ref:`Positions view`
        - :ref:`Meetings view`







