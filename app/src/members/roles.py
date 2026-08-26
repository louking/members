'''
roles - app-local role constants
===========================================

Some roles are shared across loutilities-based apps and live in
loutilities.user.roles -- adding one there needs a new loutilities release.
Roles that only matter to this app belong here instead. A Role row with a
matching name still has to be created once via the Roles admin screen
(userrole.roles); nothing in loutilities.user validates role names against
any fixed list at runtime -- loutilities.user.roles.all_roles is only read by
loutilities.user.scripts.users_init's one-time seed script, not enforced
anywhere else.
'''

# systems admin: manages the System/SystemAccessLevel/AccessType reference
# data and the position-access checklist (see #716), without needing full
# super-admin access to everything else under the Super nav group
ROLE_SYSTEMS_ADMIN = 'systems-admin'
