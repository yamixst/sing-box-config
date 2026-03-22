#!/bin/bash

cd config

for f in *.json
do
	sing-box format -w -c $f
done
