#!/bin/bash

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

. $SCRIPT_DIR/setup.sh

REPO_LOC=$1
ENTRY=$2
PASSWORD=$3
DIR_TO_BACKUP=$4
EXCLUDE_LIST=$5
IFS=' ' POLICY=($6)

LOCKFILE_DIR=/run/resticsh

mkdir -p $LOCKFILE_DIR
chown -R root:root $LOCKFILE_DIR
chmod 600 $LOCKFILE_DIR

if [[ -f "$LOCKFILE_DIR/$ENTRY" ]]; then
	echo "Restic already running for $ENTRY with PID $(cat $LOCKFILE_DIR/$ENTRY)"
	exit 1
fi

export RESTIC_CACHE_DIR=$SCRIPT_DIR/.cache
export RESTIC_REPOSITORY="$REPO_LOC"
export RESTIC_PASSWORD_FILE=$PASSWORD

echo $$ > $LOCKFILE_DIR/$ENTRY

echo "#####################################"
echo "Begin backup of $ENTRY"
echo "#####################################"
restic --verbose backup --one-file-system --iexclude-file $EXCLUDE_LIST $DIR_TO_BACKUP

echo "#####################################"
echo "Begin cleanup of $ENTRY"
echo "#####################################"
restic forget ${POLICY[@]} --prune

echo "#####################################"
echo "Backup of $ENTRY complete!"
echo "#####################################"

rm -f $LOCKFILE_DIR/$ENTRY

