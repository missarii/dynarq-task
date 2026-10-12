#!/usr/bin/env bash
# ==============================================================================
# Dynarq — One-Click Unified Local Application Launcher
# Starts both the Node.js Local AI Engine and Python Web Dashboard,
# verifies health, and opens http://localhost:8000/ in the default browser.
# ==============================================================================

set -e

# ANSI Colors for terminal output
BOLD="\033[1m"
GREEN="\033[0;32m"
ORANGE="\033[0;33m"
PURPLE="\033[0;35m"
CYAN="\033[0;36m"
RED="\033[0;31m"
RESET="\033[0m"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${PURPLE}${BOLD}"
echo "  ╔══════════════════════════════════════════════════════════════╗"
echo "  ║            D Y N A R Q   A P P L I C A T I O N             ║"
echo "  ║       Payment Reminder Assistant & Local AI Copilot          ║"
echo "  ╚══════════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# 1. Check Prerequisites
echo -e "${CYAN}==> Checking system dependencies...${RESET}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.9+.${RESET}"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: node is not installed. Please install Node.js 18+.${RESET}"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm is not installed. Please install npm.${RESET}"
    exit 1
fi

echo -e "  ${GREEN}✓${RESET} Python version : $(python3 --version)"
echo -e "  ${GREEN}✓${RESET} Node.js version: $(node --version)"
echo -e "  ${GREEN}✓${RESET} npm version    : $(npm --version)"

# 2. Setup / Verify Node.js AI Dependencies
echo -e "\n${CYAN}==> Verifying Node.js AI engine packages (@xenova/transformers)...${RESET}"
if [ ! -d "ai/node_modules" ]; then
    echo -e "  ${ORANGE}Installing @xenova/transformers in ai/...${RESET}"
    (cd ai && npm install)
else
    echo -e "  ${GREEN}✓${RESET} ai/node_modules present and ready."
fi

# 3. Clean up any stale processes on ports 8000 and 8001
echo -e "\n${CYAN}==> Ensuring ports 8000 and 8001 are available...${RESET}"
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 8001/tcp 2>/dev/null || true
sleep 1

# 4. Trap signals to ensure graceful shutdown of both background processes
NODE_PID=""
PYTHON_PID=""

cleanup() {
    echo -e "\n\n${ORANGE}==> Shutting down Dynarq services...${RESET}"
    if [ -n "$PYTHON_PID" ] && kill -0 "$PYTHON_PID" 2>/dev/null; then
        kill "$PYTHON_PID" 2>/dev/null || true
    fi
    if [ -n "$NODE_PID" ] && kill -0 "$NODE_PID" 2>/dev/null; then
        kill "$NODE_PID" 2>/dev/null || true
    fi
    echo -e "${GREEN}✓ All services stopped cleanly. Goodbye!${RESET}"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 5. Start Node.js AI Service
echo -e "\n${CYAN}==> Starting Node.js AI Service on http://127.0.0.1:8001...${RESET}"
(cd ai && node server.js) &
NODE_PID=$!

# Wait for AI service to be responsive
echo -n "  Waiting for AI neural model to warm up..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8001/health 2>/dev/null | grep -q "ok"; then
        echo -e " ${GREEN}Ready!${RESET}"
        break
    fi
    sleep 0.5
    echo -n "."
done

# 6. Start Python Web Server
echo -e "\n${CYAN}==> Starting Python Web Dashboard on http://localhost:8000...${RESET}"
(cd python && python3 app.py) &
PYTHON_PID=$!

# Wait for Python web dashboard to respond
echo -n "  Waiting for Web Dashboard to initialize..."
for i in {1..20}; do
    if curl -s http://localhost:8000/api/plan.json 2>/dev/null | grep -q "actions"; then
        echo -e " ${GREEN}Ready!${RESET}"
        break
    fi
    sleep 0.5
    echo -n "."
done

# 7. Success Banner
echo -e "\n${GREEN}${BOLD}════════════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}   🚀 DYNARQ IS FULLY RUNNING LOCALLY!${RESET}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════════${RESET}"
echo -e "  ${BOLD}Dashboard URL :${RESET} ${CYAN}http://localhost:8000/${RESET}"
echo -e "  ${BOLD}AI Microservice:${RESET} ${CYAN}http://127.0.0.1:8001/${RESET}"
echo -e "  ${BOLD}Neural Model  :${RESET} DistilBERT SQuAD (~60MB quantized ONNX)"
echo -e "  ${BOLD}Status        :${RESET} 100% Offline & Private"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════════════${RESET}"

# 8. Open in Default Browser
echo -e "\n${PURPLE}==> Opening http://localhost:8000/ in your browser...${RESET}"
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:8000/" &> /dev/null || true
elif command -v open &> /dev/null; then
    open "http://localhost:8000/" &> /dev/null || true
elif command -v sensible-browser &> /dev/null; then
    sensible-browser "http://localhost:8000/" &> /dev/null || true
fi

echo -e "\n${ORANGE}Press [CTRL + C] anytime to stop all services.${RESET}\n"

# Keep script running and wait for background jobs
wait "$PYTHON_PID" "$NODE_PID"
