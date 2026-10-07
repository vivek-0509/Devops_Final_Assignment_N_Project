#!/bin/bash
# ------------------------------------------------------------
# system_info.sh - System Information Script
# Session 3: Shell Scripting Homework
# Author: Vivek Singh Solanki (Roll No: 24bcs10338)
# ------------------------------------------------------------

# ---- Variables (store data to use later) ----
CURRENT_DATE=$(date)
HOST_NAME=$(hostname)
USER_NAME=$(whoami)
DISK_USAGE=$(df -h)
PROCESS_COUNT=$(ps -e | wc -l | tr -d ' ')

echo "=============================================="
echo "        SYSTEM INFORMATION REPORT"
echo "=============================================="
echo "Current Date  : $CURRENT_DATE"
echo "Hostname      : $HOST_NAME"
echo "Username      : $USER_NAME"
echo "----------------------------------------------"
echo "Disk Usage (df -h):"
echo "$DISK_USAGE"
echo "----------------------------------------------"
echo "Running Processes (first 10 by PID, total: $PROCESS_COUNT):"
ps -eo pid,user,%cpu,%mem,comm | head -n 11
echo "=============================================="

# ---- Take user input using read -p ----
read -p "Enter your name: " NAME
read -p "Enter your roll number: " ROLL_NO
read -p "Enter a directory name to create: " DIR_NAME

echo "----------------------------------------------"
echo "Hello $NAME (Roll No: $ROLL_NO)!"

# ---- Create a directory using mkdir ----
mkdir -p "$DIR_NAME"
echo "Directory '$DIR_NAME' created using mkdir."

# ---- Create a file using touch ----
LOG_FILE="$DIR_NAME/process.log"
touch "$LOG_FILE"
echo "File '$LOG_FILE' created using touch."

# ---- Store running process info in the file using > redirection ----
ps -eo pid,user,%cpu,%mem,start,time,comm > "$LOG_FILE"
echo "Running process information saved to '$LOG_FILE' using > redirection."

echo "----------------------------------------------"
echo "Preview of $LOG_FILE (first 5 lines):"
head -n 5 "$LOG_FILE"
echo "Total lines in $LOG_FILE: $(wc -l < "$LOG_FILE" | tr -d ' ')"
echo "=============================================="
echo "Script finished successfully."
