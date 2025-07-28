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

#### ⚡ **Performance & Concurrency**
- `-pt, --parallel-targets`: Control how many domains are processed simultaneously
- `-pw, --parallel-workflows`: Control how many workflows run in parallel

#### 🔄 **Rescan & Control**
- `-rs, --rescan`: Force re-execution of steps (all or specific -rs subfinder,nuclei)
- Smart mode (default): Skip steps with existing results (without -rs arg)
- Force mode: Re-run all steps regardless of existing results
- Selective mode: Re-run specific steps and all steps after them

#### 📊 **Monitoring & Logging**
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

#### Workflow Discovery
```bash
# List all available workflows
python sebat.py -sn
```