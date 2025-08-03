/**
 * Main Application Logic for iris-fmriprep Configuration Generator
 */

class IrisConfigApp {
    constructor() {
        this.scanParser = new ScanParser();
        this.bidsValidator = new BIDSValidator();
        this.configGenerator = new ConfigGenerator();
        
        this.scans = [];
        this.categorizedScans = {};
        
        this.initializeEventListeners();
        this.configGenerator.onUpdate((config) => this.updateYAMLPreview());
        
        // Start with empty configuration
        this.updateYAMLPreview();
    }

    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        // File input
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        }

        // Drag and drop functionality
        this.initializeDragAndDrop();

        // Run mode selection
        const runMode = document.getElementById('runMode');
        if (runMode) {
            runMode.addEventListener('change', (e) => this.handleRunModeChange(e));
        }

        // fMRIPrep options
        this.bindFMRIPrepOptions();
        
        // Advanced options
        this.bindAdvancedOptions();

        // Tab navigation
        this.initializeTabNavigation();
    }

    /**
     * Initialize tab navigation
     */
    initializeTabNavigation() {
        const tabs = document.querySelectorAll('#configTabs button[data-bs-toggle="tab"]');
        tabs.forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                const targetId = e.target.getAttribute('data-bs-target');
                if (targetId === '#bids-naming') {
                    this.updateBIDSNamingInterface();
                }
            });
        });
    }

    /**
     * Initialize drag and drop functionality
     */
    initializeDragAndDrop() {
        const dropZone = document.getElementById('dropZone');
        if (!dropZone) return;

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        // Highlight drop zone when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('dragover');
            });
        });

        // Handle dropped files
        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files.length > 0) {
                // Create a synthetic event to reuse existing upload handler
                const syntheticEvent = {
                    target: {
                        files: files
                    }
                };
                this.handleFileUpload(syntheticEvent);
            }
        });
    }

    /**
     * Handle directory selection - scan for filenames only
     */
    handleFileUpload(event) {
        const files = Array.from(event.target.files);
        
        // Extract all relevant filenames (NIFTI, JSON, and other neuroimaging files)
        const allFiles = files.map(file => file.name);
        const scanNames = this.extractScanNamesFromFiles(allFiles);
        
        if (scanNames.length > 0) {
            this.processScans(scanNames);
            this.showDetectedScans();
            this.enableBIDSNamingTab();
            
            // Show summary of what was found
            this.showDirectoryScanSummary(allFiles, scanNames);
        } else {
            alert('No neuroimaging files found in the selected directory. Please select a directory containing .nii, .nii.gz, or other scan files.');
        }
    }

    /**
     * Extract scan names from file listing
     */
    extractScanNamesFromFiles(fileNames) {
        const scanNames = new Set();
        
        // Patterns for neuroimaging files
        const patterns = [
            /^(.+)\.nii\.gz$/,
            /^(.+)\.nii$/,
            /^(.+)\.json$/,
            /^(.+)\.bval$/,
            /^(.+)\.bvec$/
        ];
        
        fileNames.forEach(fileName => {
            for (const pattern of patterns) {
                const match = fileName.match(pattern);
                if (match) {
                    const baseName = match[1];
                    // Only add if it looks like a scan (not a README, etc.)
                    if (!baseName.toLowerCase().includes('readme') && 
                        !baseName.toLowerCase().includes('dataset_description') &&
                        !baseName.toLowerCase().includes('participants')) {
                        scanNames.add(baseName);
                    }
                    break;
                }
            }
        });
        
        return Array.from(scanNames).sort();
    }

    /**
     * Show summary of directory scan
     */
    showDirectoryScanSummary(allFiles, scanNames) {
        const summary = `
            <div class="alert alert-info mt-3">
                <strong>Directory Scan Results:</strong><br>
                • Total files found: ${allFiles.length}<br>
                • Neuroimaging scans detected: ${scanNames.length}<br>
                • File types: ${this.getFileTypeSummary(allFiles)}
            </div>
        `;
        
        const detectedScansDiv = document.getElementById('detectedScans');
        const existingSummary = detectedScansDiv.querySelector('.directory-summary');
        if (existingSummary) {
            existingSummary.remove();
        }
        
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'directory-summary';
        summaryDiv.innerHTML = summary;
        detectedScansDiv.insertBefore(summaryDiv, detectedScansDiv.firstChild);
    }

    /**
     * Get file type summary
     */
    getFileTypeSummary(fileNames) {
        const types = {};
        fileNames.forEach(name => {
            const ext = name.split('.').pop().toLowerCase();
            types[ext] = (types[ext] || 0) + 1;
        });
        
        return Object.entries(types)
            .map(([ext, count]) => `${ext} (${count})`)
            .join(', ');
    }

    /**
     * Switch to manual entry mode
     */
    switchToManualEntry() {
        document.getElementById('manualEntry').style.display = 'block';
        document.getElementById('detectedScans').style.display = 'none';
    }

    /**
     * Parse manually entered scans
     */
    parseManualScans() {
        const scanList = document.getElementById('scanList').value;
        const scanNames = scanList.split('\n')
            .map(line => line.trim())
            .filter(line => line.length > 0);
        
        if (scanNames.length > 0) {
            this.processScans(scanNames);
            this.showDetectedScans();
            this.enableBIDSNamingTab();
        } else {
            alert('Please enter at least one scan name.');
        }
    }

    /**
     * Process scans and categorize them
     */
    processScans(scanNames) {
        this.scans = this.scanParser.parseScans(scanNames);
        this.categorizedScans = this.scanParser.getCategorizedScans();
        
        // Generate initial BIDS suggestions
        const suggestions = this.scanParser.generateBIDSSuggestions();
        
        // Update config with suggestions, but exclude auto-ignored scans
        Object.entries(suggestions).forEach(([category, mappings]) => {
            const filteredMappings = {};
            Object.entries(mappings).forEach(([scanName, bidsName]) => {
                // Check if this scan should be auto-ignored
                if (!/scout|localizer/i.test(scanName)) {
                    filteredMappings[scanName] = bidsName;
                }
            });
            
            if (Object.keys(filteredMappings).length > 0) {
                this.configGenerator.updateBIDSNames(category, filteredMappings);
            }
        });
    }

    /**
     * Show detected scans
     */
    showDetectedScans() {
        const scansListDiv = document.getElementById('scansList');
        const analysisResults = this.scanParser.getAnalysisResults();
        
        let html = '<div class="row">';
        
        // Show categorized scans
        Object.entries(this.categorizedScans).forEach(([category, scans]) => {
            if (scans.length > 0) {
                html += `<div class="col-md-6 mb-3">`;
                html += `<h6 class="text-capitalize">${category} Scans (${scans.length})</h6>`;
                html += '<ul class="list-group list-group-flush">';
                
                scans.forEach(scan => {
                    const isMultiEcho = scan.isMultiEcho ? ' <span class="badge bg-info">Multi-echo</span>' : '';
                    const scanCount = scan.scanCount > 1 ? ` <span class="badge bg-secondary">${scan.scanCount} files</span>` : '';
                    html += `<li class="list-group-item py-1 px-2 small">${scan.displayName}${isMultiEcho}${scanCount}</li>`;
                });
                
                html += '</ul></div>';
            }
        });
        
        html += '</div>';
        
        // Show analysis warnings
        if (analysisResults.duplicates && analysisResults.duplicates.length > 0) {
            html += '<div class="alert alert-warning mt-3">';
            html += '<strong>Potential duplicates detected:</strong><ul class="mb-0">';
            analysisResults.duplicates.forEach(dup => {
                html += `<li>${dup.baseName} (using: ${dup.recommended})</li>`;
            });
            html += '</ul></div>';
        }
        
        if (Object.keys(analysisResults.multiecho).length > 0) {
            html += '<div class="alert alert-info mt-3">';
            html += '<strong>Multi-echo sequences detected:</strong><ul class="mb-0">';
            Object.entries(analysisResults.multiecho).forEach(([group, echoes]) => {
                html += `<li>${group} (${echoes.length} echoes)</li>`;
            });
            html += '</ul></div>';
        }
        
        scansListDiv.innerHTML = html;
        document.getElementById('detectedScans').style.display = 'block';
    }

    /**
     * Enable all configuration tabs once scans are loaded
     */
    enableBIDSNamingTab() {
        // Enable all tabs
        ['bids-naming-tab', 'fmriprep-options-tab', 'advanced-tab'].forEach(tabId => {
            const tab = document.getElementById(tabId);
            tab.classList.remove('disabled');
        });
        
        // Switch to BIDS naming tab
        const bidsTab = document.getElementById('bids-naming-tab');
        bidsTab.click();
    }

    /**
     * Update BIDS naming interface
     */
    updateBIDSNamingInterface() {
        const bidsSection = document.getElementById('bidsNamingSection');
        bidsSection.style.display = 'block';
        
        // Clear existing content
        ['anatScans', 'funcScans', 'fmapScans', 'dwiScans', 'otherScans'].forEach(id => {
            document.getElementById(id).innerHTML = '';
        });
        
        const config = this.configGenerator.getConfig();
        const bidsnames = config.bidsnames || {};
        
        // Populate each category with section headers
        Object.entries(this.categorizedScans).forEach(([category, scans]) => {
            if (scans.length === 0) return;
            
            const containerId = this.getCategoryContainerId(category);
            const container = document.getElementById(containerId);
            
            if (container && scans.length > 0) {
                // Add section header
                const header = document.createElement('div');
                header.className = 'mt-4 mb-3';
                header.innerHTML = `
                    <h6 class="text-capitalize border-bottom pb-2">
                        <i class="fas fa-${this.getCategoryIcon(category)} me-2"></i>
                        ${category} Scans (${scans.length})
                    </h6>
                `;
                container.appendChild(header);
                
                // Add scans
                scans.forEach(scan => {
                    const scanDiv = this.createScanMappingDiv(category, scan, bidsnames[category] || {});
                    container.appendChild(scanDiv);
                });
            }
        });
    }

    /**
     * Get icon for scan category
     */
    getCategoryIcon(category) {
        const icons = {
            anat: 'brain',
            func: 'chart-line',
            fmap: 'magnet',
            dwi: 'project-diagram',
            other: 'file'
        };
        return icons[category] || 'file';
    }

    /**
     * Get container ID for category
     */
    getCategoryContainerId(category) {
        const mapping = {
            'anat': 'anatScans',
            'func': 'funcScans',
            'fmap': 'fmapScans',
            'dwi': 'dwiScans',
            'other': 'otherScans'
        };
        return mapping[category] || 'otherScans';
    }

    /**
     * Create scan mapping div
     */
    createScanMappingDiv(category, scan, categoryMappings) {
        const div = document.createElement('div');
        
        const yamlKey = scan.yamlKey;
        const displayName = scan.displayName;
        
        // Check if this scan should be auto-ignored
        const shouldAutoIgnore = /scout|localizer/i.test(displayName);
        
        div.className = `mb-3 p-3 border rounded ${shouldAutoIgnore ? 'bg-light' : ''}`;
        
        const currentBidsName = categoryMappings[yamlKey] || '';
        const isMultiEcho = scan.isMultiEcho;
        const scanCount = scan.scanCount;
        
        // Create description of what scans this represents
        let scanDescription = '';
        if (scanCount > 1) {
            if (isMultiEcho) {
                scanDescription = `<small class="text-muted">Represents ${scanCount} files (multi-echo sequence)</small>`;
            } else {
                scanDescription = `<small class="text-muted">Represents ${scanCount} files (highest numbered will be used)</small>`;
            }
        } else {
            scanDescription = `<small class="text-muted">Single scan</small>`;
        }
        
        if (shouldAutoIgnore) {
            scanDescription += ` <small class="text-warning">(Auto-ignored: scout/localizer)</small>`;
        }
        
        div.innerHTML = `
            <div class="mb-2 d-flex justify-content-between align-items-start">
                <div>
                    <label class="form-label fw-bold">${displayName}</label>
                    ${isMultiEcho ? '<span class="badge bg-info ms-2">Multi-echo</span>' : ''}
                    ${scanCount > 1 ? `<span class="badge bg-secondary ms-2">${scanCount} files</span>` : ''}
                </div>
                <div class="form-check">
                    <input class="form-check-input ignore-scan-checkbox" type="checkbox" id="ignore_${yamlKey}" 
                           data-category="${category}" data-original="${yamlKey}" ${shouldAutoIgnore ? 'checked' : ''}>
                    <label class="form-check-label text-danger" for="ignore_${yamlKey}">
                        <small>Ignore</small>
                    </label>
                </div>
            </div>
            ${scanDescription}
            <div class="input-group mb-2 mt-2 bids-input-group" ${shouldAutoIgnore ? 'style="opacity: 0.3"' : ''}>
                <input type="text" class="form-control bids-name-input" 
                       value="${shouldAutoIgnore ? '' : currentBidsName}" 
                       placeholder="Enter BIDS name..."
                       data-category="${category}"
                       data-original="${yamlKey}" ${shouldAutoIgnore ? 'disabled' : ''}>
                <button class="btn btn-outline-secondary" type="button" 
                        onclick="showBIDSHelper('${category}', '${yamlKey}')">
                    <i class="fas fa-question"></i>
                </button>
            </div>
            <div class="validation-feedback"></div>
        `;
        
        // Add event listener for input changes
        const input = div.querySelector('.bids-name-input');
        input.addEventListener('input', (e) => this.handleBIDSNameChange(e));
        input.addEventListener('blur', (e) => this.validateBIDSName(e));
        
        // Add event listener for ignore checkbox
        const ignoreCheckbox = div.querySelector('.ignore-scan-checkbox');
        ignoreCheckbox.addEventListener('change', (e) => this.handleIgnoreScanChange(e));
        
        return div;
    }

    /**
     * Handle BIDS name changes
     */
    handleBIDSNameChange(event) {
        const input = event.target;
        const category = input.dataset.category;
        const original = input.dataset.original;
        const bidsName = input.value.trim();
        
        // Check if this scan is being ignored
        const scanDiv = input.closest('.mb-3');
        const ignoreCheckbox = scanDiv.querySelector('.ignore-scan-checkbox');
        
        if (ignoreCheckbox && ignoreCheckbox.checked) {
            // If scan is ignored, don't update config
            return;
        }
        
        if (bidsName) {
            this.configGenerator.updateBIDSNames(category, { [original]: bidsName });
        } else {
            this.configGenerator.removeBIDSName(category, original);
        }
        
        // Clear validation feedback while typing
        const feedback = input.closest('.mb-3').querySelector('.validation-feedback');
        feedback.innerHTML = '';
        input.classList.remove('is-valid', 'is-invalid');
    }

    /**
     * Validate BIDS name
     */
    validateBIDSName(event) {
        const input = event.target;
        const bidsName = input.value.trim();
        const feedback = input.closest('.mb-3').querySelector('.validation-feedback');
        
        // Check if this scan is being ignored
        const scanDiv = input.closest('.mb-3');
        const ignoreCheckbox = scanDiv.querySelector('.ignore-scan-checkbox');
        
        if (ignoreCheckbox && ignoreCheckbox.checked) {
            // If scan is ignored, don't validate
            return;
        }
        
        if (!bidsName) {
            input.classList.remove('is-valid', 'is-invalid');
            feedback.innerHTML = '';
            return;
        }
        
        // Determine modality from category
        const category = input.dataset.category;
        const modality = category === 'anat' ? 'anat' : 
                        category === 'func' ? 'func' : 
                        category === 'fmap' ? 'fmap' : 'func';
        
        const validation = this.bidsValidator.validateBIDSName(bidsName, modality);
        
        if (validation.isValid) {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
            feedback.innerHTML = '';
        } else {
            input.classList.remove('is-valid');
            input.classList.add('is-invalid');
            feedback.innerHTML = `
                <div class="text-danger">
                    ${validation.errors.join('<br>')}
                </div>
                ${validation.warnings.length > 0 ? 
                    `<div class="text-warning">${validation.warnings.join('<br>')}</div>` : ''}
                ${validation.suggestions.length > 0 ? 
                    `<div class="text-info">${validation.suggestions.join('<br>')}</div>` : ''}
            `;
        }
    }

    /**
     * Handle ignore scan checkbox changes
     */
    handleIgnoreScanChange(event) {
        const checkbox = event.target;
        const category = checkbox.dataset.category;
        const original = checkbox.dataset.original;
        const scanDiv = checkbox.closest('.mb-3');
        const bidsInputGroup = scanDiv.querySelector('.bids-input-group');
        const bidsInput = scanDiv.querySelector('.bids-name-input');
        const validationFeedback = scanDiv.querySelector('.validation-feedback');
        
        if (checkbox.checked) {
            // Scan is being ignored
            bidsInputGroup.style.opacity = '0.3';
            bidsInput.disabled = true;
            bidsInput.value = '';
            validationFeedback.innerHTML = '';
            bidsInput.classList.remove('is-valid', 'is-invalid');
            scanDiv.classList.add('bg-light');
            
            // Remove from config
            this.configGenerator.removeBIDSName(category, original);
        } else {
            // Scan is being included again
            bidsInputGroup.style.opacity = '1';
            bidsInput.disabled = false;
            scanDiv.classList.remove('bg-light');
            
            // Restore suggested BIDS name if available
            const suggestions = this.scanParser.generateBIDSSuggestions();
            if (suggestions[category] && suggestions[category][original]) {
                bidsInput.value = suggestions[category][original];
                this.configGenerator.updateBIDSNames(category, { [original]: suggestions[category][original] });
            }
        }
    }

    /**
     * Handle run mode changes
     */
    handleRunModeChange(event) {
        const mode = event.target.value;
        this.configGenerator.setRunMode(mode);
        
        // Show/hide BIDS naming section based on run mode
        const bidsSection = document.getElementById('bidsNamingSection');
        if (mode === 'nifti') {
            bidsSection.style.display = 'none';
        } else {
            bidsSection.style.display = 'block';
        }
    }

    /**
     * Bind fMRIPrep options
     */
    bindFMRIPrepOptions() {
        const options = [
            'ncpus', 'ramsize', 'fmriprepVersion', 'outputSpaces', 'email',
            'freesurfer', 'aroma', 'anatOnly', 'longitudinal', 'forceSyn', 'returnAllComponents'
        ];
        
        options.forEach(optionId => {
            const element = document.getElementById(optionId);
            if (element) {
                element.addEventListener('change', () => this.updateFMRIPrepConfig());
            }
        });
    }

    /**
     * Update fMRIPrep configuration
     */
    updateFMRIPrepConfig() {
        const options = {};
        
        // Get numeric values
        ['ncpus', 'ramsize'].forEach(id => {
            const element = document.getElementById(id);
            if (element && element.value) {
                options[id] = parseInt(element.value);
            }
        });
        
        // Get string values
        ['outputSpaces', 'email'].forEach(id => {
            const element = document.getElementById(id);
            if (element && element.value.trim()) {
                options[id === 'outputSpaces' ? 'output-spaces' : id] = element.value.trim();
            }
        });
        
        // Get version
        const versionElement = document.getElementById('fmriprepVersion');
        if (versionElement && versionElement.value.trim()) {
            options['fmriprep-version'] = versionElement.value.trim();
        }
        
        // Get boolean options
        ['freesurfer', 'aroma', 'anatOnly', 'longitudinal', 'forceSyn', 'returnAllComponents'].forEach(id => {
            const element = document.getElementById(id);
            if (element && element.checked) {
                const configKey = id === 'anatOnly' ? 'anat-only' :
                                 id === 'forceSyn' ? 'force-syn' :
                                 id === 'returnAllComponents' ? 'return-all-components' : id;
                options[configKey] = true;
            }
        });
        
        // Get ignore options
        const ignoreOptions = [];
        ['ignoreFieldmaps', 'ignoreSlicetiming', 'ignoreSbref'].forEach(id => {
            const element = document.getElementById(id);
            if (element && element.checked) {
                ignoreOptions.push(element.value);
            }
        });
        if (ignoreOptions.length > 0) {
            options.ignore = ignoreOptions;
        }
        
        this.configGenerator.updateFMRIPrepOptions(options);
    }

    /**
     * Bind advanced options
     */
    bindAdvancedOptions() {
        const dummyScans = document.getElementById('dummyScans');
        if (dummyScans) {
            dummyScans.addEventListener('change', () => this.updateAdvancedConfig());
        }
        
        const topupMaxVols = document.getElementById('topupMaxVols');
        if (topupMaxVols) {
            topupMaxVols.addEventListener('change', () => this.updateAdvancedConfig());
        }
        
        const enableTrimstart = document.getElementById('enableTrimstart');
        if (enableTrimstart) {
            enableTrimstart.addEventListener('change', (e) => {
                document.getElementById('trimstartOptions').style.display = 
                    e.target.checked ? 'block' : 'none';
                this.updatePreprocessConfig();
            });
        }
        
        const trimstartDefault = document.getElementById('trimstartDefault');
        if (trimstartDefault) {
            trimstartDefault.addEventListener('change', () => this.updatePreprocessConfig());
        }
    }

    /**
     * Update advanced configuration
     */
    updateAdvancedConfig() {
        const options = {};
        
        const dummyScans = document.getElementById('dummyScans');
        if (dummyScans && dummyScans.value !== '') {
            options['dummy-scans'] = parseInt(dummyScans.value);
        }
        
        const topupMaxVols = document.getElementById('topupMaxVols');
        if (topupMaxVols && topupMaxVols.value !== '') {
            options['topup-max-vols'] = parseInt(topupMaxVols.value);
        }
        
        this.configGenerator.updateFMRIPrepOptions(options);
    }

    /**
     * Update preprocessing configuration
     */
    updatePreprocessConfig() {
        const enableTrimstart = document.getElementById('enableTrimstart');
        const options = {};
        
        if (enableTrimstart && enableTrimstart.checked) {
            const defaultValue = document.getElementById('trimstartDefault').value;
            if (defaultValue !== '') {
                options.trimstart = {
                    DEFAULT: parseInt(defaultValue)
                };
            }
        }
        
        this.configGenerator.updatePreprocessOptions(options);
    }

    /**
     * Update YAML preview
     */
    updateYAMLPreview() {
        const yamlPreview = document.getElementById('yamlPreview');
        const yaml = this.configGenerator.generateYAML();
        yamlPreview.innerHTML = `<code>${this.escapeHtml(yaml)}</code>`;
    }

    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Load example data
     */
    loadExampleData() {
        // Use scan names from nifti-test directory
        const exampleScans = [
            'T1_MEMPRAGE_1.2mm_p4_Session_03_RMS_6',
            'T1_MEMPRAGE_1.2mm_p4_Session_04_RMS_17',
            'ses-003_anat-AALScout_2',
            'ses-003_func_task-fid_run-01_10',
            'ses-003_func_task-rest_run-01_11',
            'ses-003_func_task-wtp_run-01_9',
            'ses-003_fmap-1_7_e1',
            'ses-003_fmap-1_7_e2',
            'ses-003_fmap-1_8_e2_ph',
            'ses-004_func_task-fid_run-01_21',
            'ses-004_func_task-rest_run-01_22',
            'ses-004_func_task-wtp_run-01_20'
        ];
        
        this.processScans(exampleScans);
        this.showDetectedScans();
        this.enableBIDSNamingTab();
        
        // Set some default fMRIPrep options
        document.getElementById('freesurfer').checked = true;
        document.getElementById('ncpus').value = 8;
        document.getElementById('ramsize').value = 32;
        this.updateFMRIPrepConfig();
    }
}

// Global functions for UI interactions
function switchToManualEntry() {
    window.app.switchToManualEntry();
}

function parseManualScans() {
    window.app.parseManualScans();
}

function showBIDSHelper(category, originalName) {
    const validator = window.app.bidsValidator;
    const suggestions = validator.getValidSuffixesForModality(category);
    
    alert(`BIDS naming help for ${category} scans:\n\nValid suffixes: ${suggestions.join(', ')}\n\nExample: sub-01_ses-1_${category === 'func' ? 'task-rest_' : ''}${suggestions[0]}`);
}

function copyYaml() {
    const yamlContent = window.app.configGenerator.generateYAML();
    navigator.clipboard.writeText(yamlContent).then(() => {
        alert('YAML configuration copied to clipboard!');
    });
}

function downloadYaml() {
    window.app.configGenerator.exportConfig();
}

function loadExampleData() {
    window.app.loadExampleData();
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new IrisConfigApp();
});