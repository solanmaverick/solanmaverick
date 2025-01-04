// Test script for XLSX parser
const fs = require('fs');
const { XLSX } = require('./utils/xlsx');

async function testParser() {
  try {
    const filename = process.argv[2] || 'test.xlsx';
    console.log(`Reading ${filename}...`);
    const buffer = fs.readFileSync(filename);
    
    // Additional checks for empty files
    if (buffer.length === 0) {
      throw new Error('File is empty');
    }
    
    console.log('Parsing XLSX file...');
    const workbook = XLSX.read(buffer);
    
    console.log('\nParsed workbook structure:');
    console.log(JSON.stringify(workbook, null, 2));
    
    // Verify the structure
    const sheet = workbook.Sheets.Sheet1;
    if (!sheet) {
      throw new Error('Sheet1 not found in parsed workbook');
    }
    
    console.log('\nVerifying data structure...');
    console.log('Number of rows:', sheet.data.length);
    
    // Test specific cell values and types
    const rows = sheet.data;
    console.log('\nVerifying cell values and types...');
    
    // Check headers
    console.log('Headers (as array):', rows[0]);
    
    // Check first data row if it exists
    if (rows.length > 1) {
      console.log('\nFirst data row (as array):');
      console.log('Column 0 (Name, string):', rows[1][0], typeof rows[1][0]);
      console.log('Column 1 (Age, number):', rows[1][1], typeof rows[1][1]);
      console.log('Column 2 (Score, number):', rows[1][2], typeof rows[1][2]);
    } else {
      console.log('\nNo data rows found (empty sheet)');
    }
    
    console.log('\nTest completed successfully!');
    
  } catch (error) {
    console.error('Test failed:', error.message);
    process.exit(1);
  }
}

// Run the test
testParser();
