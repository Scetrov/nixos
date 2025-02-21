#!/bin/bash

set -e

ansible-playbook -i src/inventory.yml src/playbook.yml