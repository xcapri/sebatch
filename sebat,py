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

def run_command(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def is_output_valid(output_path_template, domain):
    if output_path_template == "null":
        return False

    # For the new path structure, output_path_template is already resolved
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
    cat_base = step.get("cat_base", "").strip()
    step_name = step["name"]
    output_file = step.get("output_file", "").strip()
    # Build directory path
    parts = ["results-scan", domain]
    if cat_base:
        parts.append(cat_base)
    parts.append(step_name)
    dir_path = os.path.join(*parts)
    # Build file name
    if output_file:
        file_name = f"scan-at-{date_str}-{output_file}"
    else:
        file_name = f"scan-at-{date_str}"
    return os.path.join(dir_path, file_name)

def scan_domain(domain, pipeline, date_str):
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

        if actual_output_file_path and is_output_valid(actual_output_file_path, domain):
            log_status(domain, name, "skipped")
            print(f"⏩ [{name}] skipped for domain: {domain} (output already exists)")
            continue

        log_status(domain, name, "running")

        run_command(cmd)

        log_status(domain, name, "done")

def worker(domains, pipeline, scan_name, date_str):
    threads = []
    for domain in domains:
        t = threading.Thread(target=scan_domain, args=(domain, pipeline, date_str))
        t.start()
        threads.append(t)

    print_status(domains, pipeline, scan_name)

    last_print = time.time()
    while any(t.is_alive() for t in threads):
        now = time.time()
        if now - last_print > 1:
            print_status(domains, pipeline, scan_name)
            last_print = now
        time.sleep(0.1)

    print_status(domains, pipeline, scan_name)

def load_configs(path):
    configs = []
    for yaml_path in Path(path).glob("*.yaml"):
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
            config['__file'] = yaml_path
            configs.append(config)
    return configs

def main():
    parser = argparse.ArgumentParser(description="Dynamic YAML-based scan runner")
    parser.add_argument("-c", "--config", help="YAML config file")
    parser.add_argument("-t", "--targets", required=True, help="Target domains file")
    parser.add_argument("-p", "--parallel", type=int, default=3, help="Domains per batch")
    parser.add_argument("--all", action="store_true", help="Run all YAML configs in scans-wf/")
    args = parser.parse_args()

    if args.all and args.config:
        parser.error("You cannot use --all and --config together")

    if not args.all and not args.config:
        parser.error("You must specify either --all or --config")

    with open(args.targets) as f:
        all_domains = [line.strip() for line in f if line.strip()]

    if args.all:
        configs = load_configs("scans-wf/")
    else:
        with open(args.config) as f:
            config = yaml.safe_load(f)
            config['__file'] = args.config
            configs = [config]

    date_str = datetime.now().strftime("%Y-%m-%d")

    for config in configs:
        os.system('cls' if os.name == 'nt' else 'clear')
        current_scan_name = config.get('name', 'Unknown Scan')
        print(f"\n=== Running scan: {current_scan_name} ({config['__file']}) ===")
        pipeline = config['pipeline']

        # Create all necessary directories for each domain and step
        for domain in all_domains:
            domain_checked = check_cidr(domain)
            for step in pipeline:
                out_path = get_output_path(domain_checked, step, date_str)
                Path(os.path.dirname(out_path)).mkdir(parents=True, exist_ok=True)

        global resolved_paths_cache
        resolved_paths_cache = {}

        for domain in all_domains:
            domain_checked = check_cidr(domain)
            for step in pipeline:
                log_status(domain_checked, step["name"], "waiting...")

        for i in range(0, len(all_domains), args.parallel):
            batch = all_domains[i:i + args.parallel]
            worker(batch, pipeline, current_scan_name, date_str)

    print("\n✅ All scans completed.")

if __name__ == "__main__":
    main()