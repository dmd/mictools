/**
 * Scan Parser Module for iris-fmriprep Configuration Generator
 * Analyzes NIFTI filenames and extracts metadata for BIDS conversion
 */

class ScanParser {
    constructor() {
        this.scans = [];
        this.analysisResults = {};
    }

    /**
     * Parse scan names from various input sources
     */
    parseScans(scanList) {
        this.scans = scanList.filter(scan => scan.trim().length > 0);
        this.analyzeScanPatterns();
        return this.scans;
    }

    /**
     * Analyze scan patterns to detect common naming conventions
     */
    analyzeScanPatterns() {
        this.analysisResults = {
            multiecho: this.detectMultiEcho(),
            scanTypes: this.categorizeScanTypes(),
            sessions: this.detectSessions(),
            duplicates: this.detectDuplicates()
        };
    }

    /**
     * Detect multi-echo sequences
     */
    detectMultiEcho() {
        const multiEchoGroups = {};
        const multiEchoPattern = /^(.+)_(\d+)_e(\d+)(\..+)?$/;
        
        this.scans.forEach(scan => {
            const match = scan.match(multiEchoPattern);
            if (match) {
                const [, baseName, scanNumber, echoNumber] = match;
                const groupKey = `${baseName}_${scanNumber}`;
                
                if (!multiEchoGroups[groupKey]) {
                    multiEchoGroups[groupKey] = [];
                }
                multiEchoGroups[groupKey].push({
                    fullName: scan,
                    baseName,
                    scanNumber,
                    echoNumber: parseInt(echoNumber),
                    originalIndex: this.scans.indexOf(scan)
                });
            }
        });

        // Sort echoes within each group
        Object.keys(multiEchoGroups).forEach(key => {
            multiEchoGroups[key].sort((a, b) => a.echoNumber - b.echoNumber);
        });

        return multiEchoGroups;
    }

    /**
     * Categorize scans by type (anat, func, fmap, etc.) and apply final_scan logic
     */
    categorizeScanTypes() {
        const categories = {
            anat: [],
            func: [],
            fmap: [],
            dwi: [],
            other: []
        };

        // Common patterns for categorization
        const patterns = {
            anat: [
                /t1|T1|MEMPRAGE|mprage|SPGR|spgr/i,
                /t2|T2|TSE|tse|FLAIR|flair/i,
                /pd|PD|proton/i,
                /localizer|scout|AALScout/i
            ],
            func: [
                /bold|BOLD|task|TASK|rest|REST|resting/i,
                /func|FUNC|fmri|FMRI/i,
                /rfMRI|epi|EPI/i
            ],
            fmap: [
                /fmap|fieldmap|FIELDMAP/i,
                /distortion|DISTORTION/i,
                /_ph\.nii|_phase/i,
                /gre|GRE.*field/i
            ],
            dwi: [
                /dwi|DWI|dti|DTI|diffusion|DIFFUSION/i,
                /tensor|TENSOR/i
            ]
        };

        // First, group scans by base name (before the final number)
        const scanGroups = this.groupScansByBaseName();

        // For each group, apply final_scan logic and create one entry per base name
        Object.entries(scanGroups).forEach(([baseName, scans]) => {
            const finalScans = this.applyFinalScanLogic(scans);
            
            // Only need to categorize once per base name (not per individual scan)
            if (finalScans.length > 0) {
                const representativeScan = finalScans[0]; // Use first scan for pattern matching
                let categorized = false;
                
                for (const [category, patternList] of Object.entries(patterns)) {
                    if (patternList.some(pattern => pattern.test(representativeScan))) {
                        categories[category].push({
                            yamlKey: baseName,  // This is what goes in YAML
                            displayName: baseName, // This is what user sees
                            finalScans: finalScans, // The actual scans that would be processed
                            isMultiEcho: finalScans.some(scan => this.isMultiEcho(scan)),
                            scanCount: scans.length // How many scans were in this group
                        });
                        categorized = true;
                        break;
                    }
                }
                
                if (!categorized) {
                    categories.other.push({
                        yamlKey: baseName,
                        displayName: baseName,
                        finalScans: finalScans,
                        isMultiEcho: finalScans.some(scan => this.isMultiEcho(scan)),
                        scanCount: scans.length
                    });
                }
            }
        });

        return categories;
    }

