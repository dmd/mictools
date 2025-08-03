/**
 * BIDS Validator Module for iris-fmriprep Configuration Generator
 * Validates BIDS naming conventions and provides recommendations
 */

class BIDSValidator {
    constructor() {
        this.validationRules = this.initializeValidationRules();
    }

    /**
     * Initialize BIDS validation rules
     */
    initializeValidationRules() {
        return {
            // Valid BIDS entities and their patterns
            entities: {
                'sub': /^[a-zA-Z0-9]+$/,
                'ses': /^[a-zA-Z0-9]+$/,
                'task': /^[a-zA-Z0-9]+$/,
                'acq': /^[a-zA-Z0-9]+$/,
                'ce': /^[a-zA-Z0-9]+$/,
                'dir': /^[a-zA-Z0-9]+$/,
                'rec': /^[a-zA-Z0-9]+$/,
                'run': /^\d+$/,
                'mod': /^[a-zA-Z0-9]+$/,
                'echo': /^\d+$/,
                'flip': /^\d+$/,
                'inv': /^\d+$/,
                'mt': /^(on|off)$/,
                'part': /^(mag|phase|real|imag)$/,
                'proc': /^[a-zA-Z0-9]+$/
            },

            // Valid suffixes for each modality
            suffixes: {
                anat: ['T1w', 'T2w', 'T1rho', 'T1map', 'T2map', 'T2star', 'FLAIR', 'FLASH', 'PDw', 'PDmap', 'PD', 'inplaneT1', 'inplaneT2', 'angio', 'defacemask'],
                func: ['bold', 'cbv', 'sbref'],
                fmap: ['phasediff', 'phase1', 'phase2', 'magnitude1', 'magnitude2', 'magnitude', 'fieldmap', 'epi'],
                dwi: ['dwi', 'sbref'],
                perf: ['asl', 'cbf', 'm0scan'],
                meg: ['meg'],
                eeg: ['eeg'],
                ieeg: ['ieeg']
            },

            // Entity order for different modalities
            entityOrder: {
                anat: ['sub', 'ses', 'acq', 'ce', 'rec', 'run', 'mod'],
                func: ['sub', 'ses', 'task', 'acq', 'ce', 'dir', 'rec', 'run', 'echo'],
                fmap: ['sub', 'ses', 'acq', 'ce', 'dir', 'rec', 'run', 'echo', 'flip', 'inv', 'mt', 'part'],
                dwi: ['sub', 'ses', 'acq', 'ce', 'dir', 'rec', 'run'],
                perf: ['sub', 'ses', 'acq', 'ce', 'dir', 'rec', 'run', 'asl']
            },

            // Required entities for each modality
            requiredEntities: {
                func: ['task']
            }
        };
    }

    /**
     * Validate a BIDS filename
     */
    validateBIDSName(filename, modality = 'func') {
        const validation = {
            isValid: true,
            errors: [],
            warnings: [],
            suggestions: []
        };

        try {
            const parsed = this.parseBIDSName(filename);
            
            // Check suffix validity
            this.validateSuffix(parsed.suffix, modality, validation);
            
            // Check entity format and values
            this.validateEntities(parsed.entities, modality, validation);
            
            // Check entity order
            this.validateEntityOrder(parsed.entities, modality, validation);
            
            // Check required entities
            this.validateRequiredEntities(parsed.entities, modality, validation);
            
            // Check for common issues
            this.checkCommonIssues(filename, validation);
            
        } catch (error) {
            validation.isValid = false;
            validation.errors.push(`Failed to parse BIDS name: ${error.message}`);
        }

        return validation;
    }

    /**
     * Parse a BIDS filename into components
     */
    parseBIDSName(filename) {
        // Remove file extensions
        const cleanName = filename.replace(/\.(nii\.gz|nii|json|tsv|bval|bvec)$/, '');
        
        // Split into parts
        const parts = cleanName.split('_');
        const suffix = parts[parts.length - 1];
        const entityParts = parts.slice(0, -1);
        
        const entities = {};
        const entityOrder = [];
        
        entityParts.forEach(part => {
            const match = part.match(/^([a-zA-Z0-9]+)-(.+)$/);
            if (match) {
                const [, key, value] = match;
                entities[key] = value;
                entityOrder.push(key);
            } else {
                throw new Error(`Invalid entity format: ${part}`);
            }
        });
        
        return {
            entities,
            entityOrder,
            suffix,
            fullName: cleanName
        };
    }

