*******************************************
Meetings Admin Guide
*******************************************

This guide describes the concepts of the **membertility** Meetings Module, and gives guidance on
how to achieve the :term:`meeting` work flow.

The general work flow for :term:`meetings <meeting>` is

* :term:`meeting admin` creates :term:`meeting`, indicating who would be invited, date, time, location, and purpose of the meeting
* :term:`meeting admin` generates :term:`invitations <invite>` for the :term:`meeting`
* in the :term:`invitation <invite>`, the :term:`member` is given a link to click

    * :term:`member` is shown any outstanding :term:`action items <action item>` they're responsible for
    * :term:`member` clicks link and can indicate if :term:`attending <rsvp>` the :term:`meeting`
    * :term:`member` should also give their :term:`status report` for each :term:`position` they're responsible for
    * :term:`member` can update :term:`action item` status and record comments about the :term:`action item`
    * :term:`member` can add any :term:`discussion items <discussion item>` for :term:`meeting`

* as :term:`members <member>` add :term:`discussion items <discussion item>`, the :term:`meeting` :term:`agenda` is
  being built, with each :term:`discussion item` turned into a :term:`meeting` :term:`agenda item`
* when ready, the :term:`meeting admin` can generate :term:`status report` and :term:`agenda` documents

    * this will go to a Google Workspace drive location. In a future releases support will be added to create a Word doc
    * once a Google Workspace file is created, it is updated nightly as :term:`members <member>` continue to add or update
      :term:`status reports <status report>`. Alternately, the :term:`meeting admin` can cause it to be updated on demand
    * the Google Workspace documents are initially generated to a configured folder, but
      can safely be moved to any desired folder

* additional emails can be sent to the :term:`meeting` :term:`invite` list if needed, e.g., with links to documents
  which should be read to prepare for the meeting
* during the meeting, the admin can do the following, which forms the minutes for the meeting

    * update attendee list (who actually came)
    * add discussion about any :term:`agenda item`
    * add an :term:`action item` under an :term:`agenda item`
    * add a :term:`motion` under an :term:`agenda item`, and tally its :term:`votes <vote>`
    * create a new :term:`agenda item` (e.g., for unplanned discussion)

* after the meeting, the admin can make any adjustments to the notes which were taken, and when satisfied, generate the
  :term:`minutes` document (again to a Google Workspace drive location)

    * when :term:`minutes` from the last meeting are voted on, changes are rarely required. But if changes are required, the
      admin can go into the last :term:`meeting's <meeting>` view, make the changes, and generate the :term:`minutes` again
    * Google Workspace :term:`minutes` are generated to configured location but can safely be moved to the desired folder

* :term:`action items <action item>`, :term:`motions <motion>` / :term:`votes <vote>`, :term:`minutes` are available to
  the :term:`members <member>` through the system immediately after the meeting
* :term:`members <member>` receive reminder emails about outstanding :term:`action items <action item>`

Meeting Data Model
======================

..
   see https://www.graphviz.org/
   see http://graphs.grevian.org/

.. graphviz::

   digraph records {
        graph [fontname = "helvetica"];
        node [fontname = "helvetica"];
        edge [fontname = "helvetica"];
        "member 1" -> "position report 1";
        "member 2" -> "position report 1";
        "member 3" -> "position report 2";
        "member 4" -> "position report 3";
        "member 4" -> "ad hoc report 4";
        "meeting admin 1" -> "agenda item 4";
        "position report 1" -> "discussion/agenda item 1";
        "position report 1" -> "discussion/agenda item 2";
        "position report 2" -> "discussion/agenda item 3";
        "discussion/agenda item 1" -> "action item 1";
        "discussion/agenda item 2" -> "motion 1";
        "motion 1" -> "motion vote tally 1";
        { rank=same; "member 1", "member 2", "member 3", "member 4", "meeting admin 1" };
        { rank=same; "position report 1", "position report 2", "position report 3", "ad hoc report 4" };
        { rank=same; "discussion/agenda item 1", "discussion/agenda item 2", "discussion/agenda item 3", "agenda item 4" };
        { rank=same; "action item 1", "motion 1" };
    }

Prepare for Meeting Module use
===============================================================================

The following needs to be set up in the database before using the meeting module. These require the indicated role
to achieve. Full documentation of this is TBD.

