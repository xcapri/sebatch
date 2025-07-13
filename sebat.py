#!/usr/bin/env python3

import subprocess
import threading
import argparse
import time
import yaml
from pathlib import Path
import os
from datetime import datetime

statuses = {}
resolved_paths_cache = {}

lock = threading.Lock()

def log_status(domain, step, status):
    with lock:
        key = f"{domain}::{step}"
        statuses[key] = status

def print_status(domains, steps, scan_name):
    with lock:
        os.system('cls' if os.name == 'nt' else 'clear')

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

def print_all_workflows_status(workflow_configs, all_domains):
    """Print status for all workflows running in parallel"""
    with lock:
        os.system('cls' if os.name == 'nt' else 'clear')
        
        for config in workflow_configs:
            scan_name = config.get('name', 'Unknown Scan')
            pipeline = config['pipeline']
            
            print(f"Scan Progress ({scan_name}):\n")
            
            for domainx in all_domains:
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
            for domainx in all_domains:
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

def scan_domain(domain, pipeline, date_str, skip_if_any_result=True):
    firstdomain = domain 
    domain = check_cidr(domain)   

    global resolved_paths_cache
    resolved_paths_cache.setdefault(domain, {})

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
                else:
                    print(f"⚠️ Warning: Reference '{placeholder}' not found for domain {domain} in step {name}. Command might be invalid.")        

        if actual_output_file_path:
            cmd = cmd.replace("{output_file}", actual_output_file_path)

        if skip_if_any_result and is_any_result_exists(domain, step):
            log_status(domain, name, "skipped")
            print(f">> [{name}] skipped for domain: {domain} (any result already exists)")
            continue

        if actual_output_file_path and is_output_valid(actual_output_file_path, domain):
            log_status(domain, name, "skipped")
            print(f">> [{name}] skipped for domain: {domain} (output already exists)")
            continue

        log_status(domain, name, "running")

        run_command(cmd)

        log_status(domain, name, "done")

def worker(domains, pipeline, scan_name, date_str, skip_if_any_result=True, all_workflows=None, all_domains=None):
    threads = []
    for domain in domains:
        t = threading.Thread(target=scan_domain, args=(domain, pipeline, date_str, skip_if_any_result))
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
    """Get list of available workflow names"""
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
    """Display all available workflow names"""
    workflows = get_workflow_names()
    
    if not workflows:
        print("❌ No workflow files found in scans-wf/ directory!")
        return
    
    print("\n📋 Available Workflows:")
    print("=" * 60)
    
    for i, workflow in enumerate(workflows, 1):
        print(f"{i:2d}. {workflow['name']}")
        print(f"    📁 File: {workflow['file']}")
        print(f"    📝 Description: {workflow['description']}")
        print()
    
    print("💡 Usage:")
    print("  python sebat.py -wf workflow-name -t targets.txt")
    print("  python sebat.py -wf workflow1,workflow2 -t targets.txt")
    print("  python sebat.py -t targets.txt  (runs all workflows)")

def load_workflows_by_names(workflow_names):
    """Load specific workflows by name"""
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
                print(f"❌ Error loading workflow '{name}': {e}")
        else:
            print(f"❌ Workflow '{name}' not found!")
            print(f"💡 Available workflows: {', '.join(available_names.keys())}")
    
    return configs

def find_latest_scan_date():
    """Find the most recent scan date from existing results"""
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
    """Display current scan results for a specific date"""
    results_dir = Path("results-scan")
    if not results_dir.exists():
        print("❌ No results-scan directory found!")
        return
    
    print(f"\n📊 Scan Results for Date: {date_str}")
    print("=" * 60)
    
    found_results = False
    total_files = 0
    
    for domain_dir in sorted(results_dir.iterdir()):
        if domain_dir.is_dir():
            domain_name = domain_dir.name
            domain_has_results = False
            
            print(f"\n🌐 Domain: {domain_name}")
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
                                    
                                    print(f"  📁 {category_name}/{tool_name}/")
                                    print(f"      📄 {file_path.name} ({size_str})")
                                    
                                    try:
                                        with open(file_path, 'r', encoding='utf-8') as f:
                                            lines = f.readlines()[:5] 
                                            if lines:
                                                print("      📝 Content preview:")
                                                for line in lines:
                                                    print(f"         {line.rstrip()}")
                                                if len(f.readlines()) > 5:
                                                    print("         ... (more content)")
                                    except Exception as e:
                                        print(f"      ⚠️  Could not read file: {e}")
                                    
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
                                
                                print(f"  📁 {category_name}/")
                                print(f"      📄 {file_path.name} ({size_str})")
                                print()
                                domain_has_results = True
                                found_results = True
                                total_files += 1
            
            if not domain_has_results:
                print("  ❌ No results found for this domain")
    
    if not found_results:
        print(f"❌ No scan results found for date: {date_str}")
        print("💡 Try running a scan first or check a different date")
    else:
        print(f"\n✅ Found {total_files} result files for {date_str}")
        print("💡 Use 'python sebat.py -ccr latest' to check the most recent results")

