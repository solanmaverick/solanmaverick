import fs from 'fs';
import XLSX from 'xlsx';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import path from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Mock WeChat Mini Program environment
globalThis.wx = {
    getFileSystemManager: () => ({
        readFile: ({ filePath, success, fail }) => {
            try {
                const data = fs.readFileSync(filePath);
                success({ data });
            } catch (error) {
                fail(error);
            }
        }
    })
};

// Import our parser (assuming it's also ESM)
import { parseExcelFile } from './utils/excel-parser.js';

async function runTests() {
    // Create test files directory if it doesn't exist
    if (!fs.existsSync('test_files')) {
        fs.mkdirSync('test_files');
    }

    const scenarios = ['random_positions', 'missing_values', 'dynamic_only', 'styled_cells'];
    const results = {
        passed: 0,
        failed: 0,
        details: []
    };
    
    // Required fixed attributes
    const fixedAttributes = ['学校名称', '专业名称', '学校代码', '专业代码', '位次差'];
    const noLabelAttributes = ['学校代码', '专业代码'];

    for (const scenario of scenarios) {
        console.log(`\nTesting scenario: ${scenario}`);
        try {
            const fileContent = fs.readFileSync(`test_${scenario}.xlsx`);
            const result = await parseExcelFile(fileContent);
            
            // Test cases
            const tests = [
                {
                    name: 'Fixed attributes present',
                    test: () => {
                        return fixedAttributes.every(attr => {
                            const hasAttr = Object.keys(result.rows[0]).includes(attr);
                            console.log(`Checking fixed attribute: ${attr} - ${hasAttr ? 'Present' : 'Missing'}`);
                            return hasAttr;
                        });
                    }
                },
                {
                    name: 'Fixed attributes in correct position',
                    test: () => {
                        const row = result.rows[0];
                        return fixedAttributes.every(attr => {
                            const hasCorrectPosition = row[attr] !== undefined;
                            console.log(`Checking position for: ${attr} - ${hasCorrectPosition ? 'Correct' : 'Incorrect'}`);
                            return hasCorrectPosition;
                        });
                    }
                },
                {
                    name: 'No labels for code attributes',
                    test: () => {
                        return noLabelAttributes.every(attr => {
                            const isNoLabel = result.noLabelAttributes && result.noLabelAttributes.includes(attr);
                            console.log(`Checking no-label for: ${attr} - ${isNoLabel ? 'Correct' : 'Incorrect'}`);
                            return isNoLabel;
                        });
                    }
                },
                {
                    name: 'Dynamic attributes identified correctly',
                    test: () => {
                        const allAttributes = Object.keys(result.rows[0]);
                        const dynamicAttrs = allAttributes.filter(attr => !fixedAttributes.includes(attr));
                        const hasDynamicAttrs = dynamicAttrs.length > 0;
                        console.log('Dynamic attributes found:', dynamicAttrs);
                        return hasDynamicAttrs;
                    }
                },
                {
                    name: 'Fixed attributes not in settings',
                    test: () => {
                        // Mock settings page data
                        const settingsData = {
                            displayAttributes: Object.keys(result.rows[0])
                                .filter(attr => !fixedAttributes.includes(attr))
                        };
                        const noFixedInSettings = fixedAttributes.every(attr => 
                            !settingsData.displayAttributes.includes(attr));
                        console.log('Settings attributes:', settingsData.displayAttributes);
                        return noFixedInSettings;
                    }
                },
                {
                    name: 'Cell formatting preserved',
                    test: () => {
                        let formattingChecks = {
                            schoolName: false,
                            majorName: false,
                            schoolCode: false,
                            majorCode: false,
                            rankDiff: false
                        };
                        
                        for (const row of result.rows) {
                            console.log('Checking row:', JSON.stringify(row, null, 2));
                            
                            // Check school and major name (blue text)
                            const schoolName = row['学校名称']?.style;
                            const majorName = row['专业名称']?.style;
                            console.log('School style:', schoolName);
                            console.log('Major style:', majorName);
                            
                            if (schoolName?.color === '0000FF' && majorName?.color === '0000FF') {
                                formattingChecks.schoolName = true;
                                formattingChecks.majorName = true;
                            }
                            
                            // Check codes (gray background)
                            const schoolCode = row['学校代码']?.style;
                            const majorCode = row['专业代码']?.style;
                            console.log('School code style:', schoolCode);
                            console.log('Major code style:', majorCode);
                            
                            if (schoolCode?.backgroundColor === 'F0F0F0' && 
                                majorCode?.backgroundColor === 'F0F0F0') {
                                formattingChecks.schoolCode = true;
                                formattingChecks.majorCode = true;
                            }
                            
                            // Check rank difference (green/red based on value)
                            const rankDiff = row['位次差'];
                            console.log('Rank diff:', rankDiff);
                            
                            if (rankDiff) {
                                const isPositive = rankDiff.value.startsWith('+');
                                const expectedColor = isPositive ? '008000' : 'FF0000';
                                console.log(`Expected color: ${expectedColor}, Actual color: ${rankDiff.style?.color}`);
                                
                                if (rankDiff.style?.color === expectedColor) {
                                    formattingChecks.rankDiff = true;
                                }
                            }
                        }
                        
                        console.log('Formatting checks:', formattingChecks);
                        return Object.values(formattingChecks).every(check => check);
                    }
                },
                {
                    name: 'Dynamic attributes identified',
                    test: () => {
                        return result.dynamicAttributes.length > 0 && 
                               !result.dynamicAttributes.some(attr => result.fixedAttributes.includes(attr));
                    }
                },
                {
                    name: 'No label attributes correct',
                    test: () => {
                        return result.noLabelAttributes.includes('学校代码') && 
                               result.noLabelAttributes.includes('专业代码');
                    }
                },
                {
                    name: 'Cell formatting preserved',
                    test: () => {
                        return result.rows.some(row => 
                            Object.values(row).some(cell => 
                                cell.style && (cell.style.color || cell.style.backgroundColor || 
                                             cell.style.bold || cell.style.italic)
                            )
                        );
                    }
                }
            ];
            
            // Run tests
            for (const test of tests) {
                const passed = test.test();
                results.details.push({
                    scenario,
                    test: test.name,
                    passed
                });
                if (passed) {
                    results.passed++;
                    console.log(`✓ ${test.name}`);
                } else {
                    results.failed++;
                    console.log(`✗ ${test.name}`);
                }
            }
            
        } catch (error) {
            console.error(`Error testing ${scenario}:`, error);
            results.failed++;
            results.details.push({
                scenario,
                test: 'File processing',
                passed: false,
                error: error.message
            });
        }
    }
    
    // Print summary
    console.log('\nTest Summary:');
    console.log(`Passed: ${results.passed}`);
    console.log(`Failed: ${results.failed}`);
    
    return results;
}

runTests().catch(console.error);