* create :term:`positions <position>`, with proper **Has Status Report** configuration [organization-admin]
* assign :term:`members <member>` to their :term:`position(s) <position>` [organization-admin]
* create :term:`tags <tag>` which will be used to :term:`invite` :term:`members <member>` to :term:`meetings <meeting>`
  and to indicate the :term:`voting members <voting member>` [meetings-admin]
* set :term:`interest` defaults for **Meeting Invite Tags**, **Meeting Vote Tags**, Google Workplace folders
  [super-admin]


Use cases for before the meeting (for when you want to...)
============================================================================

These sections describe what an :term:`meeting admin`  might want to do when planning a :term:`meeting`.

create a meeting
---------------------------

When a :term:`meeting` is being planned, the first thing to do is create it.

* bring up :ref:`Meetings view`
* click **New**

    .. include:: meetings-meetings-fields.rst

* click **Create**

To access the :term:`meeting` you just created, select the new row and click **View Meeting**. You'll see that there is an
:term:`action item` :term:`agenda item` which was automatically created.

If the **Meeting Type** has an **Automatic Agenda Item Title**, an :term:`agenda item` with the indicated title is created.

renew a meeting
---------------------------
If a previously held :term:`meeting` needs to be created again, an easy way is to renew it.

* bring up :ref:`Meetings view`
* click **Renew**

    .. note::
        all of the fields are filled in based on the meeting being renewed, but you'll want to change the
        **Date** to be the date of the new meeting

    .. include:: meetings-meetings-fields.rst

    * **Renew Options** are defaulted based on **Meeting Type**. These can be changed for this renewal, but if you find
      yourself changing these each time, it would probably be best to set them as you'd like in the :ref:`Meeting Types view`.

* click **Renew**

To access the :term:`meeting` you just renewed, select the new row and click **View Meeting**. You'll see that there is an
:term:`action item` :term:`agenda item` which was automatically created, and any agenda items which were meant to be
copied based on the **Renew Options** will also be there.

If the **Meeting Type** has an **Automatic Agenda Item Title**, an :term:`agenda item` with the indicated title is created.


invite members to a meeting (in-person / virtual)
-------------------------------------------------------------------------------------
In order to :term:`invite` :term:`members <member>` to an in-person or virtual meeting, you must be in the
:term:`meeting's <meeting>` :ref:`Meeting view`. To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from
:ref:`Meetings view` select the meeting and click **View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* click **Send Invitations**
* there will be a popup with the list of :term:`members <member>` who will be invited, and you will be given the option
  to change the **Subject**, add a **Message**, and update the **From** address
* click **Send Invitations**

The :term:`invitations <invite>` are sent to the :term:`members <member>` who resolve to the **Invite Tags**
specified for the :term:`meeting`.

If the **Meeting Type** is has the option *RSVP Required*, an :term:`agenda item` with title *Attendees* is created. As
:term:`invited <invite>` :term:`members <member>` :term:`rsvp` to the meeting, their **RSVP** will show whether
they plan to come to the :term:`meeting`.

invite member discussion for a meeting (*Online Motion/Votes*)
---------------------------------------------------------------------------------------------
In order to solicit discussion for a meeting with *Online Motion/Votes*, you must be in the
:term:`meeting's <meeting>` :ref:`Meeting view`. To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from
:ref:`Meetings view` select the meeting and click **View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* click **Send Discussion Request**
* there will be a popup with the list of :term:`members <member>` who will be invited, and you will be given the option
  to change the **Subject**, add a **Message**, and update the **From** address

  .. hint::

    the **Message** should include what the discussion is about, and when the discussion should be completed. The
    :term:`meeting` **Date** is the last day for voting on any :term:`motions <motion>` which come out of the
    discussion

* click **Send Discussion Request**

The :term:`discussion request` is sent to the :term:`members <member>` who resolve to the **Invite Tags**
specified for the :term:`meeting`. The intention is that discussion will be held on the email thread. Once the discussion
has run its course, motion text should be proposed and the motion moved and seconded.

This electronic voting process continues at :ref:`create online motion`.

check to see if status reports are missing, and send reminders
------------------------------------------------------------------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting Status view`, from :ref:`Meetings view` select the meeting and click
**Meeting Status**.

From the :term:`meeting's <meeting>` :ref:`Meeting Status view`,

