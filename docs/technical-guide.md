# Sebatch Technical Guide

This document contains detailed technical information, command examples, and advanced usage patterns for Sebatch.


## 📋 Command Line Options

| Option | Description | Required | Default | Example |
|--------|-------------|----------|---------|---------|
| `-t, --targets` | File containing target domains (supports CIDR notation) | Yes* | - | `-t targets.txt` |
| `-pt, --parallel-targets` | Number of targets to process in parallel | No | 3 | `-pt 5` |
| `-pw, --parallel-workflows` | Number of workflows to process in parallel | No | 1 | `-pw 2` |
| `-rs, --rescan [STEP]` | Force re-scan. Use `-rs` for all steps, or `-rs STEP_NAME` for specific step(s) | No | - | `-rs nuclei` |
| `-sn, --show-names` | Show available workflow names and descriptions | No | - | `-sn` |
| `-sw, --show-workflow` | Show beautiful ASCII workflow diagram for specific workflow | No | - | `-sw workflow-name` |
| `-wf, --workflow` | Specific workflow name(s), comma-separated | No | All workflows | `-wf workflow1,workflow2` |
| `-v, --verbose [SID]` | Show logs in real-time. Use `-v` for all logs or `-v SID` for specific scan | No | - | `-v` or `-v 12345` |
| `-vl, --view-logs` | List available log files with size and scan information | No | - | `-vl` |
| `-cl, --clear-logs` | Clear all debug log files | No | - | `-cl` |

*Required for scanning operations, not required for `-sn`, `-v`, `-vl`, or `-cl` options.

### Command Categories

#### 🔍 **Scanning Commands**
- `-t, --targets`: Specify the file containing target domains or IP ranges
- `-wf, --workflow`: Select specific workflows to run (comma-separated)
- `-sn, --show-names`: List all available workflows with descriptions
- `-sw, --show-workflow`: Display beautiful ASCII workflow diagram for specific workflow

#### ⚡ **Performance & Concurrency**
- `-pt, --parallel-targets`: Control how many domains are processed simultaneously
- `-pw, --parallel-workflows`: Control how many workflows run in parallel

## 📋 Workflow Template Guide

Sebatch workflows are defined using YAML configuration files. Each workflow file contains a structured pipeline of security scanning steps that can be executed in parallel or sequentially.

### Basic Workflow Structure

```yaml
name: workflow-name
reference: https://example.com/reference
description: Brief description of what this workflow does
pipeline:
  - name: step-name
    cat_base: category-name
    output_file: optional-filename
    command: your-command-here
```

### Workflow Components Explained

#### **Top-Level Properties**

| Property | Required | Description | Example |
|----------|----------|-------------|---------|
| `name` | ✅ Yes | Unique identifier for the workflow | `sample-workflow` |
| `reference` | ❌ No | URL or reference to the original source | `vulnshot.com/sample/blog/post` |
| `description` | ❌ No | Human-readable description of the workflow | `Subdomain Enumeration and Vulnerability Scanning` |
| `pipeline` | ✅ Yes | Array of scanning steps to execute | See pipeline section below |

#### **Pipeline Step Properties**

| Property | Required | Description | Example |
|----------|----------|-------------|---------|
| `name` | ✅ Yes | Unique identifier for this step within the workflow | `subfinder`, `nuclei` |
| `cat_base` | ❌ No | Category for organizing output files | `subdomain`, `vuln-scanner`, `fuzzing` |
| `output_file` | ❌ No | Custom filename prefix (optional) | `subdomains.txt`, `vulnerabilities.txt` |
| `command` | ✅ Yes | The actual command to execute | `subfinder -silent -d {domain}` |

### Output File System

#### **Automatic File Naming**
When `output_file` is not specified or left blank, Sebatch automatically generates filenames:

```
results-scan/
└── {domain}/
    └── {cat_base}/
        └── {step_name}/
            └── scan-at-{date}-{time}
```

**Example:**
```
results-scan/
└── example.com/
    └── subdomain/
        └── subfinder/
            └── scan-at-2024-01-15-143022
```

#### **Custom File Naming**
When `output_file` is specified, the format becomes:

```
results-scan/
└── {domain}/
    └── {cat_base}/
        └── {step_name}/
            └── scan-at-{date}-{output_file}
```

**Example with `output_file: subdomains.txt`:**
```
results-scan/
└── example.com/
    └── subdomain/
        └── subfinder/
            └── scan-at-2024-01-15-subdomains.txt
```

### Command Templates

#### **Available Placeholders**

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{domain}` | The target domain being scanned | `example.com` |
| `{output_file}` | The full path to the output file | `/path/to/results-scan/example.com/subdomain/subfinder/scan-at-2024-01-15` |
| `{step_name}.output_file` | Reference to output file from a previous step | `subfinder.output_file` |
| `{step_name}.output_file*` | Wildcard reference to multiple output files | `subfinder.output_file*` |

#### **Command Examples**

```yaml
# Basic command with domain placeholder
- name: subfinder
  command: subfinder -silent -d {domain} | anew {output_file}

# Command using output from previous step
- name: httpx
  command: cat subfinder.output_file | httpx -silent -sc -fr -title

# Command with wildcard file reference
- name: nuclei
  command: cat subfinder.output_file* | nuclei -silent -tags git

# Multi-line command
- name: notify
  command: |
    cat nuclei.output_file | notify -silent -bulk
