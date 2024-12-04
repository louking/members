###########################################################################################
# fabfile  -- deployment using Fabric
#
#   Copyright 2019 Lou King
###########################################################################################
'''
fabfile  -- deployment using Fabric
=================================================================

expecting fabric.json with following content
    {
        "connect_kwargs": {
            "key_filename": sshkeyfilename (export OpenSSH key from puttygen)
        },
        "user": "membersmgr"
    }

execute as follows

    fab -H <target-host> deploy

or 

    fab -H <target1>,<target2> deploy

if you need to check out a particular branch

    fab -H <target-host> deploy --branchname=<branch>

'''

from fabric import task
from invoke import Exit

APP_NAME = 'members'
DOCKER_NAME = 'members'

qualifiers = ['prod', 'sandbox']

@task
def deploy(c, qualifier, branchname='master'):
    if qualifier not in qualifiers:
        raise Exit(f'deploy qualifier parameter must be one of {qualifiers}')
        
    print(f'c.user={c.user} c.host={c.host} branchname={branchname}')

    project_dir = f'~/{DOCKER_NAME}-{qualifier}'

    for the_file in ['docker-compose.yml']:
        if not c.run(f"cd {project_dir} && curl --fail -O 'https://raw.githubusercontent.com/louking/{APP_NAME}/{branchname}/{the_file}'", warn=True):
            raise Exit(f'louking/{APP_NAME}/{branchname}/{the_file} does not exist')

    # stop and build/start docker services
    c.run(f'cd {project_dir} && docker compose down')
    c.run(f'cd {project_dir} && docker compose up -d')
