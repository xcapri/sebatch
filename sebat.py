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

statuses = {}
resolved_paths_cache = {}

lock = threading.Lock()

# Global verbose logging
verbose_log_file = None
verbose_enabled = False
progress_lines_count = 0  

def show_logs_realtime():
    debug_dir = Path("debug")
    if not debug_dir.exists():
        print("[ERROR] No debug directory found! Run a scan first to generate logs.")
        return
    
    # Get current date and look for today's log file
    current_date = datetime.now().strftime("%Y%m%d")
    log_filename = f"sebatch_verbose_{current_date}.log"
    log_path = debug_dir / log_filename
    
    if not log_path.exists():
        print(f"[ERROR] No log file found for today ({current_date})! Run a scan first to generate logs.")
        print(f"[INFO] Expected log file: {log_filename}")
        return
    
    print(f"[INFO] Reading log file: {log_filename}")
    print("[INFO] Press Ctrl+C to stop reading logs")
    print("-" * 80)
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            # Read existing content
            content = f.read()
            if content:
                print(content)
            
            # Follow new content in real-time
            while True:
                new_content = f.read()
                if new_content:
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
    prefix = f"[{workflow_name}] " if workflow_name else ""
    log_message = f"[{timestamp}] {prefix}{message}"
    
    # Write to log file
    if verbose_log_file:
        try:
            verbose_log_file.write(log_message + "\n")
            verbose_log_file.flush()  
        except Exception as e:
            print(f"Warning: Could not write to verbose log: {e}")

def clear_logs():
    debug_dir = Path("debug")
    if not debug_dir.exists():
        print("[INFO] No debug directory found. Nothing to clear.")
        return
    
    log_files = list(debug_dir.glob("sebatch_verbose_*.log"))
    if not log_files:
        print("[INFO] No log files found. Nothing to clear.")
        return
    
    count = 0
    for log_file in log_files:
        try:
            log_file.unlink()
            count += 1
        except Exception as e:
            print(f"[WARNING] Could not delete {log_file.name}: {e}")
    
    print(f"[SUCCESS] Cleared {count} log files from debug/ directory")

def setup_verbose_logging():
    global verbose_log_file, verbose_enabled
    
    if not verbose_enabled:
        return
    
    # Create debug folder if it doesn't exist
    debug_dir = Path("debug")
    debug_dir.mkdir(exist_ok=True)
    
    # Create log file with date only (no time)
    date_str = datetime.now().strftime("%Y%m%d")
    log_filename = f"debug/sebatch_verbose_{date_str}.log"
    
    try:
        verbose_log_file = open(log_filename, 'w', encoding='utf-8')
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
        
        # Print progress at the top
        print(f"Scan Progress ({scan_name}):\n")

        for domainx in domains:
            domain = check_cidr(domainx)
            line = f"{domain:25} |"
            for step in steps:
                key = f"{domain}::{step['name']}"
                stat = statuses.get(key, "waiting...")
                line += f" {step['name']}={stat:15} "
            print(line)

        waiting_count = sum(1 for s in statuses.values() if s == "waiting...")
        done_count = sum(1 for s in statuses.values() if s == "done" or s == "skipped")
        print(f"\n[WAITING: {waiting_count}] [DONE: {done_count}]\n")

def print_all_workflows_status(workflow_configs, current_domains):
    with lock:
        # Always clear screen for clean progress display
        os.system('cls' if os.name == 'nt' else 'clear')
        
        for config in workflow_configs:
            scan_name = config.get('name', 'Unknown Scan')
            pipeline = config['pipeline']
            
            print(f"Scan Progress ({scan_name}):\n")
            
            for domainx in current_domains:
                domain = check_cidr(domainx)
                line = f"{domain:25} |"
                for step in pipeline:
                    key = f"{domain}::{step['name']}"
                    stat = statuses.get(key, "waiting...")
                    line += f" {step['name']}={stat:15} "
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
            for file_path in category_dir.iterdir():
                if file_path.is_file() and file_path.name.startswith("scan-at-"):
                    # Check if it's from today or find the most recent
                    if date_str in file_path.name:
                        return str(file_path)
                    else:
                        # If not today, find the most recent file
                        scan_files = [f for f in category_dir.iterdir() if f.is_file() and f.name.startswith("scan-at-")]
                        if scan_files:
                            latest_file = max(scan_files, key=lambda x: x.stat().st_mtime)
                            return str(latest_file)
    
    return None