```

### Category Organization (`cat_base`)

The `cat_base` property helps organize your scan results into logical categories:

#### **Common Categories**

You can group tools based on their functions with the name cat_base, for example by grouping tools for subdomain recon, tools for finding known URLs, and tools for scanning. For example:

- `subdomain` - Subdomain enumeration results
- `vuln-scanner` - Vulnerability scanning results
- `port-scanner` - Port scanning results
- `recon` - Reconnaissance results
- `notify` - Notification logs

#### **Category Structure**
```
results-scan/
└── example.com/
    ├── subdomain/          # cat_base: subdomain
    │   ├── subfinder/
    │   └── assetfinder/
    ├── vuln-scanner/       # cat_base: vuln-scanner
    │   ├── nuclei/
    │   └── httpx/
    └── notify/ 
```

### Step Dependencies & Execution Order

#### **Automatic Dependency Detection**
Sebatch automatically detects when steps depend on previous steps by analyzing command references:

```yaml
pipeline:
  - name: subfinder
    command: subfinder -silent -d {domain} | anew {output_file}
  
  - name: httpx
    command: cat subfinder.output_file | httpx -silent  # Depends on subfinder
    # This step will wait for subfinder to complete
  
  - name: nuclei
    command: cat httpx.output_file | nuclei -silent     # Depends on httpx
    # This step will wait for httpx to complete
```

#### **Parallel Execution**
Steps without dependencies can run in parallel within the same category:

```yaml
pipeline:
  - name: subfinder
    cat_base: subdomain
    command: subfinder -silent -d {domain} | anew {output_file}
  
  - name: assetfinder
    cat_base: subdomain
    command: assetfinder --subs-only {domain} | anew {output_file}
    # This runs in parallel with subfinder (same cat_base, no dependencies)
  
  - name: httpx
    cat_base: vuln-scanner
    command: cat subfinder.output_file | httpx -silent
    # This waits for subfinder to complete
```

### Complete Workflow Example

```yaml
name: comprehensive-scan
reference: https://github.com/xcapri/sebatch
description: Complete subdomain enumeration and vulnerability scanning workflow
pipeline:
  # Subdomain Enumeration (Parallel)
  - name: subfinder
    cat_base: subdomain
    output_file: subdomains.txt
    command: subfinder -silent -d {domain} | anew {output_file}

  - name: assetfinder
    cat_base: subdomain
    output_file: assets.txt
    command: assetfinder --subs-only {domain} | anew {output_file}

  - name: dnsgen
    cat_base: subdomain
    output_file: generated.txt
    command: echo {domain} | dnsgen - | anew {output_file}

  # HTTP Discovery (Depends on subdomain enumeration)
  - name: httpx
    cat_base: vuln-scanner
    output_file: live-hosts.txt
    command: cat subfinder.output_file | httpx -silent -sc -fr -title -cname -cl | anew {output_file}

  # Vulnerability Scanning (Depends on HTTP discovery)
  - name: nuclei
    cat_base: vuln-scanner
    output_file: vulnerabilities.txt
    command: cat httpx.output_file | nuclei -tags git -silent -nc -nh | anew {output_file}

  # Notification (Depends on vulnerability scanning)
  - name: notify
    cat_base: 
    output_file: 
    command: |
      cat nuclei.output_file | notify -silent -bulk
```

### Best Practices

#### **1. Naming Conventions**
- Use descriptive step names: `subfinder`, `nuclei`, `httpx`
- Use meaningful categories: `subdomain`, `vuln-scanner`, `recon`
- Use clear output file names: `subdomains.txt`, `vulnerabilities.txt`

#### **2. Command Structure**
- Always use `{output_file}` to save results
- Reference previous steps with `{step_name}.output_file`

#### **3. Performance Optimization**
- Group independent steps in the same `cat_base` for parallel execution
- Use -pt for parallel targets in each workflow
- Use -pw for parallel workflows across multiple targets, each workflow

#### **4. Output Organization**
- Use meaningful `cat_base` values for logical grouping
- Use descriptive `output_file` names for easy identification
- Keep related steps in the same category

#### 🔄 **Rescan & Control**
- `-rs, --rescan`: Force re-execution of steps (all or specific -rs subfinder,nuclei)
- Smart mode (default): Skip steps with existing results (without -rs arg)
- Force mode: Re-run all steps regardless of existing results
- Selective mode: Re-run specific steps and all steps after them

#### 📊 **Monitoring & Logging**

Use this flag to see what is happening in the backend.

- `-v, --verbose`: Real-time log viewing with optional scan ID filtering
- `-vl, --view-logs`: Display log file information and scan statistics
- `-cl, --clear-logs`: Clean up log files to free disk space

### Command Usage Examples

#### Basic Scanning
```bash
# Run all workflows on targets
python sebat.py -t targets.txt

# Run specific workflow
python sebat.py -wf sample-workflow -t targets.txt

# Run multiple workflows
python sebat.py -wf workflow1,workflow2 -t targets.txt
```

#### Performance Tuning
```bash
# Increase parallel targets (default: 3)
python sebat.py -t targets.txt -pt 10

# Run workflows in parallel (default: 1)
python sebat.py -t targets.txt -pw 3

# Combine both for maximum performance
python sebat.py -t targets.txt -pt 5 -pw 2
```

#### Rescan Operations
```bash
# Force rescan all steps
python sebat.py -rs -wf sample-workflow -t targets.txt

# Rescan specific step and all steps after it
python sebat.py -rs nuclei -wf sample-workflow -t targets.txt

# Rescan multiple specific steps
python sebat.py -rs nuclei,notify -wf sample-workflow -t targets.txt
```

#### Log Management
```bash
# View all logs in real-time
python sebat.py -v

# View logs for specific scan ID
python sebat.py -v 12345

# List log files and their information
python sebat.py -vl

# Clear all log files
python sebat.py -cl
```

#### Workflow Discovery & Visualization
```bash
# List all available workflows
python sebat.py -sn

# Show workflow diagram for specific workflow
python sebat.py -sw sample-workflow

# Show workflow diagram for any workflow
python sebat.py -sw workflow-name
```