# members
member activity management

## user management

### Interests
While this system is being created for Frederick Steeplechasers Running Club, we'd like to keep it possible to be used by other groups. "interest" is what we're calling the group, and all tasks / administration, etc., are segregated by interest.

* all database items have "interest" as a field e.g., the name of a club, to allow the database items to be maintained separately
* all users are configured with one or more "interests" which they may access

### Security Roles
all users are configured with one or more "security roles", which allow them access to specific system views. This module supports the following security roles.

* leadership-admin is is given access to create leadership task items
* leadership-member is given access to leadership task 

## leadership task module

A club needs new members of its leadership team to do several tasks. E.g., the member needs to gain access to the club's documents, read certain policies, make certain commitments. The "leadership task module" of this system is designed to define these tasks, and track the members' completion records.

### Leadership Tasks
The system keeps track of each leadership-member user's indication that they have completed each of a list of tasks, and when this was completed. 

* leadership tasks are displayed to leadership-member user (task checklist view)
* each leadership task has a priority, which controls the order of display
* user can select a task, open an "edit task" window, and click a "completed" button to mark the task as completed
* leadership-admin sets the period for task (e.g., conflict of interest may be required every other year, safe sport every year), after which the task is shown once again as uncompleted to the leadership-member

### Leadership Task Type
Tasks are not one size fits all. Different tasks may have different information which needs to be displayed, or collected from the leadership-member user. For this there's leadership task type.

* leadership tasks are assigned a task type, with differing types causing "edit task" display to show specific fields
* task display may include (e.g.) link to document which must be read in order to mark task completed, etc.
* there may be metadata which needs to be collected for a particular task type (e.g., conflict of interest information)

### Leadership Task Groups
To facilitate assignment of sets of tasks to individual leadership-member users, tasks are assigned into one or more task groups, and leadership-member users are assigned one or more task groups.

* leadership-admin creates leadership task groups to facilitate assignment of groups of tasks to leadership-member users
* leadership tasks may be assigned to one or more leadership task groups
* leadership-member users are assigned one or more leadership task groups which are displayed on their task checklist view

### Leadership Admin Tracking
The leadership-admin needs to be able to see summaries of what tasks are outstanding in total and for individual leadership-member users. These views are defined for this purpose.

* leadership task summary view - shows an overview of task compliance
* leadership task individual view - shows task compliance by leadership-member user

### Leadership Task Reminder Emails
For those members who have not completed all there tasks, emails will be sent periodically to remind them what tasks are outstanding.

* individual emails are sent to leadership-members who have outstanding tasks
* period is defined outside of the system, by cron job or similar (e.g., every two weeks)
* how to determine if task is overdue? should we send emails for any tasks which are not completed at the time the email is sent? Or should there be some grace period after the user has "signed on" to the system for the first time, and after the task expires?
* leadership-admin receives summary email, separate from the individual emails mentioned above
