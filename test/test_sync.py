'''
test_sync - test members.sync
=========================================================
'''

# standard
import logging

# homegrown
from members.sync import SyncManager


class _RecordingSyncManager(SyncManager):
    '''concrete SyncManager recording every hook call, for exercising import_group()'s
    add/update/remove algorithm without any real external service or group'''

    def __init__(self, svcusers, groupusers, group_key_map):
        self.svcusers = svcusers
        self.groupusers = groupusers
        self.group_key_map = group_key_map
        self.started = False
        self.finished = False
        self.updated = []
        self.added = []
        self.removed = []

    def start_import(self):
        self.started = True

    def get_users_from_service(self):
        return self.svcusers

    def get_users_from_group(self):
        return dict(self.groupusers)

    def get_group_key_from_service_user(self, svcuser):
        return self.group_key_map[svcuser]

    def check_update_user_in_group(self, svcuser, groupuser):
        self.updated.append((svcuser, groupuser))

    def add_user_to_group(self, svcuser, groupuserkey):
        self.added.append((svcuser, groupuserkey))

    def remove_user_from_group(self, groupuserkey):
        self.removed.append(groupuserkey)

    def finish_import(self):
        self.finished = True


def test_import_group_adds_service_user_missing_from_group(bareapp):
    mgr = _RecordingSyncManager(svcusers={'a': 'svc-a'}, groupusers={}, group_key_map={'svc-a': 'key-a'})
    with bareapp.app_context():
        mgr.import_group()
    assert mgr.added == [('svc-a', 'key-a')]
    assert mgr.updated == []
    assert mgr.removed == []


def test_import_group_updates_user_already_in_group(bareapp):
    mgr = _RecordingSyncManager(svcusers={'a': 'svc-a'}, groupusers={'key-a': 'group-a'},
                                group_key_map={'svc-a': 'key-a'})
    with bareapp.app_context():
        mgr.import_group()
    assert mgr.updated == [('svc-a', 'group-a')]
    assert mgr.added == []
    assert mgr.removed == []


def test_import_group_removes_group_user_no_longer_in_service(bareapp):
    mgr = _RecordingSyncManager(svcusers={}, groupusers={'key-x': 'group-x'}, group_key_map={})
    with bareapp.app_context():
        mgr.import_group()
    assert mgr.removed == ['key-x']
    assert mgr.added == []
    assert mgr.updated == []


def test_import_group_calls_start_and_finish(bareapp):
    mgr = _RecordingSyncManager(svcusers={}, groupusers={}, group_key_map={})
    with bareapp.app_context():
        mgr.import_group()
    assert mgr.started is True
    assert mgr.finished is True


def test_import_group_debug_sets_logger_debug_level(bareapp):
    mgr = _RecordingSyncManager(svcusers={}, groupusers={}, group_key_map={})
    with bareapp.app_context():
        mgr.import_group(debug=True)
    assert bareapp.logger.level == logging.DEBUG


def test_import_group_no_debug_sets_logger_warning_level(bareapp):
    mgr = _RecordingSyncManager(svcusers={}, groupusers={}, group_key_map={})
    with bareapp.app_context():
        mgr.import_group(debug=False)
    assert bareapp.logger.level == logging.WARNING
