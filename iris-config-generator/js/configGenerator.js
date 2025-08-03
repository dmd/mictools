/**
 * Configuration Generator Module for iris-fmriprep Configuration Generator
 * Generates YAML configuration files for iris-fmriprep
 */

class ConfigGenerator {
    constructor() {
        this.config = {
            run: 'fmriprep',
            bidsnames: {},
            fmriprep: {},
            preprocess: {}
        };
    }

    /**
     * Update configuration section
     */
    updateConfig(section, data) {
        if (this.config.hasOwnProperty(section)) {
            this.config[section] = { ...this.config[section], ...data };
        } else {
            this.config[section] = data;
        }
        this.notifyUpdate();
    }

    /**
     * Set run mode
     */
    setRunMode(mode) {
        this.config.run = mode;
        this.notifyUpdate();
    }

    /**
     * Update BIDS names mapping
     */
    updateBIDSNames(category, mapping) {
        if (!this.config.bidsnames[category]) {
            this.config.bidsnames[category] = {};
        }
        this.config.bidsnames[category] = { ...this.config.bidsnames[category], ...mapping };
        this.notifyUpdate();
    }

    /**
     * Remove BIDS name mapping
     */
    removeBIDSName(category, originalName) {
        if (this.config.bidsnames[category] && this.config.bidsnames[category][originalName]) {
            delete this.config.bidsnames[category][originalName];
            if (Object.keys(this.config.bidsnames[category]).length === 0) {
                delete this.config.bidsnames[category];
            }
            this.notifyUpdate();
        }
    }

    /**
     * Update fMRIPrep options
     */
    updateFMRIPrepOptions(options) {
        // Clean up options - remove false values and empty strings
        const cleanedOptions = {};
        
        Object.entries(options).forEach(([key, value]) => {
            if (value !== false && value !== '' && value !== null && value !== undefined) {
                // Convert string numbers to actual numbers where appropriate
                if (['ncpus', 'ramsize', 'dummy-scans', 'topup-max-vols'].includes(key)) {
                    const numValue = parseInt(value);
                    if (!isNaN(numValue)) {
                        cleanedOptions[key] = numValue;
                    }
                } else if (typeof value === 'string' && value.trim() !== '') {
                    cleanedOptions[key] = value.trim();
                } else if (typeof value === 'boolean' && value === true) {
                    cleanedOptions[key] = true;
                } else if (Array.isArray(value) && value.length > 0) {
                    cleanedOptions[key] = value;
                }
            }
        });

        this.config.fmriprep = cleanedOptions;
        this.notifyUpdate();
    }

    /**
     * Update preprocessing options
     */
    updatePreprocessOptions(options) {
        const cleanedOptions = {};
        
        if (options.trimstart && Object.keys(options.trimstart).length > 0) {
            cleanedOptions.trimstart = {};
            Object.entries(options.trimstart).forEach(([key, value]) => {
                const numValue = parseInt(value);
                if (!isNaN(numValue) && numValue >= 0) {
                    cleanedOptions.trimstart[key] = numValue;
                }
            });
        }

        if (Object.keys(cleanedOptions).length > 0) {
            this.config.preprocess = cleanedOptions;
        } else {
            delete this.config.preprocess;
        }
        
        this.notifyUpdate();
    }

    /**
     * Generate YAML string
     */
    generateYAML() {
        const configCopy = JSON.parse(JSON.stringify(this.config));
        
        // Clean up empty sections
        Object.keys(configCopy).forEach(key => {
            if (typeof configCopy[key] === 'object' && Object.keys(configCopy[key]).length === 0) {
                delete configCopy[key];
            }
        });

        try {
            return jsyaml.dump(configCopy, {
                indent: 2,
                lineWidth: 80,
                noRefs: true,
                sortKeys: false
            });
        } catch (error) {
            console.error('Error generating YAML:', error);
            return '# Error generating YAML configuration';
        }
    }

    /**
     * Load configuration from YAML string
     */
    loadFromYAML(yamlString) {
        try {
            const loaded = jsyaml.load(yamlString);
            this.config = {
                run: 'fmriprep',
                bidsnames: {},
                fmriprep: {},
                preprocess: {},
                ...loaded
            };
            this.notifyUpdate();
            return true;
        } catch (error) {
            console.error('Error loading YAML:', error);
            return false;
        }
    }

    /**
     * Get current configuration
     */
    getConfig() {
        return JSON.parse(JSON.stringify(this.config));
    }

    /**
     * Reset configuration to defaults
     */
    reset() {
        this.config = {
            run: 'fmriprep',
            bidsnames: {},
            fmriprep: {},
            preprocess: {}
        };
        this.notifyUpdate();
    }

