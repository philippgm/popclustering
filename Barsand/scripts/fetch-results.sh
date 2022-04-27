#!/bin/bash
rm -rf results
mkdir results

for msm_id in `cat *-msm-ids.txt`
do
   wget https://atlas.ripe.net/api/v2/measurements/$msm_id/results -O results/$msm_id.json
done

cat results/* | sed 's/\]\[/,/g' > ripe-results.json
