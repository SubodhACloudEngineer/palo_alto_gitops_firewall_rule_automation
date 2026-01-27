#!/bin/bash

#############################################
# VM1 Monitoring Script
# Palo Alto GitOps Demo
#
# Purpose: Continuously monitor access to VM2
# Shows: ❌ BLOCKED → ✅ SUCCESS transition
#
# Usage: ./monitor_vm2_access.sh
#############################################

# Configuration
TARGET_IP="172.19.2.5"
TARGET_URL="http://${TARGET_IP}"
COUNTER=0
SUCCESS_COUNT=0
FAIL_COUNT=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
clear
echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}    Palo Alto Firewall Demo - VM2 Access Monitor${NC}"
echo -e "${CYAN}================================================================${NC}"
echo ""
echo -e "${YELLOW}Source:${NC}      VM1 (user01workstation) - 172.19.1.5"
echo -e "${YELLOW}Target:${NC}      VM2 (web01application) - ${TARGET_IP}"
echo -e "${YELLOW}Protocol:${NC}    HTTP"
echo ""
echo -e "${CYAN}================================================================${NC}"
echo -e "${PURPLE}Starting continuous access monitoring...${NC}"
echo -e "${CYAN}================================================================${NC}"
echo ""
echo -e "${YELLOW}Instructions:${NC}"
echo -e "  - Initially, you should see ❌ BLOCKED status"
echo -e "  - After GitOps pipeline deploys the rule, status changes to ✅ SUCCESS"
echo -e "  - Press Ctrl+C to stop monitoring"
echo ""
echo -e "${CYAN}================================================================${NC}"
echo ""

# Function to display stats
display_stats() {
    local total=$((SUCCESS_COUNT + FAIL_COUNT))
    if [ $total -gt 0 ]; then
        local success_rate=$(awk "BEGIN {printf \"%.1f\", ($SUCCESS_COUNT / $total) * 100}")
        echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${PURPLE}Statistics:${NC} Total: $total | ✅ Success: $SUCCESS_COUNT | ❌ Failed: $FAIL_COUNT | Rate: ${success_rate}%"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    fi
}

# Trap Ctrl+C for clean exit
trap 'echo -e "\n\n${YELLOW}Monitoring stopped.${NC}"; display_stats; exit 0' INT

# Main monitoring loop
while true; do
    COUNTER=$((COUNTER + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Try to access the web server
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 ${TARGET_URL} 2>&1)
    
    # Check response
    if [ "$RESPONSE" == "200" ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo -e "[${TIMESTAMP}] ${GREEN}Attempt #${COUNTER}:${NC} ${GREEN}✅ SUCCESS${NC} - HTTP 200 OK"
        echo -e "                        ${GREEN}🎉 FIREWALL RULE IS ACTIVE! VM1 → VM2 connection allowed${NC}"
        
        # Play system beep if available
        echo -e "\a" 2>/dev/null
        
        # Show celebration message on first success
        if [ $SUCCESS_COUNT -eq 1 ]; then
            echo ""
            echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
            echo -e "${GREEN}║                                                               ║${NC}"
            echo -e "${GREEN}║       🎊 BREAKTHROUGH! Firewall Rule Deployed! 🎊            ║${NC}"
            echo -e "${GREEN}║                                                               ║${NC}"
            echo -e "${GREEN}║  GitOps pipeline has successfully deployed the allow rule    ║${NC}"
            echo -e "${GREEN}║  Traffic from VM1 to VM2 is now permitted                    ║${NC}"
            echo -e "${GREEN}║                                                               ║${NC}"
            echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
            echo ""
        fi
        
    elif [ "$RESPONSE" == "000" ]; then
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo -e "[${TIMESTAMP}] ${RED}Attempt #${COUNTER}:${NC} ${RED}❌ BLOCKED${NC} - Connection refused/timeout"
        echo -e "                        ${YELLOW}⏳ Waiting for firewall rule deployment...${NC}"
        
    elif [ "$RESPONSE" == "404" ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo -e "[${TIMESTAMP}] ${YELLOW}Attempt #${COUNTER}:${NC} ${GREEN}✅ CONNECTED${NC} - HTTP 404 (server reachable, page not found)"
        
    elif [ "$RESPONSE" == "403" ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo -e "[${TIMESTAMP}] ${YELLOW}Attempt #${COUNTER}:${NC} ${GREEN}✅ CONNECTED${NC} - HTTP 403 (server reachable, access forbidden)"
        
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo -e "[${TIMESTAMP}] ${YELLOW}Attempt #${COUNTER}:${NC} ${YELLOW}⚠️  HTTP ${RESPONSE}${NC} - Unexpected response"
    fi
    
    # Show stats every 20 attempts
    if [ $((COUNTER % 20)) -eq 0 ]; then
        display_stats
    fi
    
    # Wait before next attempt
    sleep 5
done
