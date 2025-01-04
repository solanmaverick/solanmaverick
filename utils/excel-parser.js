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
      
      // Extract headers from the first row
      const headers = firstSheet.data[0] || [];
      console.debug('Extracted headers:', headers);
      
      // Process data rows (skip header row)
      const data = firstSheet.data.slice(1).map(row => {
        return row.map(cell => ({
          value: cell || '',
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