def scan_domain(domain, pipeline, date_str, skip_if_any_result=True, workflow_name=None, rescan_steps=None):
    firstdomain = domain 
    domain = check_cidr(domain)   

    global resolved_paths_cache
    resolved_paths_cache.setdefault(domain, {})

    verbose_log(f"Starting scan for domain: {domain}", workflow_name)

    # If rescanning specific steps, determine which steps need to run
    required_steps = None
    if isinstance(rescan_steps, list) and len(rescan_steps) == 1:
        # Single step rescan - find the step and all steps after it
        target_step = rescan_steps[0]
        target_index = None
        
        # Find the target step index
        for i, step in enumerate(pipeline):
            if step['name'] == target_step:
                target_index = i
                break
        
        if target_index is not None:
            # Include the target step and all steps after it
            required_steps = [step['name'] for step in pipeline[target_index:]]
            verbose_log(f"Rescanning {target_step} - will execute: {required_steps}", workflow_name)

    for step_index, step in enumerate(pipeline):
        name = step["name"]

        actual_output_file_path = get_output_path(domain, step, date_str)
        resolved_paths_cache[domain][name] = actual_output_file_path

        cmd = step["command"]
        cmd = cmd.replace("{domain}", firstdomain)  

        for i in range(step_index):
            prev_step = pipeline[i]
            prev_step_name = prev_step["name"]
            placeholder = f"{prev_step_name}.output_file"
            if placeholder in cmd:
                resolved_prev_output = resolved_paths_cache[domain].get(prev_step_name)
                if resolved_prev_output:
                    cmd = cmd.replace(placeholder, resolved_prev_output)
                    verbose_log(f"Replaced {placeholder} with {resolved_prev_output} for {domain}", workflow_name)
                else:
                    verbose_log(f"Warning: Reference '{placeholder}' not found for domain {domain} in step {name}. Command might be invalid.", workflow_name)

        # Handle references to steps not in current workflow (from previous scans)
        # Extract all step references from the command
        step_references = re.findall(r'(\w+)\.output_file', cmd)
        
        for step_name in step_references:
            placeholder = f"{step_name}.output_file"
            if placeholder in cmd:
                # First check if this step exists in current workflow and has been resolved
                if step_name in resolved_paths_cache[domain] and resolved_paths_cache[domain][step_name]:
                    # Use the resolved path from current workflow
                    resolved_output = resolved_paths_cache[domain][step_name]
                    cmd = cmd.replace(placeholder, resolved_output)
                    verbose_log(f"Replaced {placeholder} with {resolved_output} for {domain}", workflow_name)
                else:
                    # Try to find from previous scans
                    previous_output = find_previous_scan_output(domain, step_name, date_str)
                    if previous_output:
                        cmd = cmd.replace(placeholder, previous_output)
                        verbose_log(f"Found previous scan output for {step_name}: {previous_output} for {domain}", workflow_name)
                    else:
                        verbose_log(f"Warning: Could not find output file for step '{step_name}' in current workflow or previous scans for domain {domain}", workflow_name)

        if actual_output_file_path:
            cmd = cmd.replace("{output_file}", actual_output_file_path)
            verbose_log(f"Output file path: {actual_output_file_path} for {domain}", workflow_name)

        # Determine if this step should be rescanned
        should_rescan = False
        if rescan_steps is not None:  # Rescan mode is enabled
            if rescan_steps is True:  # Rescan all steps
                should_rescan = True
            elif isinstance(rescan_steps, list):
                if name in rescan_steps:  # Rescan specific steps
                    should_rescan = True
                elif required_steps and name in required_steps:  # Required steps (target + after)
                    should_rescan = True
        
        # Skip logic: if we're not rescanning and results exist, skip
        if not should_rescan and skip_if_any_result and is_any_result_exists(domain, step):
            log_status(domain, name, "skipped")
            verbose_log(f"Step {name} skipped for {domain} (any result already exists)", workflow_name)
            continue

        if not should_rescan and actual_output_file_path and is_output_valid(actual_output_file_path, domain):
            log_status(domain, name, "skipped")
            verbose_log(f"Step {name} skipped for {domain} (output already exists)", workflow_name)
            continue

        log_status(domain, name, "running")
        verbose_log(f"Executing step {name} for {domain}: {cmd}", workflow_name)

        result = run_command(cmd)
        
        # Log command output if verbose
        if result.stdout:
            verbose_log(f"Command output for {name} on {domain}: {result.stdout}", workflow_name)
            # Also show output in real-time
            print(f"\n[OUTPUT] {name} on {domain}:")
            print(result.stdout)
        if result.stderr:
            verbose_log(f"Command stderr for {name} on {domain}: {result.stderr}", workflow_name)
            # Also show stderr in real-time
            print(f"\n[ERROR] {name} on {domain}:")
            print(result.stderr)

        log_status(domain, name, "done")
        verbose_log(f"Completed step {name} for {domain}", workflow_name)

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
        print("[TIP] Use 'python sebat.py -ccr latest' to check the most recent results")

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
    parser.add_argument("-wf", "--workflow", help="Specific workflow name(s), comma-separated (e.g., workflow1,workflow2)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show logs in real-time (log reader mode)")
    parser.add_argument("-cl", "--clear-logs", action="store_true", help="Clear all debug log files")
    args = parser.parse_args()

    # Handle clear logs
    if args.clear_logs:
        clear_logs()
        return

    # Handle verbose as log reader mode
    if args.verbose:
        show_logs_realtime()
        return

    if args.show_names:
        show_workflow_names()
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

    # Process rescan argument
    rescan_steps = None
    if args.rescan is not None:
        if args.rescan is True:
            # -rs without value: rescan all steps
            rescan_steps = True
            verbose_log("Rescan mode: All steps will be rescanned")
            print("[INFO] Rescan mode: All steps will be rescanned")
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
            verbose_log(f"Rescan mode: Specific steps will be rescanned: {step_names}")
            
            # Show which steps will be executed for each workflow
            print(f"[INFO] Rescan mode: Specific steps will be rescanned: {', '.join(step_names)}")
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
        verbose_log("Normal mode: Existing results will be used if available")

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

        for domain in all_domains:
            domain_checked = check_cidr(domain)
            for step in pipeline:
                out_path = get_output_path(domain_checked, step, date_str)
                Path(os.path.dirname(out_path)).mkdir(parents=True, exist_ok=True)
        
        verbose_log(f"Created output directories for {len(all_domains)} domains", current_scan_name)

        global resolved_paths_cache
        resolved_paths_cache = {}

        for domain in all_domains:
            domain_checked = check_cidr(domain)
            for step in pipeline:
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
                skip_logic = rescan_steps is None  # Only skip if not in rescan mode
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
    else:
        # Run workflows sequentially
        verbose_log(f"Running {len(configs)} workflows sequentially")
        for config in configs:
            run_workflow(config, False, None) 

    verbose_log("All scans completed")
    
    cleanup_verbose_logging()

if __name__ == "__main__":
    main()