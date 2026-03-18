#!/bin/bash
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "❌ Server not running"
