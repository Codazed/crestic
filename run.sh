#!/bin/bash

SCRIPT_DIR=$(dirname $(readlink -f $0))
ENTRY_DIR=$SCRIPT_DIR/entries/$1

pushd $ENTRY_DIR > /dev/null
	$SCRIPT_DIR/backup.sh "$(cat bucket)" "$(basename $(pwd))" "$(readlink -f password)" "$(cat include)" "$(readlink -f exclude)" "$(cat policy)"
	popd > /dev/null
