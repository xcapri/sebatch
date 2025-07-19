# Sebatch Technical Guide

This document contains detailed technical information, command examples, and advanced usage patterns for Sebatch.

## 📋 Command Line Options

| Option | Description | Required |
|--------|-------------|----------|
| `-t, --targets` | File containing target domains | Yes* |
| `-pt, --parallel-targets` | Number of targets to process in parallel | No (default: 3) |
| `-pw, --parallel-workflows` | Number of workflows to process in parallel | No (default: 1) |
| `-rs, --rescan [STEP]` | Force re-scan. Use `-rs` for all steps, or `-rs STEP_NAME` for specific step(s) | No |
| `-sn, --show-names` | Show available workflow names | No |
| `-wf, --workflow` | Specific workflow name(s), comma-separated | No (runs all if not specified) |
| `-v, --verbose` | Show logs in real-time (log reader mode) | No |
| `-cl, --clear-logs` | Clear all debug log files | No |

*Required for scanning operations, not required for `-sn`, `-v`, or `-cl` options.

## 🚀 Advanced Usage Examples

### Basic Commands

```bash
# Run with custom parallel targets (default: 3)
python sebat.py -wf sample-workflow -t targets.txt -pt 5

# Run all workflows with 10 parallel targets
python sebat.py -t targets.txt -pt 10

# Run multiple workflows in parallel (2 workflows at once)
python sebat.py -wf workflow1,workflow2 -t targets.txt -pw 2

# Run all workflows with parallel targets and workflows
python sebat.py -t targets.txt -pt 5 -pw 3
```

### Re-scan Functionality

```bash
# Force re-scan all steps (ignore existing results)
python sebat.py -rs -wf sample-workflow -t targets.txt

# Selective re-scan: re-run only nuclei step and all steps after it
python sebat.py -rs nuclei -wf sample-workflow -t targets.txt

# Selective re-scan: re-run multiple specific steps
python sebat.py -rs nuclei,notify -wf sample-workflow -t targets.txt

# Run modular workflow that uses outputs from previous scans
python sebat.py -wf nuclei-only -t targets.txt
```

### Log Management

```bash
# View logs in real-time (log reader mode)
python sebat.py -v

# Clear all debug log files
python sebat.py -cl
```

## 📄 YAML Workflow Configuration

### Basic Structure

```yaml
name: My Security Scan
reference: https://example.com/blog/post
pipeline:
  - name: subfinder
    cat_base: subdomain
    output_file: # Optional prefix
    command: subfinder -silent -d {domain} -o {output_file}
  
  - name: nuclei
    cat_base: vuln-scanner
    output_file: # Optional prefix
    command: nuclei -tags xss,sqli -silent -l subfinder.output_file -o {output_file}
```

### Configuration Options

| Field | Description | Required |
|-------|-------------|----------|
| `name` | Workflow name | Yes |
| `reference` | Reference URL or documentation | No |
| `pipeline` | List of scanning steps | Yes |
| `cat_base` | Category for organizing results | No |
| `output_file` | Optional prefix for output files | No |
| `command` | Command to execute | Yes |

### Special Placeholders

- `{domain}` - Passing Target domain
- `{output_file}` - Generated output file path (default: result will be saved in result-scan/{cat_base}/{pipeline_name}/{domain}-{output_file})
- `{step_name}.output_file` - Reference to previous step's output

## 🔄 Selective Re-scan Feature

Sebatch supports selective re-scanning, allowing you to re-run specific steps without executing the entire pipeline:

### Usage Examples

```bash
# Re-run only the nuclei step and all steps after it
python sebat.py -rs nuclei -wf sample-workflow -t targets.txt

# Re-run multiple specific steps
python sebat.py -rs nuclei,notify -wf sample-workflow -t targets.txt

# Re-run all steps (traditional behavior)
python sebat.py -rs -wf sample-workflow -t targets.txt
```

### How It Works

- **Single Step**: `-rs nuclei` will execute `nuclei` and any steps that come after it in the pipeline
- **Multiple Steps**: `-rs step1,step2` will execute only the specified steps
- **All Steps**: `-rs` (without step name) will execute all steps
- **Smart Skipping**: Steps before the target step are completely skipped

## 🔗 Modular Workflows

Create workflows that reference outputs from previous scans, even if those steps don't exist in the current workflow:

### Example: Nuclei-Only Workflow

