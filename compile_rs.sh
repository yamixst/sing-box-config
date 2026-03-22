#!/bin/sh

cd rule_set

for f in *.json
do
	echo "Compile $f"
	sing-box rule-set format -w $f
done

mkdir -p ./srs

for f in *.json
do
	echo "Compile $f"
	sing-box rule-set compile $f -o "./srs/${f%.json}.srs"
done
