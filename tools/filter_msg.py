#!/usr/bin/env python3
import sys
import re

msg = sys.stdin.read()
# Remove any line containing Claude Code or Co-Authored-By Claude
lines = msg.split('\n')
filtered_lines = []
for line in lines:
    if 'Generated with [Claude Code]' in line:
        continue
    if 'Co-Authored-By: Claude' in line:
        continue
    filtered_lines.append(line)
# Remove trailing empty lines but keep one newline at end
msg = '\n'.join(filtered_lines).rstrip() + '\n'
sys.stdout.write(msg)
