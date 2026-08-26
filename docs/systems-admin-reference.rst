===========================================
Systems Admin Reference
===========================================

This page gives a reference to all **membertility** views which are available to
:term:`members <member>` who have access to the Systems menu via various :term:`security roles <security role>`.


.. _Systems view:

Systems view
===============
**Navigation:** Systems > Systems

The Systems view defines all of the :term:`systems <system>` :term:`members <member>` may need access to
because of a :term:`position` they hold. See :ref:`Systems and Access Levels`.

    :System:
        name of the system, e.g., Google Workspace, MailChimp, Canva, the club website, a RunSignUp race,
        membertility itself, or any other system the club needs access to

    :Slug:
        stable identifier for this system, used in place of its name in the bootstrap CSVs
        (``bundles.csv``, and the ``access-report --actual-csv``) so a CSV keeps working even if the
        system's name is later reworded. Must be unique. Recommended: lowercase, hyphenated, e.g.
        ``mailchimp``, ``google-workspace``

    :Description:
        describes the system, possibly giving more information than just the name

    :Active:
        if *yes*, this system is in current use

.. image:: images/systems-view.*
    :align: center

.. image:: images/systems-edit.*
    :align: center


.. _System Access Levels view:

System Access Levels view
============================
**Navigation:** Systems > System Access Levels

The System Access Levels view defines the levels of access available within each :term:`system`. Every
:term:`system` needs at least one :term:`access level`, even if there's only one tier of access -- see
:ref:`Systems and Access Levels`.

    :System:
        the :term:`system` this access level belongs to

    :Access Level:
        name of the access level, e.g. "Super Admin" for one of membertility's several administrative
        :term:`security roles <security role>`

    :Slug:
        stable identifier for this access level, used in place of its name in the bootstrap CSVs. Must
        be unique within its :term:`system` (but may repeat across different systems, e.g. two systems
        can each have an ``super-admin`` slug). Recommended: lowercase, hyphenated, e.g. ``super-admin``

    :Description:
        describes the access level, possibly giving more information than just the name

    :Active:
        if *yes*, this access level is in current use

.. image:: images/system-access-levels-view.*
    :align: center

.. image:: images/system-access-levels-edit.*
    :align: center


.. _Access Types view:

Access Types view
============================
**Navigation:** Systems > Access Types

The Access Types view defines named bundles of :term:`system`/:term:`access level` pairs which are shared by
several :term:`positions <position>` -- see :ref:`Access Types Guide`.

    :Access Type:
        name of the access type, e.g. "Race Director access"

    :Slug:
        stable identifier for this access type, used in place of its name in the bootstrap CSVs
        (``bundles.csv``, ``positions.csv``). Must be unique. Recommended: lowercase, hyphenated, e.g.
        ``race-director-access``

    :Description:
        describes the access type, possibly giving more information than just the name

    :Active:
        if *yes*, this access type is in current use

    :System Access:
        the :term:`system`/:term:`access level` pairs bundled into this access type

.. image:: images/access-types-view.*
    :align: center

.. image:: images/access-types-edit.*
    :align: center


.. _Access Checklist view:

Access Checklist view
============================
**Navigation:** Systems > Access Checklist

The Access Checklist view lists :term:`system` access grant/revoke actions a :term:`systems admin` needs to
take in the real external systems, generated automatically when a :term:`member's <member>` :term:`positions
<position>` change in a way that changes what access they need -- see :ref:`Access Checklist Guide`. Every
field except **Resolved** is set automatically and can't be edited.

    :Member:
        the :term:`member` whose required access changed

    :Action:
        **grant** if the :term:`member` newly needs this access, **revoke** if they no longer need it

    :System:
        the :term:`system` this entry is about

    :Access Level:
        the :term:`access level` this entry is about

    :Position:
        the :term:`position` whose change triggered this entry

    :Effective Date:
        date the change takes effect

    :Detected:
        date and time this entry was added to the checklist

    :Resolved:
        once the :term:`systems admin` has made the actual change in the real :term:`system`, edit this to
        today's date to check the entry off the list. Leave blank while the entry is still outstanding.

    :Resolved By:
        the :term:`member` who resolved this entry, filled in automatically when **Resolved** is set

.. image:: images/access-checklist-view.*
    :align: center

.. image:: images/access-checklist-edit.*
    :align: center
