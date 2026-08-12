'''
fakecurrentuser - minimal stand-in for flask_security.current_user, for tests

The admin API view classes (organization_admin.PositionWizardApi, awards_admin.RaceAwardsBase,
etc.) call current_user.has_role(role) directly in their permission() methods rather than
taking a user as a parameter, and each module imports its own `current_user` name
(`from flask_security import current_user`) -- so tests monkeypatch that module-level name
to one of these rather than setting up real Flask-Security login state.
'''


class FakeCurrentUser:
    def __init__(self, roles=()):
        self._roles = set(roles)

    def has_role(self, role):
        return role in self._roles