    /**
     * Group scans by base name (mimicking converters.py logic)
     * The base name is what goes in the YAML - without trailing numbers or echo suffixes
     */
    groupScansByBaseName() {
        const groups = {};
        
        this.scans.forEach(scan => {
            // Extract base name by removing the final number and echo suffixes
            // This matches the logic in converters.py where scanname is used in glob(scanname + "*[0-9].nii.gz")
            let baseName;
            
            // Check if it's a multi-echo scan: name_number_eX[_suffix] -> name
            const multiEchoMatch = scan.match(/^(.+)_\d+_e\d+(?:_\w+)?$/);
            if (multiEchoMatch) {
                baseName = multiEchoMatch[1];
            } else {
                // Regular scan: name_number[_suffix] -> name
                const regularMatch = scan.match(/^(.+)_\d+(?:_\w+)?$/);
                if (regularMatch) {
                    baseName = regularMatch[1];
                } else {
                    // No number at the end, treat as unique
                    baseName = scan;
                }
            }
            
            if (!groups[baseName]) {
                groups[baseName] = [];
            }
            groups[baseName].push(scan);
        });
        
        return groups;
    }

    /**
     * Apply final_scan logic from converters.py
     */
    applyFinalScanLogic(scans) {
        if (scans.length <= 1) {
            return scans;
        }

        // Check if these are multi-echo scans (may have suffixes like _ph)
        const isMultiEcho = scans.some(scan => /_e\d+(?:_\w+)?$/.test(scan));
        
        const files = {};
        
        scans.forEach(scan => {
            let match;
            if (isMultiEcho) {
                // Multi-echo pattern: _(\d+)_e\d+[_suffix]$
                match = scan.match(/_(\d+)_e\d+(?:_\w+)?$/);
            } else {
                // Regular pattern: _(\d+)[_suffix]$
                match = scan.match(/_(\d+)(?:_\w+)?$/);
            }
            
            if (match) {
                const fid = parseInt(match[1]);
                
                // Ignore files with numbers >= 1000 (as in converters.py)
                if (fid >= 1000) {
                    return;
                }
                
                if (!files[fid]) {
                    files[fid] = [];
                }
                files[fid].push(scan);
            }
        });
        
        // Get the highest numbered group
        const ids = Object.keys(files).map(id => parseInt(id)).sort((a, b) => a - b);
        if (ids.length === 0) {
            return scans; // Fallback if no numbered scans found
        }
        
        const highestId = ids[ids.length - 1];
        return files[highestId].sort();
    }

    /**
     * Check if a scan is part of a multi-echo sequence
     */
    isMultiEcho(scanName) {
        return Object.values(this.analysisResults.multiecho || {})
            .some(group => group.some(echo => echo.fullName === scanName));
    }

    /**
     * Detect session information from scan names
     */
    detectSessions() {
        const sessions = new Set();
        const sessionPattern = /ses-(\w+)|session[_-]?(\d+)/i;
        
        this.scans.forEach(scan => {
            const match = scan.match(sessionPattern);
            if (match) {
                const sessionId = match[1] || match[2];
                sessions.add(sessionId);
            }
        });
        
        return Array.from(sessions).sort();
    }

