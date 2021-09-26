#!/bin/bash

SCRIPT_PATH=$(dirname $(readlink -f $0))

IFS=$'\n' b2_key=($(cat $SCRIPT_PATH/.key-b2))

export B2_ACCOUNT_ID=${b2_key[0]}
export B2_ACCOUNT_KEY=${b2_key[1]}
