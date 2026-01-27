#!/bin/bash

##############################################
# VM1 Setup Script
# Palo Alto GitOps Demo
#
# Purpose: Setup VM1 with monitoring script
#          and required tools
#
# Usage: Run this on VM1 (user01workstation)
##############################################

echo "================================================"
echo "  VM1 Setup for Palo Alto GitOps Demo"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Update package list
echo -e "${YELLOW}Updating package list...${NC}"
sudo apt-get update

# Install required tools
echo -e "${YELLOW}Installing required tools...${NC}"
sudo apt-get install -y curl wget netcat-openbsd dnsutils traceroute jq

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Tools installed successfully${NC}"
else
    echo -e "${RED}❌ Failed to install tools${NC}"
    exit 1
fi

# Create demo directory
echo -e "${YELLOW}Creating demo directory...${NC}"
mkdir -p ~/palo-demo
cd ~/palo-demo

# Download monitoring script
echo -e "${YELLOW}Creating monitoring script...${NC}"
cat > ~/palo-demo/monitor_vm2_access.sh << 'EOF'
#!/bin/bash

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
NC='\033[0m'

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

# Trap Ctrl+C
trap 'echo -e "\n\n${YELLOW}Monitoring stopped.${NC}"; display_stats; exit 0' INT

# Main loop
while true; do
    COUNTER=$((COUNTER + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 ${TARGET_URL} 2>&1)
    
    if [ "$RESPONSE" == "200" ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo -e "[${TIMESTAMP}] ${GREEN}Attempt #${COUNTER}:${NC} ${GREEN}✅ SUCCESS${NC} - HTTP 200 OK"
        echo -e "                        ${GREEN}🎉 FIREWALL RULE IS ACTIVE! VM1 → VM2 connection allowed${NC}"
        
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
        
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo -e "[${TIMESTAMP}] ${YELLOW}Attempt #${COUNTER}:${NC} ${YELLOW}⚠️  HTTP ${RESPONSE}${NC}"
    fi
    
    if [ $((COUNTER % 20)) -eq 0 ]; then
        display_stats
    fi
    
    sleep 5
done
EOF

chmod +x ~/palo-demo/monitor_vm2_access.sh

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Monitoring script created${NC}"
else
    echo -e "${RED}❌ Failed to create monitoring script${NC}"
    exit 1
fi

# Create quick test script
echo -e "${YELLOW}Creating quick test script...${NC}"
cat > ~/palo-demo/quick_test.sh << 'EOF'
#!/bin/bash

echo "Quick connectivity test to VM2..."
echo ""
echo "Target: 172.19.2.5 (web01application)"
echo ""

echo "1. Ping test:"
ping -c 3 172.19.2.5

echo ""
echo "2. HTTP test:"
curl -v --connect-timeout 5 http://172.19.2.5

echo ""
echo "3. Port scan:"
nc -zv 172.19.2.5 80

echo ""
echo "Test complete!"
EOF

chmod +x ~/palo-demo/quick_test.sh

# Create info file
cat > ~/palo-demo/README.txt << 'EOF'
Palo Alto GitOps Demo - VM1 Scripts
====================================

This directory contains scripts for the Palo Alto firewall automation demo.

Scripts:
--------
1. monitor_vm2_access.sh - Main monitoring script
   - Shows real-time access attempts to VM2
   - Displays BLOCKED → SUCCESS transition during demo
   - Usage: ./monitor_vm2_access.sh

2. quick_test.sh - Quick connectivity test
   - Tests ping, HTTP, and port connectivity to VM2
   - Usage: ./quick_test.sh

Demo Instructions:
------------------
1. Start monitoring: ./monitor_vm2_access.sh
2. Initially shows: ❌ BLOCKED
3. After GitOps deployment: ✅ SUCCESS
4. Press Ctrl+C to stop

Network Information:
--------------------
VM1 (This machine): 172.19.1.5 (user01workstation)
VM2 (Target): 172.19.2.5 (web01application)
Firewall Trust: 172.19.1.4
Firewall DMZ: 172.19.2.4

Firewall Zones:
---------------
VM1 subnet → trust zone
VM2 subnet → dmz zone

For more information, see the main demo guide.
EOF

# Verify VM information
echo ""
echo -e "${YELLOW}Verifying VM configuration...${NC}"
echo ""
echo "Hostname: $(hostname)"
echo "Private IP: $(hostname -I | awk '{print $1}')"
echo "Expected IP: 172.19.1.5"
echo ""

# Test connectivity to firewall
echo -e "${YELLOW}Testing connectivity to firewall...${NC}"
FIREWALL_TRUST="172.19.1.4"
ping -c 2 $FIREWALL_TRUST > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Can reach firewall trust interface ($FIREWALL_TRUST)${NC}"
else
    echo -e "${RED}❌ Cannot reach firewall trust interface ($FIREWALL_TRUST)${NC}"
fi

# Test connectivity to VM2 (should fail initially)
echo -e "${YELLOW}Testing connectivity to VM2...${NC}"
VM2_IP="172.19.2.5"
timeout 5 curl -s http://$VM2_IP > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Can reach VM2 ($VM2_IP) - Rule already deployed?${NC}"
else
    echo -e "${YELLOW}❌ Cannot reach VM2 ($VM2_IP) - This is expected (blocked by firewall)${NC}"
fi

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✅ VM1 Setup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Demo scripts are ready in: ~/palo-demo/"
echo ""
echo "To start monitoring:"
echo "  cd ~/palo-demo"
echo "  ./monitor_vm2_access.sh"
echo ""
echo "For quick test:"
echo "  ./quick_test.sh"
echo ""
echo "To view instructions:"
echo "  cat README.txt"
echo ""
echo -e "${YELLOW}IMPORTANT: Run the monitoring script BEFORE starting the GitOps demo!${NC}"
echo ""