    /**
     * Detect potential duplicate scans (same base name, different numbers)
     */
    detectDuplicates() {
        const groups = {};
        const duplicates = [];
        
        this.scans.forEach((scan, index) => {
            // Extract base name by removing trailing numbers and extensions
            const baseName = scan.replace(/[_-]\d+(\.[^.]+)*$/, '');
            
            if (!groups[baseName]) {
                groups[baseName] = [];
            }
            groups[baseName].push({ scan, index });
        });
        
        // Find groups with multiple scans
        Object.entries(groups).forEach(([baseName, scans]) => {
            if (scans.length > 1) {
                duplicates.push({
                    baseName,
                    scans: scans,
                    recommended: this.selectFinalScan(scans.map(s => s.scan))
                });
            }
        });
        
        return duplicates;
    }

    /**
     * Select the final scan from a group (highest number < 1000)
     */
    selectFinalScan(scanGroup) {
        const numberPattern = /_(\d+)(?:\.nii\.gz|\.json)?$/;
        let maxValidScan = null;
        let maxNumber = -1;
        
        scanGroup.forEach(scan => {
            const match = scan.match(numberPattern);
            if (match) {
                const number = parseInt(match[1]);
                if (number < 1000 && number > maxNumber) {
                    maxNumber = number;
                    maxValidScan = scan;
                }
            }
        });
        
        return maxValidScan || scanGroup[scanGroup.length - 1];
    }

    /**
     * Generate suggested BIDS names based on original scan names
     */
    generateBIDSSuggestions() {
        const suggestions = {
            anat: {},
            func: {},
            fmap: {},
            dwi: {},
            other: {}
        };

        Object.entries(this.analysisResults.scanTypes).forEach(([category, scans]) => {
            scans.forEach(scanInfo => {
                const yamlKey = scanInfo.yamlKey;
                const representativeScan = scanInfo.finalScans[0]; // Use first scan for pattern matching
                const bidsName = this.suggestBIDSName(representativeScan, category);
                
                if (bidsName) {
                    suggestions[category][yamlKey] = bidsName;
                }
            });
        });

        return suggestions;
    }

    /**
     * Suggest BIDS-compliant names based on original scan names
     */
    suggestBIDSName(originalName, category) {
        // Remove common suffixes and numbers
        const cleanName = originalName
            .replace(/\.nii\.gz$/, '')
            .replace(/\.json$/, '')
            .replace(/_\d+(_e\d+)?$/, '');

        const suggestions = {
            anat: {
                't1|T1|MEMPRAGE|mprage': 'T1w',
                't2|T2|tse|TSE': 'T2w', 
                'flair|FLAIR|darkfluid': 'FLAIR',
                'pd|PD': 'PDw',
                'localizer|scout|AALScout': 'T1w'
            },
            func: {
                'rest|REST|resting': 'task-rest_bold',
                'task|TASK': name => {
                    const taskMatch = name.match(/task[_-]?([a-zA-Z0-9]+)/i);
                    const taskName = taskMatch ? taskMatch[1].toLowerCase() : 'unknown';
                    return `task-${taskName}_bold`;
                },
                'cue': 'task-cue_bold',
                'fid': 'task-fid_bold',
                'wtp': 'task-wtp_bold',
                'bold|BOLD': 'task-unknown_bold'
            },
            fmap: {
                'fmap|fieldmap': 'fieldmap',
                'distortion': 'epi',
                '_ph|phase': 'phasediff'
            }
        };

        const categoryPatterns = suggestions[category] || {};
        
        for (const [pattern, suggestion] of Object.entries(categoryPatterns)) {
            if (new RegExp(pattern, 'i').test(cleanName)) {
                if (typeof suggestion === 'function') {
                    return suggestion(cleanName);
                }
                return suggestion;
            }
        }

        // Default suggestions
        const defaults = {
            anat: 'T1w',
            func: 'task-unknown_bold',
            fmap: 'fieldmap',
            dwi: 'dwi'
        };

        return defaults[category] || 'unknown';
    }

    /**
     * Get analysis results
     */
    getAnalysisResults() {
        return this.analysisResults;
    }

    /**
     * Get categorized scans
     */
    getCategorizedScans() {
        return this.analysisResults.scanTypes || {};
    }
}

// Export for use in other modules
window.ScanParser = ScanParser;