def main():
    parser = argparse.ArgumentParser(description="Dynamic YAML-based scan runner")
    parser.add_argument("-t", "--targets", help="Target domains file")
    parser.add_argument("-pt", "--parallel-targets", type=int, default=3, help="Number of targets to process in parallel")
    parser.add_argument("-pw", "--parallel-workflows", type=int, default=1, help="Number of workflows to process in parallel")
    parser.add_argument("-rs", "--rescan", action="store_true", help="Force re-scan all steps (ignore existing results)")
    parser.add_argument("-sn", "--show-names", action="store_true", help="Show available workflow names")
    parser.add_argument("-wf", "--workflow", help="Specific workflow name(s), comma-separated (e.g., workflow1,workflow2)")
    args = parser.parse_args()

    if args.show_names:
        show_workflow_names()
        return

    if not args.targets:
        parser.error("Targets file (-t) is required for scanning. Use -sn to show available workflows.")

    with open(args.targets) as f:
        all_domains = [line.strip() for line in f if line.strip()]

    if args.workflow:
        workflow_names = [name.strip() for name in args.workflow.split(',')]
        configs = load_workflows_by_names(workflow_names)
        if not configs:
            print("❌ No valid workflows specified. Use -sn to see available workflows.")
            return
    else:
        configs = load_configs("scans-wf/")
        if not configs:
            print("❌ No workflow files found in scans-wf/ directory!")
            return

    date_str = datetime.now().strftime("%Y-%m-%d")

    # Process workflows in parallel
    def run_workflow(config, is_parallel_workflows=False):
        if not is_parallel_workflows:
            os.system('cls' if os.name == 'nt' else 'clear')
            current_scan_name = config.get('name', 'Unknown Scan')
            print(f"\n=== Running scan: {current_scan_name} ({config['__file']}) ===")
        
        pipeline = config['pipeline']

        # Create directories for all domains and steps
        for domain in all_domains:
            domain_checked = check_cidr(domain)
            for step in pipeline:
                out_path = get_output_path(domain_checked, step, date_str)
                Path(os.path.dirname(out_path)).mkdir(parents=True, exist_ok=True)

        global resolved_paths_cache
        resolved_paths_cache = {}

        # Initialize status for all domains and steps
        for domain in all_domains:
            domain_checked = check_cidr(domain)
            for step in pipeline:
                log_status(domain_checked, step["name"], "waiting...")

        # Process targets in parallel for this workflow
        for i in range(0, len(all_domains), args.parallel_targets):
            batch = all_domains[i:i + args.parallel_targets]
            skip_logic = not args.rescan
            
            # Pass workflow info for parallel display
            if is_parallel_workflows:
                worker(batch, pipeline, config.get('name', 'Unknown Scan'), date_str, skip_logic, configs, all_domains)
            else:
                worker(batch, pipeline, config.get('name', 'Unknown Scan'), date_str, skip_logic)

    # Run workflows in parallel if specified
    if args.parallel_workflows > 1 and len(configs) > 1:
        print(f"\n🚀 Running {len(configs)} workflows with {args.parallel_workflows} parallel workflows")
        
        workflow_threads = []
        for i in range(0, len(configs), args.parallel_workflows):
            batch_configs = configs[i:i + args.parallel_workflows]
            for config in batch_configs:
                t = threading.Thread(target=run_workflow, args=(config, True))  # True for parallel workflows
                t.start()
                workflow_threads.append(t)
            
            # Wait for current batch to complete before starting next batch
            for t in workflow_threads:
                t.join()
            workflow_threads = []
    else:
        # Run workflows sequentially
        for config in configs:
            run_workflow(config, False)  # False for sequential workflows

    print("\n>> All scans completed.")

if __name__ == "__main__":
    main()