* to determine which :term:`status reports <status report>` are missing, set the **Status** filter on the top to *missing*
* select one or more :term:`positions <position>` you'd like to send reminders to

  .. note::
    to see all the :term:`positions <position>`, you may need to show additional entries (top left of the table)

* click **Send Reminders**
* there will be a popup with the list of :term:`members <member>` to whom reminders will be sent, and you will be given the option
  to change the **Subject**, add a **Message**, and update the **From** address
* click **Send Reminders** to send the reminder emails

on behalf of a member, enter RSVP and status reports
-----------------------------------------------------------------------------------------------------

If a :term:`member` isn't able to use the system to :term:`RSVP <rsvp>` and/or enter their
:term:`status reports <status report>`, the :term:`meeting admin` can use the :ref:`Their Status Report view` to
enter the information provided outside the system.

To access the :term:`meeting's <meeting>` :ref:`Their Status Report view`, from :ref:`Meetings view` select the
meeting and click **Their Status Report**. An empty view is displayed.

To enter the :term:`member's <member>` :term:`RSVP <rsvp>` and/or :term:`status reports <status report>`, select the
member in the table heading. From there, you can proceed as if you were the selected :term:`member`, using the instructions
from :ref:`My Status Report view`.

review the agenda
-------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click
**View Meeting**. The current :term:`agenda` is displayed.

As :term:`members <member>` add :term:`discussion items <discussion item>` to their :term:`status report`, these get
added as :term:`agenda items <agenda item>` for the meeting.

Once most of the :term:`status reports <status report>` have been received, you may want to update the
:term:`agenda item` titles, or update the headings which will be used to outline the :term:`agenda items <agenda item>`
in the :term:`agenda` and :term:`minutes` documents.

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* if the :term:`agenda item` title chosen by the :term:`member` is unclear, you can make updates here.

    * select the :term:`agenda item`, click **Edit**, then update the **Title**

      .. note::
        discussion item titles shown in the :term:`status report` document will show the :term:`member's <member>` original
        text

* each :term:`position` has a default :term:`agenda` heading, but if this needs to be changed

    * select the :term:`agenda item`, click **Edit**, then select the **Agenda Heading** (new :term:`agenda` headings
      must be created first using the :ref:`Agenda Headings view`)

* **Summary** captures what the :term:`member` said in the :term:`discussion item`. If necessary, this can be edited
  for clarity

    * select the :term:`agenda item`, click **Edit**, then update the **Summary**

      .. note::
        this overwrites the words written by the :term:`member` when they created their :term:`status report` and
        will be reflected into the :term:`status report` document, so should be done only when needed

reorder agenda items
-------------------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click
**View Meeting**. The current :term:`agenda` is displayed.

As each :term:`discussion item`/:term:`agenda item` is collected, it is automatically added to the end of the
:term:`agenda`. Once most of these are collected, it may be desired to reorder them.

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

.. |reorder-icon| image:: images/reorder-icon.*

* use the reorder icon (|reorder-icon|) to grab an :term:`agenda item` and place it where desired in the
  :term:`agenda` order

  .. note::
    for best results, :term:`agenda items <agenda item>` with the same :term:`agenda` heading should be grouped together

create a new agenda item
-----------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click **View Meeting**

The :term:`meeting admin` may want to add specific :term:`agenda items <agenda item>` related to the :term:`meeting`, such
as *Call to Order*, *Next meeting <date>*, or such.

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* click **New**
* enter **Title**
* (optional) enter **Summary**
* (optional) select **Agenda Heading** (new :term:`agenda` headings must be created first using the
  :ref:`Agenda Headings view`)
* click **Save**
* reorder as needed

generate meeting documents
-------------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click
**View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* click **Generate Docs**
* select the documents to be generated (e.g., *Agenda*)
* click **Submit**
* the documents are generated and the popup disappears
* the link(s) to the documents can be found using the :ref:`Meetings view`

.. note::

    the :term:`status report` document is automatically updated as :term:`members <member>` update their
    status reports, after a slight delay

send email to meeting invitees
---------------------------------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click
**View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* click **Send Email**
* there will be a popup with the list of :term:`members <member>` to whom the email will be sent, and you will be given
  the option to change the **Subject**, add a **Message**, and update the **From** address
* click **Send Email**

Use cases for during the meeting (for when you want to...)
============================================================================
This section describes what the :term:`meeting admin` might want to do during the :term:`meeting`.

