/**
 * Templates Module for iris-fmriprep Configuration Generator
 * Provides pre-built configuration templates and examples
 */

class ConfigTemplates {
    constructor() {
        this.templates = this.initializeTemplates();
    }

    /**
     * Initialize predefined templates
     */
    initializeTemplates() {
        return {
            basic: {
                name: 'Basic fMRIPrep',
                description: 'Simple fMRIPrep configuration with default settings',
                config: {
                    run: 'fmriprep',
                    bidsnames: {
                        anat: {
                            'T1_MPRAGE': 'T1w'
                        },
                        func: {
                            'BOLD_resting': 'task-rest_bold'
                        }
                    },
                    fmriprep: {
                        ncpus: 8,
                        ramsize: 32
                    }
                }
            },

            research: {
                name: 'Research Study',
                description: 'Comprehensive setup for research with FreeSurfer and quality control',
                config: {
                    run: 'fmriprep',
                    bidsnames: {
                        anat: {
                            'MEMPRAGE_gr2_RMS': 'T1w',
                            't2_tse_darkfluid_tra': 'FLAIR'
                        },
                        func: {
                            'BOLD_AIR_RESTING': 'task-resting_acq-air_bold',
                            'cue_mb6_gr2_1': 'task-cue_bold'
                        }
                    },
                    fmriprep: {
                        freesurfer: true,
                        ncpus: 16,
                        ramsize: 64,
                        'output-spaces': 'MNI152NLin2009cAsym:res-2 anat func fsaverage',
                        'return-all-components': true
                    }
                }
            },

            multiecho: {
                name: 'Multi-Echo',
                description: 'Configuration for multi-echo fMRI data with TEDANA processing',
                config: {
                    run: 'fmriprep',
                    bidsnames: {
                        anat: {
                            'T1_MEMPRAGE_RMS': 'T1w'
                        },
                        func: {
                            'rfMRI_REST_MULTIECHO_PA': 'task-rest_acq-multiecho_dir-PA_bold'
                        }
                    },
                    fmriprep: {
                        'me-output-echos': true,
                        ncpus: 12,
                        ramsize: 48,
                        'output-spaces': 'MNI152NLin2009cAsym:res-2'
                    }
                }
            },

            clinical: {
                name: 'Clinical Pipeline',
                description: 'Fast processing for clinical applications without FreeSurfer',
                config: {
                    run: 'fmriprep',
                    bidsnames: {
                        anat: {
                            'T1_3D_SPGR': 'T1w',
                            'T2_FLAIR': 'FLAIR'
                        },
                        func: {
                            'BOLD_resting_state': 'task-rest_bold'
                        }
                    },
                    fmriprep: {
                        'anat-only': false,
                        ncpus: 8,
                        ramsize: 24,
                        'output-spaces': 'MNI152NLin2009cAsym:res-2'
                    }
                }
            },

            longitudinal: {
                name: 'Longitudinal Study',
                description: 'Configuration for longitudinal data with session tracking',
                config: {
                    run: 'fmriprep',
                    bidsnames: {
                        anat: {
                            'T1_MPRAGE_session1': 'T1w',
                            'T1_MPRAGE_session2': 'T1w'
                        },
                        func: {
                            'task_memory_session1': 'task-memory_bold',
                            'task_memory_session2': 'task-memory_bold'
                        }
                    },
                    fmriprep: {
                        longitudinal: true,
                        freesurfer: true,
                        ncpus: 12,
                        ramsize: 48
                    }
                }
            },

            preprocessOnly: {
                name: 'Preprocessing Only',
                description: 'Data preprocessing with trimming but no fMRIPrep',
                config: {
                    run: 'bids',
                    bidsnames: {
                        anat: {
                            'T1_structural': 'T1w'
                        },
                        func: {
                            'BOLD_task': 'task-unknown_bold'
                        }
                    },
                    preprocess: {
                        trimstart: {
                            DEFAULT: 10,
                            'task-memory_bold': 5
                        }
                    }
                }
            },

            niftiOnly: {
                name: 'NIFTI Conversion',
                description: 'Convert DICOM to NIFTI format only',
                config: {
                    run: 'nifti'
                }
            },

            // Template based on actual nifti-test data
            niftiTestExample: {
                name: 'NIFTI Test Example',
                description: 'Based on the actual nifti-test directory structure',
                config: {
                    run: 'fmriprep',
                    bidsnames: {
                        anat: {
                            'T1_MEMPRAGE_1.2mm_p4_Session_03_RMS_6': 'T1w',
                            'T1_MEMPRAGE_1.2mm_p4_Session_04_RMS_17': 'T1w',
                            'ses-003_anat-AALScout_2': 'T1w',
                            'ses-004_anat-AALScout_13': 'T1w'
                        },
                        func: {
                            'ses-003_func_task-fid_run-01_10': 'task-fid_bold',
                            'ses-003_func_task-rest_run-01_11': 'task-rest_bold',
                            'ses-003_func_task-wtp_run-01_9': 'task-wtp_bold',
                            'ses-004_func_task-fid_run-01_21': 'task-fid_bold',
                            'ses-004_func_task-rest_run-01_22': 'task-rest_bold',
                            'ses-004_func_task-wtp_run-01_20': 'task-wtp_bold'
                        },
                        fmap: {
                            'ses-003_fmap-1_7_e1': 'magnitude1',
                            'ses-003_fmap-1_7_e2': 'magnitude2',
                            'ses-003_fmap-1_8_e2_ph': 'phasediff',
                            'ses-004_fmap-1_18_e1': 'magnitude1',
                            'ses-004_fmap-1_18_e2': 'magnitude2',
                            'ses-004_fmap-1_19_e2_ph': 'phasediff'
                        }
                    },
                    fmriprep: {
                        freesurfer: true,
                        ncpus: 8,
                        ramsize: 32,
                        'output-spaces': 'MNI152NLin2009cAsym:res-2 anat func fsaverage'
                    }
                }
            }
        };
    }