    /**
     * Validate configuration
     */
    validateConfig() {
        const errors = [];
        const warnings = [];

        // Check if run mode is valid
        if (!['nifti', 'bids', 'fmriprep'].includes(this.config.run)) {
            errors.push('Invalid run mode. Must be one of: nifti, bids, fmriprep');
        }

        // Check BIDS names if run mode requires them
        if (['bids', 'fmriprep'].includes(this.config.run)) {
            if (!this.config.bidsnames || Object.keys(this.config.bidsnames).length === 0) {
                warnings.push('No BIDS name mappings defined. This is required for BIDS and fMRIPrep processing.');
            } else {
                // Validate BIDS names
                Object.entries(this.config.bidsnames).forEach(([category, mappings]) => {
                    Object.entries(mappings).forEach(([original, bids]) => {
                        if (!bids || bids.trim() === '') {
                            errors.push(`Empty BIDS name for scan '${original}' in category '${category}'`);
                        }
                    });
                });
            }
        }

        // Validate fMRIPrep options
        if (this.config.fmriprep) {
            const fmriprepOpts = this.config.fmriprep;
            
            // Check resource constraints
            if (fmriprepOpts.ncpus && (fmriprepOpts.ncpus < 1 || fmriprepOpts.ncpus > 64)) {
                warnings.push('Number of CPUs should typically be between 1 and 64');
            }
            
            if (fmriprepOpts.ramsize && (fmriprepOpts.ramsize < 4 || fmriprepOpts.ramsize > 256)) {
                warnings.push('RAM size should typically be between 4GB and 256GB');
            }

            // Check version format
            if (fmriprepOpts['fmriprep-version'] && !/^\d+\.\d+/.test(fmriprepOpts['fmriprep-version'])) {
                warnings.push('fMRIPrep version should follow format like "25.1-latest" or "23.2.0"');
            }

            // Check for incompatible options
            if (fmriprepOpts.aroma && fmriprepOpts['fmriprep-version']) {
                const version = fmriprepOpts['fmriprep-version'];
                if (version.startsWith('23.1') || version.startsWith('24.') || version.startsWith('25.')) {
                    warnings.push('AROMA is not available in fMRIPrep 23.1 and later versions');
                }
            }
        }

        // Validate preprocessing options
        if (this.config.preprocess && this.config.preprocess.trimstart) {
            Object.entries(this.config.preprocess.trimstart).forEach(([key, value]) => {
                if (typeof value !== 'number' || value < 0) {
                    errors.push(`Invalid trimstart value for '${key}': must be a non-negative number`);
                }
            });
        }

        return { errors, warnings };
    }

    /**
     * Get configuration summary for display
     */
    getConfigSummary() {
        const summary = {
            runMode: this.config.run,
            scanCount: 0,
            categories: [],
            fmriprepEnabled: this.config.run === 'fmriprep',
            hasPreprocessing: Object.keys(this.config.preprocess || {}).length > 0
        };

        if (this.config.bidsnames) {
            summary.categories = Object.keys(this.config.bidsnames);
            summary.scanCount = Object.values(this.config.bidsnames)
                .reduce((total, category) => total + Object.keys(category).length, 0);
        }

        return summary;
    }

    /**
     * Export configuration as downloadable file
     */
    exportConfig(filename = 'iris-fmriprep-config.yaml') {
        const yamlContent = this.generateYAML();
        const blob = new Blob([yamlContent], { type: 'text/yaml' });
        const url = window.URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    /**
     * Generate example configuration
     */
    generateExample() {
        this.config = {
            run: 'fmriprep',
            bidsnames: {
                anat: {
                    'T1_MEMPRAGE_1.2mm_p4_Session_03_RMS_6': 'T1w',
                    'T1_MEMPRAGE_1.2mm_p4_Session_04_RMS_17': 'T1w'
                },
                func: {
                    'ses-003_func_task-fid_run-01_10': 'task-fid_bold',
                    'ses-003_func_task-rest_run-01_11': 'task-rest_bold',
                    'ses-003_func_task-wtp_run-01_9': 'task-wtp_bold'
                },
                fmap: {
                    'ses-003_fmap-1_7_e1': 'magnitude1',
                    'ses-003_fmap-1_7_e2': 'magnitude2',
                    'ses-003_fmap-1_8_e2_ph': 'phasediff'
                }
            },
            fmriprep: {
                freesurfer: true,
                ncpus: 8,
                ramsize: 32,
                'output-spaces': 'MNI152NLin2009cAsym:res-2 anat func fsaverage'
            }
        };
        this.notifyUpdate();
    }

    /**
     * Register update callback
     */
    onUpdate(callback) {
        this.updateCallback = callback;
    }

    /**
     * Notify about configuration updates
     */
    notifyUpdate() {
        if (this.updateCallback) {
            this.updateCallback(this.config);
        }
    }
}

// Export for use in other modules
window.ConfigGenerator = ConfigGenerator;