```yaml
name: nuclei-only
pipeline:
  - name: nuclei
    cat_base: scanner
    command: cat subfinder.output_file dnsgen.output_file analyticsrelationships.output_file | nuclei -itags cve,git,env,password,xss,backup,file,default,form,redirect,debug,origin,panel -o {output_file} -silent

  - name: notify
    command: cat nuclei.output_file | notify -silent -bulk
```

### How It Works

- **Automatic Detection**: When a workflow references `{step_name}.output_file` but that step doesn't exist in the current workflow, Sebatch automatically searches for output files from previous scans
- **Smart Resolution**: It finds the most recent scan files for that step and uses them
- **Clear Logging**: Provides detailed information about which files were found and used
- **Error Handling**: Warns when required files can't be found

### Benefits

- **Modular Design**: Create focused workflows for specific tasks
- **Reuse Results**: Leverage outputs from previous comprehensive scans
- **Efficiency**: Skip expensive steps when you only need specific results
- **Flexibility**: Mix and match workflow components as needed

## 📊 Output Structure

Results are automatically organized by domain and category:
Its flexible based on your scans-workflow configuration.

```
results-scan/
└── example.com/
    ├── subdomain/
    │   ├── subfinder/
    │   │   └── scan-at-2024-06-08
    │   └── subdosec/
    │       └── scan-at-2024-06-08
    ├── vuln-scanner/
    │   └── nuclei/
    │       └── scan-at-2024-06-08
    ├── httpx/
    │   └── scan-at-2024-06-08
    └── notify/
        └── scan-at-2024-06-08
```

## 🔧 Creating Custom Workflows

### Example: Subdomain Enumeration + Vulnerability Scanning

```yaml
name: Subdomain Recon + Vuln Scan
pipeline:
  - name: subfinder
    cat_base: subdomain
    command: subfinder -silent -d {domain} -o {output_file}
  
  - name: httpx
    output_file: # use output_file to custom prefix
    cat_base: web # you can leave blank
    command: cat subfinder.output_file | httpx -silent -o {output_file}
  
  - name: nuclei
    cat_base: vuln-scanner
    command: cat httpx.output_file | nuclei -silent -o {output_file}

  - name: testcommand
    cat_base: vuln-scanner
    command: |
    echo {domain} | another command | another command &&
    cat httpx.output_file | nuclei -silent -o {output_file}

    .. add more tools 
```

### Example: Modular Vulnerability Scanning

Create a focused workflow that uses outputs from previous comprehensive scans:

```yaml
name: quick-vuln-scan
pipeline:
  - name: nuclei
    cat_base: vuln-scanner
    command: cat subfinder.output_file httpx.output_file | nuclei -tags xss,sqli,rce -silent -o {output_file}
  
  - name: notify
    command: cat nuclei.output_file | notify -silent -bulk
```

### Example: Multi-Tool Analysis

```yaml
name: comprehensive-analysis
pipeline:
  - name: analyticsrelationships
    cat_base: subdomain
    command: analyticsrelationships --url {domain} | awk '{print $2}' | httpx -silent | turut | grep -v amazonaws.com | tee -a {output_file}
  
  - name: subfinder
    cat_base: subdomain
    command: cat analyticsrelationships.output_file | subfinder -rl 1 -silent -o {output_file}
  
  - name: dnsgen
    cat_base: subdomain
    command: cat subfinder.output_file | dnsgen - | tee -a {output_file}
  
  - name: nuclei
    cat_base: scanner
    command: cat subfinder.output_file dnsgen.output_file analyticsrelationships.output_file | nuclei -itags cve,git,env,password,xss,backup,file,default,form,redirect,debug,origin,panel -o {output_file} -silent
  
  - name: notify
    command: cat nuclei.output_file | notify -silent -bulk
```

## 🛠️ Troubleshooting

### Common Issues

1. **Command not found errors**: Ensure all required tools are installed and in your PATH
2. **Permission errors**: Check file permissions for output directories
3. **Missing output files**: Verify that previous scan steps completed successfully
4. **Invalid step names**: Use `-sn` to see available workflow names and steps

### Debug Mode

Use verbose logging to troubleshoot issues:

```bash
# Enable verbose logging
python sebat.py -v

# Check logs in real-time
tail -f debug/sebatch_verbose_YYYYMMDD.log
```

### Performance Optimization

- Adjust `-pt` (parallel targets) based on your system resources
- Use `-rs` selectively to avoid unnecessary re-scanning
- Consider using modular workflows for focused tasks 