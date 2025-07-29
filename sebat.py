#!/usr/bin/env python3

import subprocess
import threading
import argparse
import time
import yaml
from pathlib import Path
import os
from datetime import datetime
import sys
import platform
from queue import Queue, Empty
import re
import random
import string

statuses = {}
resolved_paths_cache = {}

lock = threading.Lock()

# Global verbose logging
verbose_log_file = None
verbose_enabled = False
progress_lines_count = 0
scan_id = None  # Global scan ID for the current session

def generate_scan_id():
    """Generate a unique scan ID with 4-8 digit number"""
    # Generate a random number between 1000 and 99999999 (4-8 digits)
    scan_number = random.randint(1000, 99999999)
    return str(scan_number)

def get_scan_id():
    """Get the current scan ID, generate if not exists"""
    global scan_id
    if scan_id is None:
        scan_id = generate_scan_id()
    return scan_id

def format_file_size(size_bytes):
    """Format file size in human readable format (B, KB, MB, GB)"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def show_logs_realtime(scan_id_filter=None):
    debug_dir = Path("debug")
    if not debug_dir.exists():
        print("[ERROR] No debug directory found! Run a scan first to generate logs.")
        return
    
    # Look for the single log file
    log_filename = "sebatch_verbose.log"
    log_path = debug_dir / log_filename
    
    if not log_path.exists():
        print(f"[ERROR] No log file found! Run a scan first to generate logs.")
        print(f"[INFO] Expected log file: {log_filename}")
        return
    
    if scan_id_filter and scan_id_filter != 'all':
        print(f"[INFO] Reading log file: {log_filename} (filtered for SID: {scan_id_filter})")
    else:
        print(f"[INFO] Reading log file: {log_filename} (all logs)")
    print("[INFO] Press Ctrl+C to stop reading logs")
    print("-" * 80)
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            # Read existing content
            content = f.read()
            if content:
                if scan_id_filter and scan_id_filter != 'all':
                    # Filter content by scan ID
                    lines = content.split('\n')
                    filtered_lines = []
                    for line in lines:
                        if f"[SID:{scan_id_filter}]" in line:
                            filtered_lines.append(line)
                    if filtered_lines:
                        print('\n'.join(filtered_lines))
                    else:
                        print(f"[WARNING] No logs found for SID: {scan_id_filter}")
                        return
                else:
                    print(content)
            
            # Follow new content in real-time
            while True:
                new_content = f.read()
                if new_content:
                    if scan_id_filter and scan_id_filter != 'all':
                        # Filter new content by scan ID
                        lines = new_content.split('\n')
                        filtered_lines = []
                        for line in lines:
                            if f"[SID:{scan_id_filter}]" in line:
                                filtered_lines.append(line)
                        if filtered_lines:
                            print('\n'.join(filtered_lines))
                    else:
                        print(new_content, end='')
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[INFO] Log reading stopped")
    except Exception as e:
        print(f"[ERROR] Error reading log file: {e}")

def verbose_log(message, workflow_name=None):
    global verbose_log_file, verbose_enabled
    
    if not verbose_enabled:
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_scan_id = get_scan_id()
    scan_id_prefix = f"[SID:{current_scan_id}] "
    workflow_prefix = f"[{workflow_name}] " if workflow_name else ""
    log_message = f"[{timestamp}] {scan_id_prefix}{workflow_prefix}{message}"
    
    # Write to log file
    if verbose_log_file:
        try:
            verbose_log_file.write(log_message + "\n")
            verbose_log_file.flush()  
        except Exception as e:
            print(f"Warning: Could not write to verbose log: {e}")

def list_log_files():
    debug_dir = Path("debug")
    if not debug_dir.exists():
        print("[INFO] No debug directory found. No logs available.")
        return
    
    # Look for the single log file
    log_filename = "sebatch_verbose.log"
    log_path = debug_dir / log_filename
    
    if not log_path.exists():
        print("[INFO] No log file found.")
        return
    
    print("\n[INFO] Log File Status:")
    print("=" * 80)
    
    mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
    size = log_path.stat().st_size
    size_str = format_file_size(size)
    
    print(f"File: {log_filename}")
    print(f"[TIME] Last Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[SIZE] Size: {size_str}")
    
    # Extract and display scan IDs from this file
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            scan_ids = set()
            for line in content.split('\n'):
                if '[SID:' in line:
                    # Extract scan ID from line
                    start = line.find('[SID:') + 5
                    end = line.find(']', start)
                    if start > 4 and end > start:
                        scan_id = line[start:end]
                        scan_ids.add(scan_id)
            
            if scan_ids:
                print(f"[SCANS] Contains {len(scan_ids)} scan(s): {', '.join(sorted(scan_ids, reverse=True))}")
            else:
                print(f"[SCANS] No scan IDs found")
    except Exception as e:
        print(f"[WARNING] Could not read file: {e}")
    
    # Show recommendations
    if size > 100 * 1024 * 1024:  # > 100 MB
        print(f"\n[WARNING] Log file is getting large ({size_str})")
        print("[TIP] Consider clearing logs with: python sebat.py -cl")
    elif size > 50 * 1024 * 1024:  # > 50 MB
        print(f"\n[INFO] Log file size: {size_str}")
        print("[TIP] Use 'python sebat.py -cl' to clear logs when needed")
    else:
        print(f"\n[INFO] Log file size: {size_str} - OK")
    
        print("\n[TIP] Use 'python sebat.py -v' to read all logs")
    print("[TIP] Use 'python sebat.py -v SID' to read specific scan logs")
    print("[TIP] Use 'python sebat.py -cl' to clear all log files")

def clear_logs():
    debug_dir = Path("debug")
    if not debug_dir.exists():
        print("[INFO] No debug directory found. Nothing to clear.")
        return
    
    log_filename = "sebatch_verbose.log"
    log_path = debug_dir / log_filename
    
    if not log_path.exists():
        print("[INFO] No log file found. Nothing to clear.")
        return
    
    # Calculate size before clearing
    size = log_path.stat().st_size
    size_str = format_file_size(size)
    
    print(f"[INFO] Found log file with size: {size_str}")
    print("[INFO] Clearing log file...")
    
    try:
        log_path.unlink()
        print(f"[SUCCESS] Cleared log file ({size_str} freed)")
        print("[INFO] New scans will create fresh log file")
    except Exception as e:
        print(f"[WARNING] Could not delete {log_filename}: {e}")

def setup_verbose_logging():
    global verbose_log_file, verbose_enabled
    
    if not verbose_enabled:
        return
    
    # Create debug folder if it doesn't exist
    debug_dir = Path("debug")
    debug_dir.mkdir(exist_ok=True)
    
    # Use single log file - APPEND mode
    log_filename = "debug/sebatch_verbose.log"
    
    try:
        # Use append mode ('a') instead of write mode ('w')
        verbose_log_file = open(log_filename, 'a', encoding='utf-8')
        verbose_log(f"Verbose logging started - Log file: {log_filename}")
    except Exception as e:
        print(f"Warning: Could not create verbose log file: {e}")
        verbose_log_file = None

def cleanup_verbose_logging():
    global verbose_log_file
    if verbose_log_file:
        try:
            verbose_log_file.close()
        except Exception as e:
            print(f"Warning: Could not close verbose log file: {e}")
        verbose_log_file = None

def log_status(domain, step, status):
    with lock:
        key = f"{domain}::{step}"
        statuses[key] = status

def print_status(domains, steps, scan_name):
    with lock:
        # Always clear screen for clean progress display
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Print progress at the top with scan ID
        current_scan_id = get_scan_id()
        print(f"Scan Progress ({scan_name}) [SID:{current_scan_id}]:\n")

        for domainx in domains:
            domain = check_cidr(domainx)
            line = f"{domain:25} |"
            for i, step in enumerate(steps):
                key = f"{domain}::{step['name']}"
                stat = statuses.get(key, "waiting...")
                
                # Format status for display
                if stat == "waiting...":
                    status_display = "WAIT..."
                elif stat == "running":
                    status_display = "RUN.."
                elif stat == "done":
                    status_display = "DONE"
                elif stat == "skipped":
                    status_display = "SKIP"
                else:
                    status_display = stat.upper()
                
                # Add step with status
                line += f" {step['name']}({status_display})"
                
                # Add arrow if not the last step
                if i < len(steps) - 1:
                    # Show ---> only if the NEXT step is running, otherwise just ---
                    next_step = steps[i + 1]
                    next_key = f"{domain}::{next_step['name']}"
                    next_stat = statuses.get(next_key, "waiting...")
                    
                    if next_stat == "running":
                        line += " --->"
                    else:
                        line += " ---"
            
            print(line)

        waiting_count = sum(1 for s in statuses.values() if s == "waiting...")
        done_count = sum(1 for s in statuses.values() if s == "done" or s == "skipped")
        print(f"\n[WAITING: {waiting_count}] [DONE: {done_count}]\n")

def print_all_workflows_status(workflow_configs, current_domains):
    with lock:
        # Always clear screen for clean progress display
        os.system('cls' if os.name == 'nt' else 'clear')
        
        current_scan_id = get_scan_id()
        
        for config in workflow_configs:
            scan_name = config.get('name', 'Unknown Scan')
            pipeline = config['pipeline']
            
            print(f"Scan Progress ({scan_name}) [SID:{current_scan_id}]:\n")
            
            for domainx in current_domains:
                domain = check_cidr(domainx)
                line = f"{domain:25} |"
                for i, step in enumerate(pipeline):
                    key = f"{domain}::{step['name']}"
                    stat = statuses.get(key, "waiting...")
                    
                    # Format status for display
                    if stat == "waiting...":
                        status_display = "WAIT..."
                    elif stat == "running":
                        status_display = "RUN.."
                    elif stat == "done":
                        status_display = "DONE"
                    elif stat == "skipped":
                        status_display = "SKIP"
                    else:
                        status_display = stat.upper()
                    
                    # Add step with status
                    line += f" {step['name']}({status_display})"
                    
                    # Add arrow if not the last step
                    if i < len(pipeline) - 1:
                        # Show ---> only if the NEXT step is running, otherwise just ---
                        next_step = pipeline[i + 1]
                        next_key = f"{domain}::{next_step['name']}"
                        next_stat = statuses.get(next_key, "waiting...")
                        
                        if next_stat == "running":
                            line += " --->"
                        else:
                            line += " ---"
                
                print(line)
            
            # Count statuses for this workflow only
            workflow_waiting = 0
            workflow_done = 0
            for domainx in current_domains:
                domain = check_cidr(domainx)
                for step in pipeline:
                    key = f"{domain}::{step['name']}"
                    stat = statuses.get(key, "waiting...")
                    if stat == "waiting...":
                        workflow_waiting += 1
                    elif stat in ["done", "skipped"]:
                        workflow_done += 1
            
            print(f"\n[WAITING: {workflow_waiting}] [DONE: {workflow_done}]\n")
            print("-" * 80 + "\n")

def run_command(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def is_output_valid(output_path_template, domain):
    if output_path_template == "null":
        return False

    output_path = Path(output_path_template)

    if not output_path.exists():
        return False

    if output_path.is_dir():
        if not list(output_path.iterdir()):
            return False
    elif output_path.is_file():
        if output_path.stat().st_size == 0:
            return False

    return True

def check_cidr(target):
    if '/' in target:
        return target.replace('/', '-')  
    return target  

def get_output_path(domain, step, date_str):
    cat_base = (step.get("cat_base") or "").strip()
    step_name = step["name"]
    output_file = (step.get("output_file") or "").strip()
    
    parts = ["results-scan", domain]
    if cat_base:
        parts.append(cat_base)
    parts.append(step_name)
    dir_path = os.path.join(*parts)
    
    if output_file:
        file_name = f"scan-at-{date_str}-{output_file}"
    else:
        file_name = f"scan-at-{date_str}"
    
    return os.path.join(dir_path, file_name)

def is_any_result_exists(domain, step):
    cat_base = (step.get("cat_base") or "").strip()
    step_name = step["name"]
    parts = ["results-scan", domain]
    if cat_base:
        parts.append(cat_base)
    parts.append(step_name)
    dir_path = os.path.join(*parts)
    if not os.path.exists(dir_path):
        return False
    for fname in os.listdir(dir_path):
        if fname.startswith("scan-at-"):
            return True
    return False

def find_previous_scan_output(domain, step_name, date_str):
    """Find output file from previous scans when step is not in current workflow"""
    # Look for the step in results-scan directory
    results_dir = Path("results-scan")
    if not results_dir.exists():
        return None
    
    domain_dir = results_dir / domain
    if not domain_dir.exists():
        return None
    
    # Search recursively for the step name
    for category_dir in domain_dir.rglob("*"):
        if category_dir.is_dir() and category_dir.name == step_name:
            # Look for scan files in this directory
            scan_files = []
            for file_path in category_dir.iterdir():
                if file_path.is_file() and file_path.name.startswith("scan-at-"):
                    scan_files.append(file_path)
            
            if scan_files:
                # Check if it's from today or find the most recent
                today_files = [f for f in scan_files if date_str in f.name]
                if today_files:
                    # If multiple files today, return the first one (or could return all)
                    return str(today_files[0])
                else:
                    # If not today, find the most recent file
                    latest_file = max(scan_files, key=lambda x: x.stat().st_mtime)
                    return str(latest_file)
    
    return None

def find_previous_scan_outputs_with_prefix(domain, step_name, date_str):
    """Find all output files from previous scans that match a pattern (for wildcard cases)"""
    # Look for the step in results-scan directory
    results_dir = Path("results-scan")
    if not results_dir.exists():
        return []
    
    domain_dir = results_dir / domain
    if not domain_dir.exists():
        return []
    
    found_files = []
    
    # Search recursively for the step name
    for category_dir in domain_dir.rglob("*"):
        if category_dir.is_dir() and category_dir.name == step_name:
            # Look for scan files in this directory
            for file_path in category_dir.iterdir():
                if file_path.is_file() and file_path.name.startswith("scan-at-"):
                    # Check if it's from today or find the most recent
                    if date_str in file_path.name:
                        found_files.append(str(file_path))
                    else:
                        # If not today, include if it's the most recent
                        scan_files = [f for f in category_dir.iterdir() if f.is_file() and f.name.startswith("scan-at-")]
                        if scan_files:
                            latest_file = max(scan_files, key=lambda x: x.stat().st_mtime)
                            if str(latest_file) not in found_files:
                                found_files.append(str(latest_file))
    
    return found_files

def check_required_outputs_exist(domain, pipeline, selected_steps, date_str):
    """Check if all required output files exist for the selected steps"""
    missing_files = []
    required_steps = set()
    
    # Find all steps that the selected steps depend on
    for step_name in selected_steps:
        # Find the step in pipeline
        step_index = None
        for i, step in enumerate(pipeline):
            if step['name'] == step_name:
                step_index = i
                break
        
        if step_index is not None:
            step = pipeline[step_index]
            command = step['command']
            
            # Check for dependencies in the command
            step_references = re.findall(r'(\w+)\.output_file', command)
            for dep_step in step_references:
                if dep_step not in selected_steps:  # Only check non-selected dependencies
                    required_steps.add(dep_step)
    
    # Check if all required output files exist
    for step_name in required_steps:
        # Check if this step uses wildcard patterns in any command
        uses_wildcard = False
        for step in pipeline:
            if f"{step_name}.output_file*" in step['command']:
                uses_wildcard = True
                break
        
        if uses_wildcard:
            # Use the wildcard function to find all matching files
            output_files = find_previous_scan_outputs_with_prefix(domain, step_name, date_str)
            if not output_files:
                missing_files.append(f"{step_name} (wildcard)")
        else:
            # Use the regular function for single file
            output_path = find_previous_scan_output(domain, step_name, date_str)
            if not output_path:
                missing_files.append(step_name)
    
    return missing_files, list(required_steps)

def directory_exists_for_step(domain, step):
    """Check if the directory structure already exists for a step"""
    cat_base = (step.get("cat_base") or "").strip()
    step_name = step["name"]
    
    parts = ["results-scan", domain]
    if cat_base:
        parts.append(cat_base)
    parts.append(step_name)
    dir_path = os.path.join(*parts)
    
    return os.path.exists(dir_path)

def execute_step_group(domain, step_group, date_str, skip_if_any_result=True, workflow_name=None, rescan_steps=None, resolved_paths_cache=None):
    """Execute a group of steps (parallel if possible)"""
    firstdomain = domain
    domain = check_cidr(domain)
    
    if step_group['parallel'] and len(step_group['steps']) > 1:
        # Execute steps in parallel
        verbose_log(f"Executing {len(step_group['steps'])} steps in parallel for cat_base '{step_group['cat_base']}' on {domain}", workflow_name)
        
        def execute_single_step(step):
            return execute_single_step_logic(domain, step, date_str, skip_if_any_result, workflow_name, rescan_steps, resolved_paths_cache)
        
        # Create threads for parallel execution
        threads = []
        for step in step_group['steps']:
            t = threading.Thread(target=execute_single_step, args=(step,))
            t.start()
            threads.append(t)
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        verbose_log(f"Completed parallel execution of {len(step_group['steps'])} steps for {domain}", workflow_name)
    else:
        # Execute steps sequentially
        for step in step_group['steps']:
            execute_single_step_logic(domain, step, date_str, skip_if_any_result, workflow_name, rescan_steps, resolved_paths_cache)

def execute_single_step_logic(domain, step, date_str, skip_if_any_result=True, workflow_name=None, rescan_steps=None, resolved_paths_cache=None):
    """Execute a single step (extracted logic from scan_domain)"""
    firstdomain = domain
    domain = check_cidr(domain)
    
    if resolved_paths_cache is None:
        resolved_paths_cache = {}
    
    name = step["name"]
    actual_output_file_path = get_output_path(domain, step, date_str)
    resolved_paths_cache[domain][name] = actual_output_file_path

    cmd = step["command"]
    cmd = cmd.replace("{domain}", firstdomain)

    # Handle references to previous steps (this is simplified for parallel execution)
    # In parallel mode, we assume dependencies are handled by the grouping logic
    step_references = re.findall(r'(\w+)\.output_file', cmd)
    
    for step_name in step_references:
        placeholder = f"{step_name}.output_file"
        wildcard_placeholder = f"{step_name}.output_file*"
        
        if wildcard_placeholder in cmd:
            if step_name in resolved_paths_cache[domain] and resolved_paths_cache[domain][step_name]:
                resolved_output = resolved_paths_cache[domain][step_name]
                cmd = cmd.replace(wildcard_placeholder, resolved_output + "*")
                verbose_log(f"Replaced {wildcard_placeholder} with {resolved_output}* for {domain}", workflow_name)
            else:
                output_files = find_previous_scan_outputs_with_prefix(domain, step_name, date_str)
                if output_files:
                    file_pattern = " ".join(output_files)
                    cmd = cmd.replace(wildcard_placeholder, file_pattern)
                    verbose_log(f"Found previous scan outputs for {step_name}: {len(output_files)} files for {domain}", workflow_name)
                else:
                    verbose_log(f"Warning: Could not find output files for step '{step_name}' for domain {domain}", workflow_name)
        
        elif placeholder in cmd:
            if step_name in resolved_paths_cache[domain] and resolved_paths_cache[domain][step_name]:
                resolved_output = resolved_paths_cache[domain][step_name]
                cmd = cmd.replace(placeholder, resolved_output)
                verbose_log(f"Replaced {placeholder} with {resolved_output} for {domain}", workflow_name)
            else:
                previous_output = find_previous_scan_output(domain, step_name, date_str)
                if previous_output:
                    cmd = cmd.replace(placeholder, previous_output)
                    verbose_log(f"Found previous scan output for {step_name}: {previous_output} for {domain}", workflow_name)
                else:
                    verbose_log(f"Warning: Could not find output file for step '{step_name}' for domain {domain}", workflow_name)

    if actual_output_file_path:
        cmd = cmd.replace("{output_file}", actual_output_file_path)
        verbose_log(f"Output file path: {actual_output_file_path} for {domain}", workflow_name)

    # Determine if this step should be rescanned
    should_rescan = True  # Default to running the step
    
    if rescan_steps is not None:
        if rescan_steps is True:
            # Force rescan all steps
            should_rescan = True
            verbose_log(f"Step {name} will run for {domain} (force rescan all)", workflow_name)
        elif isinstance(rescan_steps, list):
            if name in rescan_steps:
                # This step is in the rescan list
                should_rescan = True
                verbose_log(f"Step {name} will run for {domain} (selected for rescan)", workflow_name)
            else:
                # This step is not in the rescan list, check if it has output
                this_step_has_output = is_any_result_exists(domain, step)
                if this_step_has_output:
                    should_rescan = False
                    verbose_log(f"Step {name} will be skipped for {domain} (output exists, not in rescan list)", workflow_name)
                else:
                    should_rescan = True
                    verbose_log(f"Step {name} will run for {domain} (no output exists, not in rescan list)", workflow_name)
    else:
        # Smart mode: check if output exists
        if skip_if_any_result and is_any_result_exists(domain, step):
            should_rescan = False
            verbose_log(f"Step {name} will be skipped for {domain} (output exists in smart mode)", workflow_name)
        else:
            should_rescan = True
            verbose_log(f"Step {name} will run for {domain} (no output exists in smart mode)", workflow_name)
    
    # If step should be skipped, mark it and return
    if not should_rescan:
        log_status(domain, name, "skipped")
        return

    # Create output directory
    if should_rescan and actual_output_file_path:
        if not directory_exists_for_step(domain, step):
            Path(os.path.dirname(actual_output_file_path)).mkdir(parents=True, exist_ok=True)
            verbose_log(f"Created output directory for {name} on {domain}", workflow_name)
        else:
            verbose_log(f"Output directory already exists for {name} on {domain}", workflow_name)

    log_status(domain, name, "running")
    verbose_log(f"Executing step {name} for {domain}: {cmd}", workflow_name)

    result = run_command(cmd)
    
    # Log command output
    if result.stdout:
        verbose_log(f"Command output for {name} on {domain}: {result.stdout}", workflow_name)
        print(f"\n[OUTPUT] {name} on {domain}:")
        print(result.stdout)
    if result.stderr:
        verbose_log(f"Command stderr for {name} on {domain}: {result.stderr}", workflow_name)
        print(f"\n[ERROR] {name} on {domain}:")
        print(result.stderr)

    log_status(domain, name, "done")
    verbose_log(f"Completed step {name} for {domain}", workflow_name)

def scan_domain(domain, pipeline, date_str, skip_if_any_result=True, workflow_name=None, rescan_steps=None):
    firstdomain = domain 
    domain = check_cidr(domain)   

    global resolved_paths_cache
    resolved_paths_cache.setdefault(domain, {})

    verbose_log(f"Starting scan for domain: {domain}", workflow_name)

    # Analyze pipeline for parallel execution groups
    step_groups = analyze_pipeline_dependencies(pipeline)
    verbose_log(f"Pipeline analysis: {len(step_groups)} groups for {domain}", workflow_name)
    
    for i, group in enumerate(step_groups):
        verbose_log(f"Group {i+1}: {len(group['steps'])} steps, cat_base='{group['cat_base']}', parallel={group['parallel']}", workflow_name)
        for step in group['steps']:
            verbose_log(f"  - {step['name']}", workflow_name)

    # If rescanning specific steps, determine which steps need to run
    required_steps = None
    if isinstance(rescan_steps, list) and len(rescan_steps) == 1:
        target_step = rescan_steps[0]
        target_index = None
        
        for i, step in enumerate(pipeline):
            if step['name'] == target_step:
                target_index = i
                break
        
        if target_index is not None:
            required_steps = [step['name'] for step in pipeline[target_index:]]
            verbose_log(f"Rescanning {target_step} - will execute: {required_steps}", workflow_name)

    # Execute each group
    for group in step_groups:
        # Filter steps in this group based on rescan requirements
        if required_steps is not None:
            # Only execute steps that are in the required_steps list
            filtered_steps = [step for step in group['steps'] if step['name'] in required_steps]
            if filtered_steps:
                filtered_group = {
                    'cat_base': group['cat_base'],
                    'steps': filtered_steps,
                    'parallel': len(filtered_steps) > 1 and group['parallel']
                }
                execute_step_group(domain, filtered_group, date_str, skip_if_any_result, workflow_name, rescan_steps, resolved_paths_cache)
        else:
            execute_step_group(domain, group, date_str, skip_if_any_result, workflow_name, rescan_steps, resolved_paths_cache)

def worker(domains, pipeline, scan_name, date_str, skip_if_any_result=True, all_workflows=None, all_domains=None, rescan_steps=None):
    threads = []
    for domain in domains:
        t = threading.Thread(target=scan_domain, args=(domain, pipeline, date_str, skip_if_any_result, scan_name, rescan_steps))
        t.start()
        threads.append(t)

    # Use different status display based on whether we're running parallel workflows
    if all_workflows and all_domains:
        print_all_workflows_status(all_workflows, all_domains)
    else:
        print_status(domains, pipeline, scan_name)

    last_print = time.time()
    while any(t.is_alive() for t in threads):
        now = time.time()
        if now - last_print > 1:
            if all_workflows and all_domains:
                print_all_workflows_status(all_workflows, all_domains)
            else:
                print_status(domains, pipeline, scan_name)
            last_print = now
        time.sleep(0.1)

    # Final status update
    if all_workflows and all_domains:
        print_all_workflows_status(all_workflows, all_domains)
    else:
        print_status(domains, pipeline, scan_name)

def load_configs(path):
    configs = []
    for yaml_path in Path(path).glob("*.yaml"):
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
            config['__file'] = yaml_path
            configs.append(config)
    return configs

def get_workflow_names():
    workflows = []
    for yaml_path in Path("scans-wf/").glob("*.yaml"):
        try:
            with open(yaml_path) as f:
                config = yaml.safe_load(f)
                workflow_name = config.get('name', yaml_path.stem)
                workflows.append({
                    'name': workflow_name,
                    'file': yaml_path.name,
                    'description': config.get('description', 'No description')
                })
        except Exception as e:
            print(f"Warning: Could not load {yaml_path}: {e}")
    return workflows

def show_workflow_names():
    workflows = get_workflow_names()
    
    if not workflows:
        print("[ERROR] No workflow files found in scans-wf/ directory!")
        return
    
    print("\n[LIST] Available Workflows:")
    print("=" * 60)
    
    for i, workflow in enumerate(workflows, 1):
        print(f"{i:2d}. {workflow['name']}")
        print(f"    [FILE] File: {workflow['file']}")
        print(f"    [NOTE] Description: {workflow['description']}")
        print()
    
    print("[TIP] Usage:")
    print("  python sebat.py -wf workflow-name -t targets.txt")
    print("  python sebat.py -wf workflow1,workflow2 -t targets.txt")
    print("  python sebat.py -t targets.txt  (runs all workflows)")

def load_workflows_by_names(workflow_names):
    all_workflows = get_workflow_names()
    available_names = {w['name']: w['file'] for w in all_workflows}
    
    configs = []
    for name in workflow_names:
        name = name.strip()
        if name in available_names:
            file_path = f"scans-wf/{available_names[name]}"
            try:
                with open(file_path) as f:
                    config = yaml.safe_load(f)
                    config['__file'] = file_path
                    configs.append(config)
            except Exception as e:
                print(f"[ERROR] Error loading workflow '{name}': {e}")
        else:
            print(f"[ERROR] Workflow '{name}' not found!")
            print(f"[TIP] Available workflows: {', '.join(available_names.keys())}")
    
    return configs

def find_latest_scan_date():
    results_dir = Path("results-scan")
    if not results_dir.exists():
        return None
    
    dates = set()
    for domain_dir in results_dir.iterdir():
        if domain_dir.is_dir():
            for category_dir in domain_dir.rglob("*"):
                if category_dir.is_dir():
                    for file_path in category_dir.iterdir():
                        if file_path.is_file() and file_path.name.startswith("scan-at-"):
                            date_part = file_path.name.replace("scan-at-", "").split("-")[:3]
                            if len(date_part) == 3:
                                date_str = "-".join(date_part)
                                dates.add(date_str)
    
    if dates:
        return max(dates)  
    return None

def check_current_results(date_str):
    results_dir = Path("results-scan")
    if not results_dir.exists():
        print("[ERROR] No results-scan directory found!")
        return
    
    print(f"\n[RESULTS] Scan Results for Date: {date_str}")
    print("=" * 60)
    
    found_results = False
    total_files = 0
    
    for domain_dir in sorted(results_dir.iterdir()):
        if domain_dir.is_dir():
            domain_name = domain_dir.name
            domain_has_results = False
            
            print(f"\n[DOMAIN] Domain: {domain_name}")
            print("-" * 40)
            
            for category_dir in sorted(domain_dir.iterdir()):
                if category_dir.is_dir():
                    category_name = category_dir.name
                    category_has_results = False
                    
                    for tool_dir in sorted(category_dir.iterdir()):
                        if tool_dir.is_dir():
                            tool_name = tool_dir.name
                            
                            for file_path in tool_dir.iterdir():
                                if file_path.is_file() and f"scan-at-{date_str}" in file_path.name:
                                    file_size = file_path.stat().st_size
                                    size_str = f"{file_size} bytes" if file_size < 1024 else f"{file_size/1024:.1f} KB"
                                    
                                    print(f"  [FILE] {category_name}/{tool_name}/")
                                    print(f"      [DOC] {file_path.name} ({size_str})")
                                    
                                    try:
                                        with open(file_path, 'r', encoding='utf-8') as f:
                                            lines = f.readlines()[:5] 
                                            if lines:
                                                print("      [NOTE] Content preview:")
                                                for line in lines:
                                                    print(f"         {line.rstrip()}")
                                                if len(f.readlines()) > 5:
                                                    print("         ... (more content)")
                                    except Exception as e:
                                        print(f"      [WARNING]  Could not read file: {e}")
                                    
                                    print()
                                    category_has_results = True
                                    domain_has_results = True
                                    found_results = True
                                    total_files += 1
                    
                    if not category_has_results:
                        for file_path in category_dir.iterdir():
                            if file_path.is_file() and f"scan-at-{date_str}" in file_path.name:
                                file_size = file_path.stat().st_size
                                size_str = f"{file_size} bytes" if file_size < 1024 else f"{file_size/1024:.1f} KB"
                                
                                print(f"  [FILE] {category_name}/")
                                print(f"      [DOC] {file_path.name} ({size_str})")
                                print()
                                domain_has_results = True
                                found_results = True
                                total_files += 1
            
            if not domain_has_results:
                print("  [ERROR] No results found for this domain")
    
    if not found_results:
        print(f"[ERROR] No scan results found for date: {date_str}")
        print("[TIP] Try running a scan first or check a different date")
    else:
        print(f"\n[SUCCESS] Found {total_files} result files for {date_str}")

def analyze_step_dependencies(pipeline, target_step_name):
    """Analyze which steps need to run to provide input for the target step"""
    if target_step_name not in [step['name'] for step in pipeline]:
        return []
    
    # Find the target step index
    target_index = None
    for i, step in enumerate(pipeline):
        if step['name'] == target_step_name:
            target_index = i
            break
    
    if target_index is None:
        return []
    
    # Find all steps that the target step depends on
    required_steps = []
    target_step = pipeline[target_index]
    target_command = target_step['command']
    
    # Check for dependencies in the target step's command
    for i in range(target_index):
        prev_step = pipeline[i]
        prev_step_name = prev_step['name']
        placeholder = f"{prev_step_name}.output_file"
        if placeholder in target_command:
            required_steps.append(prev_step_name)
    
    # Add the target step itself
    required_steps.append(target_step_name)
    
    return required_steps

def analyze_pipeline_dependencies(pipeline):
    """Analyze pipeline to group steps for parallel execution within same cat_base"""
    step_groups = []
    current_group = []
    current_cat_base = None
    
    for i, step in enumerate(pipeline):
        step_name = step['name']
        cat_base = (step.get('cat_base') or '').strip()
        command = step['command']
        
        # Check if this step depends on any previous step
        has_dependencies = False
        for j in range(i):
            prev_step = pipeline[j]
            prev_step_name = prev_step['name']
            placeholder = f"{prev_step_name}.output_file"
            if placeholder in command:
                has_dependencies = True
                break
        
        # If this step has dependencies, start a new group
        if has_dependencies:
            if current_group:
                step_groups.append({
                    'cat_base': current_cat_base,
                    'steps': current_group,
                    'parallel': len(current_group) > 1
                })
            current_group = [step]
            current_cat_base = cat_base
        else:
            # No dependencies, check if we can add to current group
            if current_cat_base == cat_base and cat_base:
                # Same cat_base, add to current group
                current_group.append(step)
            else:
                # Different cat_base or no cat_base, start new group
                if current_group:
                    step_groups.append({
                        'cat_base': current_cat_base,
                        'steps': current_group,
                        'parallel': len(current_group) > 1
                    })
                current_group = [step]
                current_cat_base = cat_base
    
    # Add the last group
    if current_group:
        step_groups.append({
            'cat_base': current_cat_base,
            'steps': current_group,
            'parallel': len(current_group) > 1
        })
    
    return step_groups

def print_completion_message(date_str, total_domains, total_workflows):
    """Print a beautiful completion message with scan summary"""
    print("\n" + "=" * 80)
    print("🎉 SCAN COMPLETED SUCCESSFULLY! 🎉")
    print("=" * 80)
    print(f"📅 Scan Date: {date_str}")
    print(f"🎯 Total Domains: {total_domains}")
    print(f"⚙️  Total Workflows: {total_workflows}")
    print(f"🆔 Scan ID: {get_scan_id()}")
    print()
    print("📁 RESULTS LOCATION:")
    print("   └── results-scan/")
    print("       └── {domain}/")
    print("           └── {category}/")
    print("               └── {tool}/")
    print("                   └── scan-at-{date_str}")
    print()
    print("🔍 USEFUL COMMANDS:")
    print("   • Check results: python sebat.py -vl")
    print("   • List workflows: python sebat.py -sn")
    print()
    print("=" * 80)

def show_workflow_diagram(workflow_name):
    """Display a beautiful workflow diagram for a specific workflow"""
    # Load the workflow
    configs = load_workflows_by_names([workflow_name])
    if not configs:
        print(f"[ERROR] Workflow '{workflow_name}' not found!")
        print("[TIP] Use 'python sebat.py -sn' to see available workflows")
        return
    
    config = configs[0]
    pipeline = config.get('pipeline', [])
    description = config.get('description', 'No description')
    reference = config.get('reference', 'No reference')
    
    # Analyze pipeline dependencies
    step_groups = analyze_pipeline_dependencies(pipeline)
    
    print("\n" + "=" * 80)
    print(f"WORKFLOW DIAGRAM: {workflow_name.upper()}")
    print("=" * 80)
    print(f"Description: {description}")
    print(f"Reference: {reference}")
    print(f"Total Steps: {len(pipeline)}")
    print(f"Execution Groups: {len(step_groups)}")
    print()
    
    # Display beautiful ASCII flowchart
    print("FLOWCHART DIAGRAM:")
    print()
    
    # Calculate the maximum step name length for proper box sizing
    max_step_length = 0
    for group in step_groups:
        for step in group['steps']:
            max_step_length = max(max_step_length, len(step['name']))
    
    # Ensure minimum width
    box_width = max(max_step_length + 4, 12)
    
    # Start with target
    print(" " * 20 + "┌─────────┐")
    print(" " * 20 + "│  TARGET │")
    print(" " * 20 + "└─────────┘")
    print(" " * 20 + "     │")
    print(" " * 20 + "     ▼")
    
    for i, group in enumerate(step_groups):
        group_name = group['cat_base'] if group['cat_base'] else 'general'
        steps = group['steps']
        
        if len(steps) == 1:
            # Single step - simple flow
            step = steps[0]
            step_name = step['name']
            
            # Center the step name in the box
            padding = (box_width - len(step_name)) // 2
            left_pad = padding
            right_pad = box_width - len(step_name) - left_pad
            
            print(" " * 20 + "┌" + "─" * box_width + "┐")
            print(" " * 20 + "│" + " " * left_pad + step_name + " " * right_pad + "│")
            print(" " * 20 + "└" + "─" * box_width + "┘")
            
            if i < len(step_groups) - 1:
                print(" " * 20 + "     │")
                print(" " * 20 + "     ▼")
        
        else:
            # Multiple steps - show parallel execution
            if group['parallel']:
                # Parallel execution
                print(" " * 20 + "┌" + "─" * box_width + "┐")
                
                for j, step in enumerate(steps):
                    step_name = step['name']
                    padding = (box_width - len(step_name)) // 2
                    left_pad = padding
                    right_pad = box_width - len(step_name) - left_pad
                    
                    print(" " * 20 + "│" + " " * left_pad + step_name + " " * right_pad + "│")
                
                print(" " * 20 + "└" + "─" * box_width + "┘")
                print(" " * 20 + "     │")
                print(" " * 20 + "     ▼")
            else:
                # Sequential execution within group
                for j, step in enumerate(steps):
                    step_name = step['name']
                    padding = (box_width - len(step_name)) // 2
                    left_pad = padding
                    right_pad = box_width - len(step_name) - left_pad
                    
                    print(" " * 20 + "┌" + "─" * box_width + "┐")
                    print(" " * 20 + "│" + " " * left_pad + step_name + " " * right_pad + "│")
                    print(" " * 20 + "└" + "─" * box_width + "┘")
                    
                    if j < len(steps) - 1:
                        print(" " * 20 + "     │")
                        print(" " * 20 + "     ▼")
                    elif i < len(step_groups) - 1:
                        print(" " * 20 + "     │")
                        print(" " * 20 + "     ▼")
    
    print(" " * 20 + "┌─────────┐")
    print(" " * 20 + "│ RESULTS │")
    print(" " * 20 + "└─────────┘")

def validate_rescan_steps(step_names, configs):
    """Validate that the provided step names exist in the workflows"""
    if not step_names:
        return True, []
    
    all_steps = set()
    workflow_steps = {}
    
    for config in configs:
        workflow_name = config.get('name', 'Unknown')
        pipeline = config.get('pipeline', [])
        workflow_steps[workflow_name] = [step['name'] for step in pipeline]
        all_steps.update(workflow_steps[workflow_name])
    
    invalid_steps = [step for step in step_names if step not in all_steps]
    
    if invalid_steps:
        return False, invalid_steps, workflow_steps
    
    return True, []

def main():
    parser = argparse.ArgumentParser(description="Dynamic YAML-based scan runner")
    parser.add_argument("-t", "--targets", help="Target domains file")
    parser.add_argument("-pt", "--parallel-targets", type=int, default=3, help="Number of targets to process in parallel")
    parser.add_argument("-pw", "--parallel-workflows", type=int, default=1, help="Number of workflows to process in parallel")
    parser.add_argument("-rs", "--rescan", nargs='?', const=True, metavar='STEP', help="Force re-scan. Use -rs to rescan all steps, or -rs STEP_NAME to rescan specific step only")
    parser.add_argument("-sn", "--show-names", action="store_true", help="Show available workflow names")
    parser.add_argument("-sw", "--show-workflow", metavar='WORKFLOW_NAME', help="Show beautiful workflow diagram for specific workflow")
    parser.add_argument("-wf", "--workflow", help="Specific workflow name(s), comma-separated (e.g., workflow1,workflow2)")
    parser.add_argument("-v", "--verbose", nargs='?', const='all', metavar='SID', help="Show logs in real-time. Use '-v' for all logs or '-v SID' for specific scan")
    parser.add_argument("-vl", "--view-logs", action="store_true", help="List available log files")
    parser.add_argument("-cl", "--clear-logs", action="store_true", help="Clear all debug log files")
    args = parser.parse_args()

    # Handle clear logs
    if args.clear_logs:
        clear_logs()
        return

    # Handle verbose as log reader mode
    if args.verbose is not None:
        show_logs_realtime(args.verbose)
        return

    # Handle view logs
    if args.view_logs:
        list_log_files()
        return

    if args.show_names:
        show_workflow_names()
        return

    if args.show_workflow:
        show_workflow_diagram(args.show_workflow)
        return

    if not args.targets:
        parser.error("Targets file (-t) is required for scanning. Use -sn to show available workflows.")

    with open(args.targets) as f:
        all_domains = [line.strip() for line in f if line.strip()]

    verbose_log(f"Loaded {len(all_domains)} targets from {args.targets}")

    if args.workflow:
        workflow_names = [name.strip() for name in args.workflow.split(',')]
        configs = load_workflows_by_names(workflow_names)
        if not configs:
            print("[ERROR] No valid workflows specified. Use -sn to see available workflows.")
            return
        verbose_log(f"Selected workflows: {workflow_names}")
    else:
        configs = load_configs("scans-wf/")
        if not configs:
            print("[ERROR] No workflow files found in scans-wf/ directory!")
            return
        verbose_log(f"Loaded {len(configs)} workflows from scans-wf/ directory")

    date_str = datetime.now().strftime("%Y-%m-%d")
    verbose_log(f"Scan date: {date_str}")

    # Process rescan argument and determine scan mode
    rescan_steps = None
    scan_mode = "smart"  # Default mode: check existing results and skip if available
    
    if args.rescan is not None:
        if args.rescan is True:
            # -rs without value: rescan all steps
            rescan_steps = True
            scan_mode = "force_all"
            verbose_log("Rescan mode: All steps will be rescanned")
            print("[INFO] 🔄 Rescan mode: All steps will be rescanned")
        else:
            # -rs with value: rescan specific step(s)
            step_names = [name.strip() for name in args.rescan.split(',')]
            
            # Validate step names
            validation_result = validate_rescan_steps(step_names, configs)
            if len(validation_result) == 2:
                is_valid, _ = validation_result
                if not is_valid:
                    print(f"[ERROR] Invalid step name(s): {', '.join(step_names)}")
                    return
            else:
                is_valid, invalid_steps, workflow_steps = validation_result
                if not is_valid:
                    print(f"[ERROR] Invalid step name(s): {', '.join(invalid_steps)}")
                    print("\n[INFO] Available steps by workflow:")
                    for workflow_name, steps in workflow_steps.items():
                        print(f"  {workflow_name}: {', '.join(steps)}")
                    print(f"\n[TIP] Use: python sebat.py -rs STEP_NAME -t {args.targets}")
                    return
            
            rescan_steps = step_names
            scan_mode = "force_specific"
            verbose_log(f"Rescan mode: Specific steps will be rescanned: {step_names}")
            
            # Show which steps will be executed for each workflow
            print(f"[INFO] 🔄 Rescan mode: Specific steps will be rescanned: {', '.join(step_names)}")
            for config in configs:
                workflow_name = config.get('name', 'Unknown')
                pipeline = config.get('pipeline', [])
                
                if len(step_names) == 1:
                    # Single step rescan - show target step and all steps after it
                    target_step = step_names[0]
                    target_index = None
                    for i, step in enumerate(pipeline):
                        if step['name'] == target_step:
                            target_index = i
                            break
                    
                    if target_index is not None:
                        steps_to_execute = [step['name'] for step in pipeline[target_index:]]
                        print(f"[INFO] Workflow '{workflow_name}': Will execute {', '.join(steps_to_execute)} (from {target_step} onwards)")
                    else:
                        print(f"[INFO] Workflow '{workflow_name}': Will execute {target_step}")
                else:
                    # Multiple steps rescan
                    print(f"[INFO] Workflow '{workflow_name}': Will execute {', '.join(step_names)}")
    else:
        verbose_log("Smart mode: Will check existing results and skip completed steps")
        print("[INFO] 🧠 Smart mode: Will check existing results and skip completed steps")
        print("[INFO] 💡 Use '-rs' to force rescan all steps, or '-rs STEP_NAME' for specific step")

    # Setup verbose logging for file output only
    global verbose_enabled
    verbose_enabled = True
    setup_verbose_logging()
    verbose_log("Sebatch started with logging enabled")

    # Process workflows in parallel
    def run_workflow(config, is_parallel_workflows=False, active_workflows=None):
        current_scan_name = config.get('name', 'Unknown Scan')
        
        if not is_parallel_workflows:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"\n=== Running scan: {current_scan_name} ({config['__file']}) ===")
        
        verbose_log(f"Starting workflow: {current_scan_name}", current_scan_name)
        pipeline = config['pipeline']
        verbose_log(f"Workflow has {len(pipeline)} steps", current_scan_name)

        # Remove the code that creates all output directories at the start
        # Directories will be created only when needed during step execution

        verbose_log(f"Starting scan processing for {len(all_domains)} domains", current_scan_name)

        global resolved_paths_cache
        resolved_paths_cache = {}

        for domain in all_domains:
            domain_checked = check_cidr(domain)
            for step in pipeline:
                # Initialize status based on rescan mode
                if rescan_steps is not None:
                    if rescan_steps is True:
                        # Force rescan all steps
                        log_status(domain_checked, step["name"], "waiting...")
                    elif isinstance(rescan_steps, list):
                        # For specific rescan, determine which steps will actually run
                        if len(rescan_steps) == 1:
                            # Single step rescan - find the target step and all steps after it
                            target_step = rescan_steps[0]
                            target_index = None
                            for i, pipeline_step in enumerate(pipeline):
                                if pipeline_step['name'] == target_step:
                                    target_index = i
                                    break
                            
                            if target_index is not None:
                                # All steps from target_index onwards will run
                                steps_to_run = [s['name'] for s in pipeline[target_index:]]
                                if step["name"] in steps_to_run:
                                    log_status(domain_checked, step["name"], "waiting...")
                                else:
                                    # Step is not in the dependency chain, mark as skipped if it has output
                                    if is_any_result_exists(domain_checked, step):
                                        log_status(domain_checked, step["name"], "skipped")
                                    else:
                                        log_status(domain_checked, step["name"], "waiting...")
                            else:
                                # Target step not found, use original logic
                                if step["name"] in rescan_steps:
                                    log_status(domain_checked, step["name"], "waiting...")
                                else:
                                    if is_any_result_exists(domain_checked, step):
                                        log_status(domain_checked, step["name"], "skipped")
                                    else:
                                        log_status(domain_checked, step["name"], "waiting...")
                        else:
                            # Multiple steps rescan - use original logic
                            if step["name"] in rescan_steps:
                                log_status(domain_checked, step["name"], "waiting...")
                            else:
                                if is_any_result_exists(domain_checked, step):
                                    log_status(domain_checked, step["name"], "skipped")
                                else:
                                    log_status(domain_checked, step["name"], "waiting...")
                else:
                    # Smart mode: check if output exists
                    # Determine skip logic based on scan mode
                    if scan_mode == "smart":
                        skip_logic = True  # Smart mode: skip if results exist
                    elif scan_mode == "force_all":
                        skip_logic = False  # Force all: never skip
                    elif scan_mode == "force_specific":
                        skip_logic = False  # Force specific: never skip (handled by rescan_steps)
                    else:
                        skip_logic = True  # Default to smart mode
                    
                    if skip_logic and is_any_result_exists(domain_checked, step):
                        log_status(domain_checked, step["name"], "skipped")
                    else:
                        log_status(domain_checked, step["name"], "waiting...")

        from queue import Queue, Empty
        domain_queue = Queue()
        for domain in all_domains:
            domain_queue.put(domain)

        active_domains = set()
        active_domains_lock = threading.Lock()

        def print_status_active():
            with active_domains_lock:
                domains_to_print = list(active_domains)
            print_status(domains_to_print, pipeline, current_scan_name)

        def domain_worker():
            while True:
                try:
                    domain = domain_queue.get_nowait()
                except Empty:
                    break
                with active_domains_lock:
                    active_domains.add(domain)
                
                # Determine skip logic based on scan mode
                if scan_mode == "smart":
                    skip_logic = True  # Smart mode: skip if results exist
                elif scan_mode == "force_all":
                    skip_logic = False  # Force all: never skip
                elif scan_mode == "force_specific":
                    skip_logic = False  # Force specific: never skip (handled by rescan_steps)
                else:
                    skip_logic = True  # Default to smart mode
                
                scan_domain(domain, pipeline, date_str, skip_logic, current_scan_name, rescan_steps)
                with active_domains_lock:
                    active_domains.remove(domain)
                domain_queue.task_done()

        threads = []
        for _ in range(args.parallel_targets):
            t = threading.Thread(target=domain_worker)
            t.start()
            threads.append(t)

        last_print = time.time()
        while any(t.is_alive() for t in threads):
            now = time.time()
            if now - last_print > 1:
                if is_parallel_workflows:
                    print_all_workflows_status(active_workflows, all_domains)
                else:
                    print_status_active()
                last_print = now
            time.sleep(0.1)

        for t in threads:
            t.join()

        if is_parallel_workflows:
            print_all_workflows_status(active_workflows, all_domains)
        else:
            print_status_active()

        verbose_log(f"Completed workflow: {current_scan_name}", current_scan_name)
        
        # Show workflow completion message
        if not is_parallel_workflows:
            print(f"\n✅ Workflow '{current_scan_name}' completed!")
            print(f"📁 Check results in: results-scan/")
            print("-" * 60)

    # Run workflows in parallel if specified
    if args.parallel_workflows > 1 and len(configs) > 1:
        # Clear screen for clean display
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Limit the number of workflows to run based on parallel_workflows
        workflows_to_run = configs[:args.parallel_workflows]
        print(f"\nRunning {len(workflows_to_run)} workflows (limited by -pw {args.parallel_workflows})")
        print(f"Workflows: {[c.get('name', 'Unknown') for c in workflows_to_run]}")
        
        verbose_log(f"Running {len(workflows_to_run)} workflows in parallel (limited by -pw {args.parallel_workflows})")
        verbose_log(f"Workflow names: {[c.get('name', 'Unknown') for c in workflows_to_run]}")
        
        workflow_threads = []
        for config in workflows_to_run:
            t = threading.Thread(target=run_workflow, args=(config, True, workflows_to_run)) 
            t.start()
            workflow_threads.append(t)
        
        # Wait for all workflows to complete
        for t in workflow_threads:
            t.join()
        
        verbose_log("All parallel workflows completed")
        print(f"\n✅ All {len(workflows_to_run)} workflows completed in parallel!")
        print(f"📁 Check results in: results-scan/")
        print("-" * 60)
    else:
        # Run workflows sequentially
        verbose_log(f"Running {len(configs)} workflows sequentially")
        for config in configs:
            run_workflow(config, False, None) 

    verbose_log("All scans completed")
    
    # Show completion message
    print_completion_message(date_str, len(all_domains), len(configs))
    
    cleanup_verbose_logging()

if __name__ == "__main__":
    main()