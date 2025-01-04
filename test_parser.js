import fs from 'fs';
import { parseExcelFile } from './utils/excel-parser.js';

async function testParser() {
    try {
        // Read the test file
        const fileData = fs.readFileSync('./test_dynamic.xlsx');
        
        // Parse the file using our modified parser
        const result = await parseExcelFile(fileData);
        
        console.log('Parsed Headers:', result.headers);
        console.log('\nFirst Row Data:');
        console.log(JSON.stringify(result.rows[0], null, 2));
        
        // Verify fixed attributes are present
        const fixedAttributes = ['学校名称', '专业名称', '学校代码', '专业代码', '位次差'];
        const missingFixed = fixedAttributes.filter(attr => !result.headers.includes(attr));
        console.log('\nMissing Fixed Attributes (should be empty):', missingFixed);
        
        // Verify dynamic attributes are preserved
        const dynamicAttributes = result.headers.filter(h => !fixedAttributes.includes(h));
        console.log('\nDynamic Attributes Found:', dynamicAttributes);
        
    } catch (error) {
        console.error('Test failed:', error);
    }
}

testParser();