    /**
     * Validate suffix for the given modality
     */
    validateSuffix(suffix, modality, validation) {
        const validSuffixes = this.validationRules.suffixes[modality];
        if (validSuffixes && !validSuffixes.includes(suffix)) {
            validation.isValid = false;
            validation.errors.push(`Invalid suffix '${suffix}' for modality '${modality}'. Valid suffixes: ${validSuffixes.join(', ')}`);
            
            // Suggest closest match
            const suggestion = this.findClosestMatch(suffix, validSuffixes);
            if (suggestion) {
                validation.suggestions.push(`Did you mean '${suggestion}'?`);
            }
        }
    }

    /**
     * Validate entity formats and values
     */
    validateEntities(entities, modality, validation) {
        Object.entries(entities).forEach(([key, value]) => {
            // Check if entity is recognized
            if (!this.validationRules.entities[key]) {
                validation.warnings.push(`Unrecognized entity '${key}'. This may not be standard BIDS.`);
                return;
            }
            
            // Check entity value format
            const pattern = this.validationRules.entities[key];
            if (!pattern.test(value)) {
                validation.isValid = false;
                validation.errors.push(`Invalid value '${value}' for entity '${key}'. Expected pattern: ${pattern}`);
            }
            
            // Special validations
            this.validateSpecialEntities(key, value, validation);
        });
    }

    /**
     * Validate special entity rules
     */
    validateSpecialEntities(key, value, validation) {
        switch (key) {
            case 'task':
                if (value.length === 0) {
                    validation.errors.push("Task label cannot be empty");
                }
                if (!/^[a-zA-Z]/.test(value)) {
                    validation.warnings.push("Task labels should start with a letter");
                }
                break;
                
            case 'run':
                const runNum = parseInt(value);
                if (runNum < 1) {
                    validation.errors.push("Run numbers should start from 1");
                }
                if (value.length > 1 && value[0] === '0') {
                    validation.warnings.push("Run numbers should not have leading zeros");
                }
                break;
                
            case 'echo':
                const echoNum = parseInt(value);
                if (echoNum < 1) {
                    validation.errors.push("Echo numbers should start from 1");
                }
                break;
        }
    }

    /**
     * Validate entity order
     */
    validateEntityOrder(entities, modality, validation) {
        const expectedOrder = this.validationRules.entityOrder[modality];
        if (!expectedOrder) return;
        
        const actualOrder = Object.keys(entities);
        const filteredExpectedOrder = expectedOrder.filter(entity => actualOrder.includes(entity));
        
        for (let i = 0; i < filteredExpectedOrder.length; i++) {
            const expectedEntity = filteredExpectedOrder[i];
            const actualIndex = actualOrder.indexOf(expectedEntity);
            
            if (actualIndex !== -1 && actualIndex !== i) {
                validation.warnings.push(`Entity order issue: '${expectedEntity}' should come before other entities. Expected order: ${expectedOrder.join(', ')}`);
                break;
            }
        }
    }

    /**
     * Validate required entities
     */
    validateRequiredEntities(entities, modality, validation) {
        const required = this.validationRules.requiredEntities[modality];
        if (!required) return;
        
        required.forEach(entity => {
            if (!entities[entity]) {
                validation.isValid = false;
                validation.errors.push(`Missing required entity '${entity}' for modality '${modality}'`);
            }
        });
    }

    /**
     * Check for common BIDS naming issues
     */
    checkCommonIssues(filename, validation) {
        // Check for spaces
        if (filename.includes(' ')) {
            validation.isValid = false;
            validation.errors.push("BIDS names cannot contain spaces");
        }
        
        // Check for special characters
        const invalidChars = /[^a-zA-Z0-9\-_]/;
        if (invalidChars.test(filename)) {
            validation.isValid = false;
            validation.errors.push("BIDS names can only contain alphanumeric characters, hyphens, and underscores");
        }
        
        // Check for consecutive underscores
        if (filename.includes('__')) {
            validation.warnings.push("Avoid consecutive underscores in BIDS names");
        }
        
        // Check length
        if (filename.length > 255) {
            validation.warnings.push("Filename is very long. Consider shortening entity values.");
        }
        
        // Check for uppercase in entity values
        const parts = filename.split('_');
        parts.forEach(part => {
            if (part.includes('-') && /[A-Z]/.test(part.split('-')[1])) {
                validation.warnings.push(`Consider using lowercase for entity values: ${part}`);
            }
        });
    }

