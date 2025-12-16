"""helper functions for managing user groups
"""
# pypi
from flask import current_app

from logging import DEBUG, WARNING

class SyncManager(object):
    def __init__(self):
        pass
    
    def start_import(self):
        """initialize import process"""
        pass
    
    def get_users_from_service(self):
        """get users from some service to import to internal group
        
        :rtype: dict of service user records"""
        return {svcuserkey: {} for svcuserkey in []}
    
    def get_users_from_group(self):
        """get users from internal group
        
        :rtype: dict of group user records
        """
        return {groupuserkey: {} for groupuserkey in []}
    
    def get_group_key_from_service_user(self, svcuser):
        """get unique key for service user in internal group
        
        :param svcuser: service user record
        :rtype: unique key for user in group
        """
        return None
    
    def check_update_user_in_group(self, svcuser, groupuser):
        """update user in internal group, if needed
        
        instantiate any changes required to keep groupuser in sync with svcuser
        """
        pass
    
    def add_user_to_group(self, svcuser, groupuserkey):
        """add svcuser to internal group
        
        :param groupuserkey: unique key for user in group"""
        pass
    
    def remove_user_from_group(self, groupuserkey):
        """remove user from internal group
        
        :param groupuserkey: unique key for user in group
        """
        pass
    
    def finish_import(self):
        """finalize import process"""
        pass
    
    def import_group(self, debug=False, debugrequests=False):
        """import users from some service to internal group"""

        # set up logging
        thislogger = current_app.logger
        thislogger.propagate = True
        if debug:
            # set up debug logging
            thislogger.setLevel(DEBUG)
        else:
            # WARNING logging
            thislogger.setLevel(WARNING)
        if debugrequests:
            # set up requests debug logging
            import logging
            logging.getLogger("requests").setLevel(DEBUG)
            logging.getLogger("urllib3").setLevel(DEBUG)
            logging.basicConfig()     
        
        # do any initialization the import requires
        self.start_import()
        
        # download member list from external service and current group members
        svcusers = self.get_users_from_service()
        groupusers = self.get_users_from_group()
        
        # loop through service members
        for svcuserkey in svcusers:
            svcuser = svcusers[svcuserkey]
            groupuserkey = self.get_group_key_from_service_user(svcuser)

            # if svc user is in the group
            if groupuserkey in groupusers:
                groupuser = groupusers.pop(groupuserkey)
                
                # check if any changes are required, and make them if needed
                self.check_update_user_in_group(svcuser, groupuser)
                
            # if club member is missing from the internal group
            else:
                self.add_user_to_group(svcuser, groupuserkey)

        # at this point, groupusers have only those users who are not in svcusers
        # loop through each of these and remove from the group
        for groupuserkey in groupusers:
            self.remove_user_from_group(groupuserkey)
            
        # finalize the import process
        self.finish_import()

