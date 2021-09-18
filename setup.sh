#!/bin/bash

SCRIPT_PATH=$(dirname $(readlink -f $0))

IFS=$'\n' key=($(cat $SCRIPT_PATH/key))

export B2_ACCOUNT_ID=${key[0]}
export B2_ACCOUNT_KEY=${key[1]}
