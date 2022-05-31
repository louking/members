*******************************************
Racing Team Admin Guide
*******************************************

This guide describes the concepts of the **membertility** Racing Team Module, and gives guidance on
how to achieve the associated work flow.

Use cases
============================================================================

These sections describe what an :term:`racingteam admin` might want to do in support of the :term:`racing team`.


add a new racing team member
-------------------------------
If the racing team :term:`member` was not already in the system, they need to be added to the system before adding them to the 
racing team.

* use :ref:`Members view` to add the racing team member to the system
* first check to see if they are already in the system, using search on their name
* if they are in the system, see :ref:`update member for racing team`
* if they are not in the system,

  *  click **New**
  *  fill in **Email**, **First Name**, **Full Name**

     .. note::
         the field is **Full** Name, not **Last** Name

  *  For **Role** add *leadership-member*, *racingteam-member*
  *  For **Interests** add *Frederick Steeplechasers Running Club*
  *  Click **Create**

* continue with :ref:`add a member to the team`


.. _update member for racing team:

update member for racing team
-------------------------------
If the racing team :term:`member` was in the system but not yet on the team, their record may need to be updated.

* use :ref:`Members view` to update the racing team member's configuration to support racing team features

  *  select the member
  *  click **Edit**
  *  make sure **Role** includes *leadership-member*, *racingteam-member*
  *  make sure **Interests** includes *Frederick Steeplechasers Running Club*
  *  make sure **Active** is *yes*
  *  Click **Update**

* continue with :ref:`add a member to the team`


.. _add a member to the team:

add a member to the team
---------------------------
The team :term:`member` :term:`terms <term>` are managed via the Racing Team Member :term:`position`.

* from :ref:`Positions view` select *Racing Team Member* :term:`position`
* use the :ref:`Position Wizard` to manage the team membership
  
  * add the :term:`member` on the effective date

team management
----------------------

* the :ref:`Positions view` can be used to show the team on a given date by searching for *Racing Team Member*
* the :ref:`Position Dates view` can be used to show the :term:`position` :term:`terms <term>` directly by searching for 
  *Racing Team Member*
* the :ref:`Distribution List view` can be used to get a distribution list for the racing team on a given date

remove a member from the team
--------------------------------
The team :term:`member` :term:`terms <term>` are managed via the Racing Team Member :term:`position`.

* from :ref:`Positions view` select Racing Team Member :term:`position`
* use the :ref:`Position Wizard` to manage the team membership
  
  * remove the :term:`member` on the effective date

open racing team applications outside of normal window
-------------------------------------------------------

* use :ref:`Racing Team Config view` to manage the racing team configuration

  * normally **Open Behavior** should be set to *auto* to automatically allow applications during the specified date ranges
  * if you want applications to be open outside of the date ranges, set **Open Behavior** to *open*
  * don't forget to reset to *auto* to have the normal behavior



