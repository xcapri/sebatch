# Sebatch 
> Sebatch (batching scan) is made for those who like to multitask. One cigarette 🚬, and wait scans done!** 

The 'oneliner runner' tool lets you run multiple security scans in parallel across multiple domains. Perfect for security researchers, penetration testers, and bug hunters who want to maximize their scanning efficiency. It's actually a more managed development of oneliner. So just enter your flagship oneliner as the scan workflow config and run scans in parallel.

## 🚀 Features

- **Parallel Processing**: Run multiple domains simultaneously
- **YAML Configuration**: Easy-to-write scan workflows
- **Organized Output**: Automatic directory structure with date-based naming
- **Smart Skipping**: Automatically skips steps with existing results (by default)
- **Selective Re-scan**: Use `-rs STEP_NAME` to re-run specific steps and all steps after them
- **Force Re-scan**: Use `-rs` flag to re-run all steps regardless of existing results
- **Automatic Previous Scan Detection**: Automatically finds and uses output files from previous scans
- **Real-time Progress**: Live status updates during scanning
- **Complete Output Display**: See full command output in real-time without truncation
- **Flexible Categories**: Group tools by category (subdomain, vuln-scanner, etc.)
- **Log Management**: Built-in log reader and log clearing functionality
- **Modular Workflows**: Create workflows that reference outputs from other workflows

## 👀 Show Case

![Sebatch Showcase](docs/sc.png)

## 🛠️ Installation

1. **Clone the repository:**
   ```
   git clone https://github.com/xcapri/sebatch.git
   cd sebatch
   ```

2. **Install Python dependencies:**
   ```
    # create virtual environment
    python3 -m venv venv

    # Activated virtual environment
    source venv/bin/activate

    # Install all packages from requirements.txt
    pip3 install -r requirements.txt
   ```

## 📝 Quick Start

### 1. Create a targets file
```
echo "example.com" > targets.txt
echo "test.org" >> targets.txt
```

### 2. Show available workflows
```
python3 sebat.py -sn
```

### 3. Run a workflow
```
python3 sebat.py -wf sample-workflow -t targets.txt
```

### 4. Run with selective rescan
```
python3 sebat.py -rs nuclei -wf sample-workflow -t targets.txt
```

> 💡 **Need more examples?** Check out the **[Technical Guide](docs/technical-guide.md)** for advanced usage, workflow templates, and troubleshooting tips.

## 🔄 Key Features Explained

### Selective Re-scan
Re-run only specific steps without executing the entire pipeline:
- `-rs nuclei` - Re-run nuclei and all steps after it
- `-rs step1,step2` - Re-run multiple specific steps
- `-rs` - Re-run all steps

### Modular Workflows
Create focused workflows that use outputs from previous scans:
```yaml
name: nuclei-only
pipeline:
  - name: nuclei
    command: cat subfinder.output_file | nuclei -silent -o {output_file}
```

### Real-time Output
See complete command output in real-time without truncation for better monitoring and debugging.

## 📚 Documentation

### 📖 [Technical Guide](docs/technical-guide.md)
Complete technical reference including:
- **Command Line Options** - All available flags and parameters
- **Advanced Usage Examples** - Complex command combinations
- **YAML Configuration** - Detailed workflow configuration guide
- **Selective Re-scan** - Complete feature documentation
- **Modular Workflows** - How to create and use modular workflows
- **Troubleshooting** - Common issues and solutions
- **Performance Optimization** - Best practices for optimal usage

### 🔗 Quick Links
- **[Workflow Examples](docs/technical-guide.md#creating-custom-workflows)** - Ready-to-use workflow templates
- **[Troubleshooting Guide](docs/technical-guide.md#troubleshooting)** - Common issues and solutions
- **[Command Reference](docs/technical-guide.md#command-line-options)** - Complete CLI documentation

## 🤝 Contributing

> I'm sure you have your own kitchen secrets. Feel free to put them into a workflow; Sebatch will help run it. However, if you want to share directly, please make a Pull Request.

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
