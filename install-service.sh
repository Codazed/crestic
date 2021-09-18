#!/bin/bash
# Please run this from the entry which you want to install the service for

SCRIPT_PATH=$(dirname $(readlink -f $0))

ENTRY=$(basename $(pwd))
TIMERVAL=$1

cat $SCRIPT_PATH/service-template | sed -e "s|%ENTRY%|$ENTRY|g" -e "s|%ROOTPATH%|$SCRIPT_PATH|g" > /etc/systemd/system/restic-$ENTRY.service
cat $SCRIPT_PATH/timer-template | sed -e "s|%ENTRY%|$ENTRY|g" -e "s|%ROOTPATH%|$SCRIPT_PATH|g" -e "s|%CALENDARENTRY%|$TIMERVAL|g" > /etc/systemd/system/restic-$ENTRY.timer

