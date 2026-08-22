#!/bin/bash

source ./app-initdb.d/sql-commands.sh

# NOTE: file end of line characters must be LF, not CRLF (see https://stackoverflow.com/a/58220487/799921)

# create database if necessary
while ! ./app-initdb.d/create-database.sh
do
    sleep 5
done

# look for sql file, should only be one, delete after loading sql into database
files=(/initdb.d/${APP_DATABASE}-*.sql)
if [ -f "$files" ] && ((${#files[@]}==1)); then
    mysql_note "loading database dump ${files[0]}"
    docker_process_sql --database=${APP_DATABASE} <$files
    rm $files
    mysql_note "database dump loaded"

    # this environment is not production if either override key is set -- sanitize
    # GSuite report file/folder ids so a report generated here can never write into
    # the real production Google Docs the dump was copied from (see #717)
    override_folder="${OVERRIDE_DEV_REPORTS_FOLDER:-$OVERRIDE_SANDBOX_REPORTS_FOLDER}"
    if [ -n "$override_folder" ]; then
        mysql_note "sanitizing GSuite report file/folder ids for non-production environment (folder=${override_folder})"
        docker_process_sql --database=${APP_DATABASE} <<-EOSQL
			UPDATE meeting SET gs_status = NULL, gs_agenda = NULL, gs_minutes = NULL;
			UPDATE localinterest SET gs_status_fdr = '${override_folder}', gs_agenda_fdr = '${override_folder}', gs_minutes_fdr = '${override_folder}';
		EOSQL
        mysql_note "GSuite report file/folder ids sanitized"
    else
        mysql_note "OVERRIDE_DEV_REPORTS_FOLDER/OVERRIDE_SANDBOX_REPORTS_FOLDER not set, skipping GSuite report sanitize"
    fi
else
    mysql_note "no database dump found in /initdb.d, skipping load and GSuite report sanitize"
fi

flask db upgrade

exec "$@"
