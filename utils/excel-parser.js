const XLSX = require('miniprogram_npm/xlsx');

const parseExcelFile = (function() {
  // Style extraction helper functions
  const extractCellStyle = (cell) => {
    if (!cell || !cell.s) return null;
    
    console.debug('Extracting style for cell:', cell);
    
    const style = {
      font: {},
      fill: {},
      border: {},
      alignment: {}
    };
    
    // Font properties
    if (cell.s.font) {
      style.font = {
        bold: cell.s.font.bold || false,
        italic: cell.s.font.italic || false,
        underline: cell.s.font.underline || false,
        size: cell.s.font.sz || 11,
        color: extractColor(cell.s.font.color) || '#000000',
        name: cell.s.font.name || 'Arial'
      };
    }
    
    // Fill properties
    if (cell.s.fill) {
      style.fill = {
        type: cell.s.fill.patternType || 'none',
        color: extractColor(cell.s.fill.fgColor) || '#FFFFFF'
      };
    }
    
    // Border properties
    if (cell.s.border) {
      style.border = {
        top: extractBorderStyle(cell.s.border.top),
        right: extractBorderStyle(cell.s.border.right),
        bottom: extractBorderStyle(cell.s.border.bottom),
        left: extractBorderStyle(cell.s.border.left)
      };
    }
    
    // Alignment properties
    if (cell.s.alignment) {
      style.alignment = {
        horizontal: cell.s.alignment.horizontal || 'left',
        vertical: cell.s.alignment.vertical || 'bottom',
        wrapText: cell.s.alignment.wrapText || false
      };
    }
    
    console.debug('Extracted style:', style);
    return style;
  };
  
  const extractColor = (color) => {
    if (!color) return null;
    
    console.debug('Extracting color:', color);
    
    // Handle RGB colors
    if (color.rgb) {
      return `#${color.rgb}`;
    }
    
    // Handle theme colors
    if (color.theme !== undefined) {
      // Theme color mapping (simplified)
      const themeColors = [
        '#FFFFFF', // Theme 0
        '#000000', // Theme 1
        '#E7E6E6', // Theme 2
        '#44546A', // Theme 3
        '#4472C4', // Theme 4
        '#ED7D31', // Theme 5
        '#A5A5A5', // Theme 6
        '#FFC000'  // Theme 7
      ];
      
      const themeColor = themeColors[color.theme] || '#000000';
      console.debug('Theme color mapped:', themeColor);
      return themeColor;
    }
    
    return null;
  };
  
  const extractBorderStyle = (border) => {
    if (!border) return null;
    
    return {
      style: border.style || 'none',
      color: extractColor(border.color) || '#000000'
    };
  };
  
  // Main parsing function
  return function(fileData) {
    try {
      console.debug('Starting Excel file parsing');
      
      const workbook = XLSX.read(fileData, {
        type: 'buffer',
        cellStyles: true,
        cellDates: true,
        cellNF: true
      });
      
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
      console.debug('First sheet name:', workbook.SheetNames[0]);
      
      // Get the range of the sheet
      const range = XLSX.utils.decode_range(firstSheet['!ref']);
      console.debug('Sheet range:', range);
      
      // Extract headers
      const headers = [];
      for (let C = range.s.c; C <= range.e.c; ++C) {
        const headerCell = firstSheet[XLSX.utils.encode_cell({r: range.s.r, c: C})];
        headers.push(headerCell ? headerCell.v : '');
      }
      console.debug('Extracted headers:', headers);
      
      // Process data rows
      const data = [];
      for (let R = range.s.r + 1; R <= range.e.r; ++R) {
        const row = [];
        for (let C = range.s.c; C <= range.e.c; ++C) {
          const cellRef = XLSX.utils.encode_cell({r: R, c: C});
          const cell = firstSheet[cellRef];
          
          if (cell) {
            const cellStyle = extractCellStyle(cell);
            row.push({
              value: cell.v,
              style: cellStyle
            });
          } else {
            row.push({
              value: '',
              style: null
            });
          }
        }
        data.push(row);
      }
      
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

module.exports = {
  parseExcelFile
};