update the attendance list
------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click
**View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* select the :term:`agenda item` entitled *Attendees*
* click **Edit**
* under the **Invites** table, on the :term:`member` row, click the cell under the **Attended** column to change
* click off the selected cell to save -- when select widget disappers, the entry is saved

  .. important::
    if you don't click off the selected cell, this change won't be saved

.. note::
    if someone comes to the meeting who isn't in the Invites table, this can be recorded in the **Discussion**
    field -- use a bullet list for best formatting in the :term:`minutes` document

add discussion about an agenda item
---------------------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click
**View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* select the :term:`agenda item` to be discussed
* click **Edit**
* add discussion text under **Discussion**
* click **Save**

add an action item
---------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click
**View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* select the :term:`agenda item` being discussed which relates to the :term:`action item`
* click **Edit**
* under **Action Items**, click **New**
* enter a concise, specific description of the action item under **Action**
* generally the **Comments** section should be left blank at this point (but see the **Note** below)
* select an **Assignee** who is responsible for the action

  .. note::
    a single **Assignee** is responsible for any :term:`action item`. If the **Assignee** should be working
    with others and the names need to be captured, this can be done within the **Action**, or within the **Comments**

* click **Create**

record a motion, its discussion, and vote tally (in-person / virtual)
----------------------------------------------------------------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click
**View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* select the :term:`agenda item` being discussed which relates to the :term:`motion`
* click **Edit**
* under **Motions**, click **New**
* enter a clear, specific description of the :term:`motion` under **Motion** (see the references for best practices
  for wording motions)
* select the person who made the motion as the **Mover**
* select the person who seconded the motion as the **Seconder**
* optionally record any comments about the :term:`motion` which come out during the discussion
* if the wording of the :term:`motion` needs to be changed due to the discussion, change this now
* click **Create**

  .. note::
    the motion can be created as above, and then updated by clicking **Edit** under **Motions**

After creating the :term:`motion` the motion's **Votes** table is created. The :term:`votes <vote>` are initialized
to *approved* if the :term:`member` is recorded as attending the meeting and *novote* if not.

To edit the :term:`votes <vote>`,

* select the :term:`motion`
* under **Motions** click **Edit**
* under **Votes**, on the :term:`member` row, click the cell under the **Vote** column to change
* click off the selected cell to save -- when select widget disappers, the entry is saved

  .. important::
    if you don't click off the selected cell, this change won't be saved

  .. note::
    if a :term:`member` comes to the meeting  and votes after the :term:`motion` was created, their default *novote* can be
    changed accordingly without immediately updating their **Attendee** status

* in the :term:`motion` **Edit** form, select the resulting **Status** (*approved*, *rejected*, *tabled*) as appropriate
* click **Save**

References

* `How to Make a Motion at a Board of Directors Meeting`_
* `How to Write a Motion for a Board Meeting`_


.. _create online motion:

record a motion, its discussion, and vote tally (*Online Motion/Votes*)
----------------------------------------------------------------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view` select the meeting and click
**View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* select the :term:`agenda item` being discussed which relates to the :term:`motion`
* click **Edit**
* under **Motions**, click **New**
* enter a clear, specific description of the :term:`motion` under **Motion** (see the references for best practices
  for wording motions)
* select the person who made the motion as the **Mover**
* select the person who seconded the motion as the **Seconder**
* optionally record any comments about the :term:`motion` which come out during the discussion
* if the wording of the :term:`motion` needs to be changed due to the discussion, change this now
* click **Create**

  .. note::
    the motion can be created as above, and then updated by clicking **Edit** under **Motions**

After creating the :term:`motion` the motion's **Votes** table is created. The :term:`votes <vote>` are initialized
to *novote*.

To send a link for voting on the :term:`motion` to the :term:`voting members <voting member>`, select the :term:`motion` and click the
**Send eVote Requests** button. The :term:`voting members <voting member>` will be displayed, and the :term:`meeting admin`
will have the opportunity to change the **Subject**, **Message**, and **From Address**. The text of the :term:`motion`
will automatically be included in the email.

The :term:`voting members <voting member>` will receive an email with a link they can click to record their :term:`vote`.
All :term:`votes <vote>` must be recorded by the **Date** set for the :term:`meeting`.

.. note::

    if additional time is required for the voting, simply update the **Date** set for the :term:`meeting` using the
    :ref:`Meetings view`.

References

* `How to Make a Motion at a Board of Directors Meeting`_
* `How to Write a Motion for a Board Meeting`_

Use cases for after the meeting (for when you want to...)
============================================================================
These sections describe what an :term:`meeting admin`  might want to do after a :term:`meeting`.

generate meeting minutes
-----------------------------------------
To access the :term:`meeting's <meeting>` :ref:`Meeting view`, from :ref:`Meetings view`, select the meeting and click
**View Meeting**