    /**
     * Get all available templates
     */
    getAllTemplates() {
        return Object.entries(this.templates).map(([key, template]) => ({
            id: key,
            ...template
        }));
    }

    /**
     * Get a specific template by ID
     */
    getTemplate(id) {
        return this.templates[id] || null;
    }

    /**
     * Get templates by category
     */
    getTemplatesByCategory() {
        return {
            basic: ['basic', 'niftiOnly'],
            research: ['research', 'longitudinal', 'multiecho'],
            clinical: ['clinical', 'preprocessOnly'],
            examples: ['niftiTestExample']
        };
    }

    /**
     * Generate common BIDS patterns for different scan types
     */
    getBIDSPatterns() {
        return {
            anat: {
                T1w: ['T1w', 'T1_weighted', 'MPRAGE', 'SPGR'],
                T2w: ['T2w', 'T2_weighted', 'TSE'],
                FLAIR: ['FLAIR', 'T2_FLAIR', 'darkfluid'],
                PDw: ['PDw', 'PD', 'proton_density']
            },
            func: {
                'task-rest_bold': ['rest', 'resting', 'resting_state'],
                'task-memory_bold': ['memory', 'n-back', 'working_memory'],
                'task-attention_bold': ['attention', 'cue', 'cueing'],
                'task-emotion_bold': ['emotion', 'faces', 'emotional'],
                'task-motor_bold': ['motor', 'finger_tapping', 'movement']
            },
            fmap: {
                'magnitude1': ['magnitude', 'mag'],
                'magnitude2': ['magnitude', 'mag'],
                'phasediff': ['phase', 'phasediff', '_ph'],
                'fieldmap': ['fieldmap', 'fmap']
            },
            dwi: {
                'dwi': ['dwi', 'DTI', 'diffusion', 'tensor']
            }
        };
    }

