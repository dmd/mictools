# CLAUDE.md - Development Context for iris-fmriprep Configuration Generator

This document provides development context for Claude when working on the iris-fmriprep Configuration Generator.

## Project Overview

This is a web-based YAML configuration generator for iris-fmriprep, a wrapper tool for running fMRIPrep on neuroimaging data. The application helps users create properly formatted YAML configuration files by providing an intuitive interface for scan management and parameter configuration.

## Architecture

### Core Components

1. **Main Application (`js/main.js`)**
   - `IrisConfigApp` class - Central application controller
   - Event handling and tab management
   - Coordinates between all other components

2. **Scan Parser (`js/scanParser.js`)**
   - `ScanParser` class - Analyzes and categorizes neuroimaging scans
   - Implements iris-fmriprep's `final_scan()` logic from `converters.py`
   - Handles multi-echo detection and BIDS suggestions

3. **BIDS Validator (`js/bidsValidator.js`)**
   - `BIDSValidator` class - Validates BIDS naming conventions
   - Real-time validation with error messages and suggestions

4. **Configuration Generator (`js/configGenerator.js`)**
   - `ConfigGenerator` class - Generates YAML output
   - Manages configuration state and export functionality

5. **UI Templates (`js/templates.js`)**
   - Common UI component templates
   - Consistent styling and structure

### Key Design Patterns

- **Modular Architecture**: Each component has a specific responsibility
- **Event-driven**: Uses event listeners for real-time updates
- **State Management**: Centralized configuration state in ConfigGenerator
- **Progressive Enhancement**: Works without server-side processing

## Critical Implementation Details

### Scan Selection Logic (Based on iris-fmriprep's converters.py)

The `final_scan()` logic is implemented in `scanParser.js:183-227`:

```javascript
applyFinalScanLogic(scans) {
    // For single-echo: returns highest numbered scan < 1000
    // For multi-echo: returns all echoes from highest numbered group
    // Ignores scans with numbers >= 1000
}
```

This mirrors the Python implementation in `../iris/converters.py:16-56`.

### Default Value Handling

**CRITICAL**: The application only includes non-default values in generated YAML. Default values are defined in `main.js:724-730`:

```javascript
const defaults = {
    ncpus: 8,
    ramsize: 32,
    'fmriprep-version': '25.1-latest',
    'output-spaces': 'MNI152NLin2009cAsym:res-2 anat func fsaverage',
    'dummy-scans': 0
};
```

### Dynamic Interface Updates

The trimstart functional scans section (`main.js:373-428`) automatically updates when BIDS names change, preserving user-entered values through the `existingValues` mechanism.

### Event Binding

All form controls have event listeners bound in:
- `bindFMRIPrepOptions()` - Main fMRIPrep options
- `bindAdvancedOptions()` - Advanced tab options including ignore checkboxes
- Individual scan inputs - Dynamic event binding for BIDS names and trimstart values

## File Structure & Responsibilities

```
config-generator/
├── index.html              # Main UI structure with Bootstrap tabs
├── css/main.css            # Styling (minimal, mostly Bootstrap)
├── js/
│   ├── main.js             # Core app logic, event handling, UI updates
│   ├── scanParser.js       # Scan analysis, categorization, final_scan logic
│   ├── bidsValidator.js    # BIDS validation rules and error messages
│   ├── configGenerator.js  # YAML generation and configuration management
│   └── templates.js        # Reusable UI templates
├── README.md               # User documentation
└── CLAUDE.md               # This file
```

## Development History & Major Features

### Phase 1: Initial Implementation
- Basic YAML generation
- Scan categorization
- BIDS naming interface

### Phase 2: Enhanced Functionality
- Implemented proper `final_scan()` logic from iris-fmriprep
- Added ignore functionality with auto-ignore for scout/localizer scans
- Fixed scan display to show base names without trailing numbers
- Added sticky YAML preview

### Phase 3: Advanced Features & Fixes
- **Enhanced trimstart**: Individual per-functional-scan settings instead of just DEFAULT
- **Default value handling**: Only non-default values appear in YAML
- **Dynamic updates**: Trimstart section updates when BIDS names change
- **Fixed ignore options**: Added missing event listeners for advanced ignore checkboxes
- **Value preservation**: User inputs preserved during dynamic interface updates

## Key Configuration Sections

### 1. BIDS Names (`bidsnames`)
Maps original scan names to BIDS-compliant names:
```yaml
bidsnames:
  anat:
    T1_MEMPRAGE_original_name: T1w
  func:
    task_rest_original: task-rest_bold
```

### 2. fMRIPrep Options (`fmriprep`)
Processing parameters (only non-defaults included):
```yaml
fmriprep:
  freesurfer: true
  ncpus: 16
  ignore:
    - fieldmaps
    - slicetiming
```

### 3. Preprocessing (`preprocess`)
Currently supports trimstart with DEFAULT and per-scan values:
```yaml
preprocess:
  trimstart:
    DEFAULT: 10
    task-rest_bold: 8
```

## Common Development Tasks

### Adding New fMRIPrep Options
1. Add HTML form control in `index.html`
2. Add to `collectAllFMRIPrepOptions()` in `main.js`
3. Add event listener in `bindFMRIPrepOptions()` or `bindAdvancedOptions()`
4. Define default value if applicable

### Adding New Validation Rules
1. Update `bidsValidator.js` with new patterns
2. Add error messages and suggestions
3. Test with various input formats

### Modifying Scan Selection Logic
1. Update `applyFinalScanLogic()` in `scanParser.js`
2. Ensure it matches iris-fmriprep's `converters.py` behavior
3. Test with various scan naming patterns

## Testing Considerations

### Test Data
Use scans from `../nifti-test/` directory which contains:
- Multi-echo sequences
- Scout/localizer scans (for auto-ignore testing)
- Various naming patterns
- Duplicate numbered scans

### Key Test Scenarios
1. **Directory scanning**: Various file types and naming patterns
2. **Final scan logic**: Multiple scans with different numbers
3. **Multi-echo handling**: Echo groups and pattern recognition  
4. **BIDS validation**: Valid and invalid naming patterns
5. **Default value handling**: Ensure only changed values appear in YAML
6. **Dynamic updates**: Changing BIDS names updates trimstart section
7. **Ignore functionality**: All ignore checkboxes work correctly

## Integration Points

### With iris-fmriprep
- Generated YAML must be compatible with iris-fmriprep's expected format
- Scan selection logic must match `converters.py:final_scan()`
- BIDS naming must follow iris-fmriprep conventions

### With External Tools
- Uses Bootstrap 5.1.3 for UI components
- Uses js-yaml library for YAML generation
- Uses Font Awesome for icons
- No server-side dependencies

## Performance Considerations

- File scanning happens in browser using HTML5 File API
- Large directories (>1000 files) may cause UI lag
- YAML generation is synchronous and fast
- Real-time validation runs on every keystroke

## Browser Compatibility

- Requires modern browser with HTML5 File API support
- Uses ES6 features (classes, arrow functions, template literals)
- No IE11 support due to modern JavaScript usage

## Security Notes

- Runs entirely client-side, no data sent to servers
- File contents are not read, only filenames processed
- Safe for use with sensitive neuroimaging data

This context should help Claude understand the codebase structure, key implementation details, and development patterns when working on future enhancements.