From the :term:`meeting's <meeting>` :ref:`Meeting view`,

* click **Generate Docs**
* select the documents to be generated (in this case **Minutes**)
* click **Submit**
* the :term:`minutes` are generated and the popup disappears
* the link to the :term:`minutes` can be found using the :ref:`Meetings view`

add Google Workspace documents to a meeting folder
------------------------------------------------------

Prior to any :term:`meeting` being created, the :term:`super admin` must use the :ref:`Interest Attributes view` to
configure the system with a folder to store the Google Workspace documents which will be created. There's a separate
folder configuration for each type of document.

.. note::
    the folders for the types of documents can be the same or different as desired

If it is desired to have the documents accessible from some other folder (e.g., one which was created specifically for the
meeting), manual intervention is needed.

The file(s) must be "Added" rather than "Moved" to the specific meeting folder. This allows meeting
documents to be found in a well known place for ease of review across meetings, as well as in the folders for each
meeting. But more importantly, membertility only has permission to write to certain folders, so if the file is
moved that will cause problems with the access, and there will be unpredictable results.

Using Google Workspaces,

* open the folder where the file was created

  * to find this folder, click on the file's link in the :ref:`Meetings view`, then in the browser address box,
    change "preview" to "edit" and reload the page
  * then click on the folder icon to the right of the filename, which opens a pull-down
  * then click on the square/arrow icon to the right of the folder name in the pull-down to open the file's folder
  * again **please don't move the file**

* click on the file you want to add to another folder
* on your keyboard, press **Shift + z**
* choose the destination folder you want to add the file to
* click **Add here**

Now the same file(s) can be found by navigating to the well known folder, or by navigating to the meeting folder, and any
changes to the file(s) will happen in both folders.

Also see `Organize your files in Google Drive`_, click on Create a shortcut for a file or folder

.. warning::
    do not copy the file and save it somewhere else, as this would prevent the system from managing the file
    contents

.. warning::
    do not edit any of these files directly as the system may overwrite what you've changed. Rather, use the system to make
    any changes you want captured in the file. Then **Generate Docs** can be used to make the update to
    the :term:`agenda` or :term:`minutes`. :term:`Status report <status report>` will be updated automatically.

download images from the meeting report
--------------------------------------------------------------------
To access the meeting status report (or newsletter items), navigate to Meetings > Meetings. Under the **Report** column
click the link (the naming of the link depends on the :term:`meeting type`).

A google doc should open in another tab.

Google docs does not allow you to right click on the image and save. It gives you a way to copy the image but there
doesn't seem to be a way to paste the image locally. `How to Download All the Images From a Google Doc or Microsoft Word
Document`_ (and others) suggest downloading as html. This creates a zip file that includes the original images (named
as *image1.jpg*, etc).

In order to see the download menu, you need to manually change the "/preview" to "/edit" at the end of the URL in your
browser's address bar.

.. warning::
    do not edit this file directly as the system may overwrite what you've changed. Rather, use the system to make
    any changes you want captured in the file. Changes can be made to other :term:`member's <member>` reports by
    navigating to :ref:`Meetings view`, selecting the meeting, then clicking **Their Status Report** button, which
    will bring up :ref:`Their Status Report view`.


References
------------------------------------------------------

.. target-notes::

.. _`How to Make a Motion at a Board of Directors Meeting`: https://bizfluent.com/how-10030515-make-motion-board-directors-meeting.html
.. _`How to Write a Motion for a Board Meeting`: https://www.boardeffect.com/blog/how-to-write-a-motion-for-a-board-meeting/
.. _`Organize your files in Google Drive`: https://support.google.com/drive/answer/2375091
.. _`How to Download All the Images From a Google Doc or Microsoft Word Document`: https://zapier.com/blog/download-images-google-doc-word/