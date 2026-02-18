#!/bin/bash
# load-env.sh - Load environment variables from .env file
# Usage: source ./load-env.sh

if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    set -a
    source .env
    set +a
    echo "✅ Environment variables loaded successfully"
else
    echo "❌ .env file not found. Please copy .env.example to .env and fill in your API keys."
    echo "   cp .env.example .env"
    exit 1
fi