    /**
     * Find closest match using simple string similarity
     */
    findClosestMatch(target, candidates) {
        let bestMatch = null;
        let bestScore = 0;
        
        candidates.forEach(candidate => {
            const score = this.stringSimilarity(target, candidate);
            if (score > bestScore && score > 0.5) {
                bestScore = score;
                bestMatch = candidate;
            }
        });
        
        return bestMatch;
    }

    /**
     * Calculate string similarity (simple implementation)
     */
    stringSimilarity(str1, str2) {
        const longer = str1.length > str2.length ? str1 : str2;
        const shorter = str1.length > str2.length ? str2 : str1;
        
        if (longer.length === 0) return 1.0;
        
        const distance = this.levenshteinDistance(longer, shorter);
        return (longer.length - distance) / longer.length;
    }

    /**
     * Calculate Levenshtein distance
     */
    levenshteinDistance(str1, str2) {
        const matrix = Array(str2.length + 1).fill(null).map(() => Array(str1.length + 1).fill(null));
        
        for (let i = 0; i <= str1.length; i++) matrix[0][i] = i;
        for (let j = 0; j <= str2.length; j++) matrix[j][0] = j;
        
        for (let j = 1; j <= str2.length; j++) {
            for (let i = 1; i <= str1.length; i++) {
                const substitutionCost = str1[i - 1] === str2[j - 1] ? 0 : 1;
                matrix[j][i] = Math.min(
                    matrix[j][i - 1] + 1,
                    matrix[j - 1][i] + 1,
                    matrix[j - 1][i - 1] + substitutionCost
                );
            }
        }
        
        return matrix[str2.length][str1.length];
    }

    /**
     * Generate BIDS-compliant name suggestion
     */
    generateBIDSSuggestion(originalName, modality, options = {}) {
        const {
            subject = 'SUBJECT',
            session = null,
            task = null,
            run = null,
            acquisition = null,
            direction = null
        } = options;

        const entities = [];
        
        // Always start with subject
        entities.push(`sub-${subject}`);
        
        // Add session if provided
        if (session) {
            entities.push(`ses-${session}`);
        }
        
        // Add modality-specific entities
        if (modality === 'func') {
            if (task) {
                entities.push(`task-${task}`);
            } else {
                // Try to extract task from original name
                const taskMatch = originalName.match(/(?:task|TASK)[_-]?([a-zA-Z0-9]+)/i);
                if (taskMatch) {
                    entities.push(`task-${taskMatch[1].toLowerCase()}`);
                } else if (/rest|REST|resting/i.test(originalName)) {
                    entities.push('task-rest');
                } else {
                    entities.push('task-unknown');
                }
            }
        }
        
        // Add optional entities
        if (acquisition) entities.push(`acq-${acquisition}`);
        if (direction) entities.push(`dir-${direction}`);
        if (run) entities.push(`run-${run.toString().padStart(2, '0')}`);
        
        // Add appropriate suffix
        const suffix = this.getSuffixForModality(modality, originalName);
        entities.push(suffix);
        
        return entities.join('_');
    }

    /**
     * Get appropriate suffix for modality
     */
    getSuffixForModality(modality, originalName) {
        const suffixMaps = {
            anat: {
                't1|T1|MEMPRAGE|mprage': 'T1w',
                't2|T2|tse|TSE': 'T2w',
                'flair|FLAIR': 'FLAIR',
                'pd|PD': 'PDw'
            },
            func: {
                'bold|BOLD': 'bold'
            },
            fmap: {
                'fieldmap|fmap': 'fieldmap',
                'phase|_ph': 'phasediff',
                'magnitude|mag': 'magnitude'
            }
        };
        
        const patterns = suffixMaps[modality] || {};
        
        for (const [pattern, suffix] of Object.entries(patterns)) {
            if (new RegExp(pattern, 'i').test(originalName)) {
                return suffix;
            }
        }
        
        // Default suffixes
        const defaults = {
            anat: 'T1w',
            func: 'bold',
            fmap: 'fieldmap',
            dwi: 'dwi'
        };
        
        return defaults[modality] || 'unknown';
    }

    /**
     * Get valid entities for a modality
     */
    getValidEntitiesForModality(modality) {
        return this.validationRules.entityOrder[modality] || [];
    }

    /**
     * Get valid suffixes for a modality
     */
    getValidSuffixesForModality(modality) {
        return this.validationRules.suffixes[modality] || [];
    }
}

// Export for use in other modules
window.BIDSValidator = BIDSValidator;