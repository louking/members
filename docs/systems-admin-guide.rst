===========================================
Systems Admin Guide
===========================================

This guide describes the concepts of the membertility Systems Module.

.. _Systems and Access Levels:

Systems and Access Levels
=============================
A :term:`system` is anything a :term:`member` may need access to because of a :term:`position` they hold --
Google Workspace, MailChimp, Canva, the club website, a RunSignUp race, or membertility itself.
:term:`Systems <system>` are defined using the :ref:`Systems view`.

Some :term:`systems <system>` have more than one level of access -- for example, membertility has several
administrative :term:`security roles <security role>`. Each :term:`system` needs at least one
:term:`access level`, defined using the :ref:`System Access Levels view`, even if there's really only one
level of access (in which case a single access level, e.g. "Access", is enough).

.. _Access Types Guide:

Access Types
=============================
Rather than assigning individual :term:`system`/:term:`access level` pairs to every :term:`position` one at a
time, related access requirements can be bundled into an :term:`access type` using the :ref:`Access Types view`
-- for example, an "Race Director access" :term:`access type` might bundle together Google Workspace, MailChimp, and RunSignUp race
:term:`access levels <access level>`. The "Race Director access" :term:`access type` can then be assigned to every 
:term:`position` that needs that bundle of access.

A one-off access requirement that isn't worth bundling into an :term:`access type` can instead be assigned
directly to a single :term:`position` as :term:`direct access` -- see :ref:`Positions view`.

A :term:`position's <position>` full set of required access is the combination of its :term:`access
types <access type>` and its :term:`direct access`.

.. _Access Checklist Guide:

Access Checklist
=============================
Whenever a :term:`member's <member>` :term:`positions <position>` change -- using the :ref:`Position Wizard` or
the :ref:`Position Dates view` -- membertility recomputes what :term:`systems <system>`/:term:`access
levels <access level>` that :term:`member` now needs, compares it to what they needed before the change, and
adds an entry to the :ref:`Access Checklist view` for anything that changed:

    * if the :term:`member` newly needs access to a :term:`system`, a **grant** entry is added
    * if the :term:`member` no longer needs access to a :term:`system`, a **revoke** entry is added

If a :term:`member` holds more than one :term:`position` that both require the same
:term:`system`/:term:`access level`, losing one of those :term:`positions <position>` does **not** add a
**revoke** entry, since the other :term:`position` still justifies the access. Only a genuine net change in
what the :term:`member` needs shows up on the checklist.

The :ref:`Access Checklist view` doesn't grant or revoke access on its own -- it's a reminder for the
:term:`systems admin` to go make the actual change in the real :term:`system` (MailChimp, RunSignUp, etc.).
Once that's done, edit the entry's **Resolved** date to check it off the list.

.. hint::
    Changing what a :term:`position` or :term:`access type` requires (in the :ref:`Positions view` or
    :ref:`Access Types view`) does **not** by itself add anything to the :ref:`Access Checklist view` -- the
    checklist only reacts to a :term:`member's <member>` :term:`positions <position>` changing, not to a
    :term:`position's <position>` requirements changing. Review access for anyone already holding an affected
    :term:`position` by hand after making that kind of change.
