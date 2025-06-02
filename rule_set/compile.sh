#!/bin/sh

for f in *.json
do
	echo "Compile $f"
	sing-box rule-set compile $f
done
