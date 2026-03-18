#!/bin/bash
cd "$(dirname "$0")/.."
if [ -f axon.pid ]; then
    kill $(cat axon.pid) && rm axon.pid
    echo "🛑 AXON Protocol stopped"
else
    echo "No PID file found"
fi
