# iris-fmriprep Configuration Generator

A web-based tool for generating YAML configuration files for iris-fmriprep processing. This tool helps users create properly formatted configuration files by providing an intuitive interface for mapping scan names to BIDS-compliant naming conventions and configuring fMRIPrep processing options.

## Features

### 🧠 **Intelligent Scan Processing**
- **Directory scanning**: Point to a directory and automatically detect neuroimaging files
- **Smart scan selection**: Implements iris-fmriprep's `final_scan()` logic to show only the scans that will actually be processed
- **Multi-echo support**: Automatically detects and handles multi-echo sequences
- **Auto-ignore**: Automatically ignores scout and localizer scans by default

### 📝 **BIDS Naming Configuration**
- **Automatic suggestions**: Provides intelligent BIDS name suggestions based on scan names
- **Real-time validation**: Validates BIDS names as you type with helpful error messages
- **Category organization**: Automatically categorizes scans into anatomical, functional, fieldmap, and DWI types
- **Ignore functionality**: Easy checkboxes to exclude scans from processing

### ⚙️ **fMRIPrep Options**
- **iris-fmriprep compatibility**: Supports the fMRIPrep processing options available through iris-fmriprep (a subset of full fMRIPrep capabilities)
- **Smart defaults**: Only includes non-default values in the generated YAML for cleaner configurations
- **Resource configuration**: Set CPU count, RAM size, and other resource parameters
- **Processing toggles**: Enable/disable FreeSurfer, AROMA, longitudinal processing, etc.

### 🔧 **Advanced Features**
- **Trimstart preprocessing**: Set individual trim values for each functional scan
- **Ignore options**: Configure fMRIPrep to ignore fieldmaps, slice timing, or SBRef files
- **Dynamic updates**: Interface automatically updates when you change BIDS names
- **Value preservation**: Your settings are preserved when switching between tabs

### 📋 **Output Management**
- **Real-time preview**: See your YAML configuration update as you make changes
- **Clean output**: Generated YAML only includes settings that differ from defaults
- **Export options**: Copy to clipboard or download as a file

## Usage

### Getting Started

1. **Open the application** in your web browser by opening `index.html`
2. **Load your scan data** using one of these methods:
   - **Directory selection**: Click "Browse for Directory" and select your neuroimaging data folder
   - **Manual entry**: Click "Enter Manually" and type scan names line by line
   - **Load example**: Use the example data to explore the interface

### Basic Workflow

1. **Scan Input Tab**
   - Select your directory or enter scan names manually
   - Review the detected scans and categories

2. **BIDS Naming Tab**
   - Review automatically suggested BIDS names
   - Modify names as needed (with real-time validation)
   - Use ignore checkboxes for scans you don't want to process

3. **fMRIPrep Options Tab**
   - Configure processing resources (CPUs, RAM)
   - Select processing options (FreeSurfer, AROMA, etc.)
   - Set output spaces and notification email

4. **Advanced Tab**
   - Configure ignore options for fMRIPrep
   - Set up trimstart preprocessing if needed
   - Adjust TOPUP and dummy scan settings

5. **Export**
   - Copy the YAML configuration to clipboard
   - Download as a `.yaml` file for use with iris-fmriprep

### Understanding Scan Selection

The tool implements iris-fmriprep's scan selection logic:
- **Single scans**: Uses the highest numbered scan less than 1000
- **Multi-echo sequences**: Uses all echoes from the highest numbered group
- **Duplicates**: Only the "final" scan from each group is shown and processed

### BIDS Naming Guidelines

- **Anatomical scans**: Use suffixes like `T1w`, `T2w`, `FLAIR`
- **Functional scans**: Use format `task-<name>_bold` (e.g., `task-rest_bold`)
- **Fieldmaps**: Use `fieldmap`, `magnitude1`, `magnitude2`, `phasediff`
- **DWI scans**: Use `dwi` suffix

The tool provides validation and suggestions to help ensure compliance.

## File Structure

```
iris-config-generator/
├── index.html              # Main application interface
├── css/
│   └── main.css            # Styling
├── js/
│   ├── main.js             # Core application logic
│   ├── scanParser.js       # Scan analysis and categorization
│   ├── bidsValidator.js    # BIDS name validation
│   ├── configGenerator.js  # YAML generation
│   └── templates.js        # UI templates
└── README.md               # This file
```

## Browser Compatibility

- Modern browsers with JavaScript enabled
- Supports HTML5 File API for directory selection
- No server required - runs entirely in the browser

## Example Output

```yaml
run: fmriprep
bidsnames:
  anat:
    T1_MEMPRAGE_1.2mm_p4_Session_03_RMS: T1w
  func:
    ses-003_func_task-rest_run-01: task-rest_bold
    ses-003_func_task-fid_run-01: task-fid_bold
fmriprep:
  freesurfer: true
  ncpus: 16
preprocess:
  trimstart:
    DEFAULT: 10
    task-rest_bold: 8
```

## Tips

- **Start simple**: Begin with the basic BIDS naming, then add advanced options as needed
- **Use validation**: Pay attention to validation messages to ensure proper BIDS compliance
- **Preview frequently**: Check the YAML preview to see how your configuration looks
- **Save configurations**: Download your YAML files for reuse and documentation

## Troubleshooting

- **Directory selection not working**: Ensure you're using a modern browser that supports HTML5 File API
- **Scans not appearing**: Check that your directory contains `.nii`, `.nii.gz`, or `.json` files
- **BIDS validation errors**: Follow the suggested format corrections provided by the validator
- **Missing advanced options**: Ensure you've enabled the relevant checkboxes in the Advanced tab

For more information about iris-fmriprep and BIDS formatting, consult the iris-fmriprep documentation.