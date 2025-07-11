# Sebatch 
> Sebatch (batching scan) is made for those who like to multitask. One cigarette 🚬, and wait for fuck*ng scans done!

The ‘oneliner runner’ tool lets you run multiple security scans in parallel across multiple domains. Perfect for security researchers, penetration testers, and bug hunters who want to maximize their scanning efficiency. It's actually a more managed development of oneliner. So just enter your flagship oneliner as the scan workflow config and run scans in parallel.

## 🚀 Features

- **Parallel Processing**: Run multiple domains simultaneously
- **YAML Configuration**: Easy-to-write scan workflows
- **Organized Output**: Automatic directory structure with date-based naming
- **Skip Existing Results**: Smart caching to avoid re-scanning
- **Real-time Progress**: Live status updates during scanning
- **Flexible Categories**: Group tools by category (subdomain, vuln-scanner, etc.)


## 🛠️ Installation

1. **Clone the repository:**
   ```
   git clone https://github.com/yourusername/sebatch.git
   cd sebatch
   ```

2. **Install Python dependencies:**
   ```
   pip install pyyaml
   ```

## 📝 Usage

### Basic Usage

1. **Create a targets file:**
   ```
   echo "example.com" > targets.txt
   echo "test.org" >> targets.txt
   echo "demo.net" >> targets.txt
   ```

2. **Run a single workflow:**
   ```
   python sebat.py -c scans-wf/sample-workflow.yaml -t targets.txt
   ```

3. **Run all workflows:**
   ```
   python sebat.py --all -t targets.txt
   ```

### Advanced Usage

```
# Run with custom parallel processing (default: 3)
python sebat.py -c scans-wf/sample-workflow.yaml -t targets.txt -p 5

# Run all workflows with 10 parallel domains
python sebat.py --all -t targets.txt -p 10
```

## 📋 Command Line Options

| Option | Description | Required |
|--------|-------------|----------|
| `-c, --config` | YAML configuration file | Yes (unless using --all) |
| `-t, --targets` | File containing target domains | Yes |
| `-p, --parallel` | Number of domains to process in parallel | No (default: 3) |
| `--all` | Run all YAML configs in scans-wf/ | No |

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
    output_file: # You can leave blank, default: result will be saved in result-scan/{cat_base}/{pipeline_name}/{domain}-{output_file}
    command: subfinder -silent -d {domain} -o {output_file}
  
  - name: httpx
    output_file:
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


## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add your workflow configurations
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [ProjectDiscovery](https://projectdiscovery.io/) for amazing security tools
- [Awesome One-liner Bug Bounty](https://github.com/dwisiswant0/awesome-oneliner-bugbounty)
- The bug bounty community for inspiration and feedback

---

**Happy scanning! 🚬💨 Remember: One cigarette, and wait scans done!** 
