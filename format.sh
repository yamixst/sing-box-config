#!/bin/bash

for f in *.json; do sing-box format -w -c $f; done