    /**
     * Suggest template based on scan types
     */
    suggestTemplate(scans) {
        const scanTypes = this.analyzeScanTypes(scans);
        
        // Multi-echo detection
        if (scanTypes.hasMultiEcho) {
            return 'multiecho';
        }
        
        // Longitudinal detection
        if (scanTypes.hasSessions && scanTypes.sessionCount > 1) {
            return 'longitudinal';
        }
        
        // Research vs clinical
        if (scanTypes.hasFieldmaps && scanTypes.hasMultipleRuns) {
            return 'research';
        }
        
        // Clinical for simple setups
        if (scanTypes.hasMinimalScans) {
            return 'clinical';
        }
        
        return 'basic';
    }

    /**
     * Analyze scan types to suggest appropriate template
     */
    analyzeScanTypes(scans) {
        const analysis = {
            hasMultiEcho: false,
            hasSessions: false,
            sessionCount: 0,
            hasFieldmaps: false,
            hasMultipleRuns: false,
            hasMinimalScans: false,
            scanCount: scans.length
        };
        
        const sessions = new Set();
        let runCounts = {};
        
        scans.forEach(scan => {
            // Multi-echo detection
            if (/_e\d+/.test(scan)) {
                analysis.hasMultiEcho = true;
            }
            
            // Session detection
            const sessionMatch = scan.match(/ses-(\w+)/i);
            if (sessionMatch) {
                analysis.hasSessions = true;
                sessions.add(sessionMatch[1]);
            }
            
            // Fieldmap detection
            if (/fmap|fieldmap|phase|magnitude/i.test(scan)) {
                analysis.hasFieldmaps = true;
            }
            
            // Run counting
            const runMatch = scan.match(/run-(\d+)/i);
            if (runMatch) {
                const taskMatch = scan.match(/task-(\w+)/i);
                const task = taskMatch ? taskMatch[1] : 'default';
                runCounts[task] = (runCounts[task] || 0) + 1;
            }
        });
        
        analysis.sessionCount = sessions.size;
        analysis.hasMultipleRuns = Object.values(runCounts).some(count => count > 1);
        analysis.hasMinimalScans = scans.length <= 3;
        
        return analysis;
    }

    /**
     * Generate template preview HTML
     */
    generateTemplatePreview(templateId) {
        const template = this.getTemplate(templateId);
        if (!template) return '<p>Template not found</p>';
        
        const config = template.config;
        let html = `<div class="template-preview">`;
        html += `<h6>${template.name}</h6>`;
        html += `<p class="text-muted small">${template.description}</p>`;
        
        if (config.bidsnames) {
            html += '<div class="mb-2"><strong>Scan Mappings:</strong></div>';
            Object.entries(config.bidsnames).forEach(([category, mappings]) => {
                html += `<div class="mb-1"><em>${category}:</em> ${Object.keys(mappings).length} scans</div>`;
            });
        }
        
        if (config.fmriprep) {
            html += '<div class="mb-2 mt-2"><strong>fMRIPrep Options:</strong></div>';
            const options = Object.keys(config.fmriprep);
            html += `<div class="small">${options.join(', ')}</div>`;
        }
        
        html += '</div>';
        return html;
    }

    /**
     * Export template as YAML
     */
    exportTemplate(templateId, filename) {
        const template = this.getTemplate(templateId);
        if (!template) return false;
        
        try {
            const yamlContent = jsyaml.dump(template.config, {
                indent: 2,
                lineWidth: 80,
                noRefs: true
            });
            
            const blob = new Blob([yamlContent], { type: 'text/yaml' });
            const url = window.URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = filename || `${templateId}-template.yaml`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            return true;
        } catch (error) {
            console.error('Error exporting template:', error);
            return false;
        }
    }
}

// Export for use in other modules
window.ConfigTemplates = ConfigTemplates;