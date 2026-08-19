#!/bin/sh

cd /uis/website && npm run dev -- -H 0.0.0.0 -p 3000 &
cd /uis/backoffice && npm run dev -- -H 0.0.0.0 -p 3001 &

wait