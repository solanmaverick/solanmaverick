import XLSX from './xlsx.js';

const parseExcelFile = (function() {
  // Style extraction helper functions
  const extractCellStyle = (cell) => {
    // In our simplified implementation, we don't handle styles yet
    return null;
  };

  // Main parsing function
  return function(fileData) {
    try {
      console.debug('Starting Excel file parsing');
      
      const workbook = XLSX.read(fileData);
      
      if (!workbook || !workbook.Sheets || !workbook.SheetNames || !workbook.SheetNames.length) {
        throw new Error('Invalid workbook structure');
      }
      
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
      console.debug('First sheet name:', workbook.SheetNames[0]);
      
      if (!firstSheet || !firstSheet.data) {
        throw new Error('Invalid sheet data');
      }
      
      // Get all unique column letters as headers
      const headers = Object.keys(firstSheet.data[0] || {}).sort((a, b) => 
        XLSX.utils.letterToColumn(a) - XLSX.utils.letterToColumn(b)
      );
      console.debug('Extracted headers:', headers);
      
      // Process all rows (including first row as it's already in the right format)
      const data = firstSheet.data.map(row => {
        return headers.map(header => ({
          value: row[header] || '',
          style: null // No styles in simplified implementation
        }));
      });
      
      console.debug('Parsed data rows:', data.length);
      
      return {
        success: true,
        headers: headers,
        data: data
      };
      
    } catch (error) {
      console.error('Excel parsing error:', error);
      return {
        success: false,
        error: error.message
      };
    }
  };
})();

export {
  parseExcelFile
};
