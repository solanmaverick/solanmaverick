// xlsx.js - Standalone implementation for WeChat Mini Program
// Supports basic Excel file parsing without external dependencies

const XLSX = {
  // File type constants
  FILE_TYPES: {
    XLSX: 'xlsx',
    XLS: 'xls',
    CSV: 'csv'
  },

  // Magic numbers for file type detection
  SIGNATURES: {
    XLSX: [0x50, 0x4B, 0x03, 0x04], // PK.. signature for XLSX
    XLS: [0xD0, 0xCF, 0x11, 0xE0],  // D0CF11E0 signature for XLS
  },

  // Detect file type from buffer
  detectFileType(buffer) {
    if (!buffer || buffer.length < 4) return null;
    
    const bytes = new Uint8Array(buffer.slice(0, 4));
    
    // Check XLSX signature
    if (bytes[0] === 0x50 && bytes[1] === 0x4B && bytes[2] === 0x03 && bytes[3] === 0x04) {
      return this.FILE_TYPES.XLSX;
    }
    
    // Check XLS signature
    if (bytes[0] === 0xD0 && bytes[1] === 0xCF && bytes[2] === 0x11 && bytes[3] === 0xE0) {
      return this.FILE_TYPES.XLS;
    }
    
    // Check if it might be CSV (text file)
    const textDecoder = new TextDecoder();
    const text = textDecoder.decode(buffer.slice(0, 1024));
    if (/^[\w,"'\s]*$/.test(text)) {
      return this.FILE_TYPES.CSV;
    }
    
    return null;
  },

  // Parse workbook from buffer
  read(buffer) {
    const fileType = this.detectFileType(buffer);
    if (!fileType) {
      throw new Error('Unsupported file format');
    }

    switch (fileType) {
      case this.FILE_TYPES.CSV:
        return this.parseCSV(buffer);
      case this.FILE_TYPES.XLSX:
        return this.parseXLSX(buffer);
      case this.FILE_TYPES.XLS:
        return this.parseXLS(buffer);
      default:
        throw new Error('Unsupported file format');
    }
  },

  // Parse CSV data
  parseCSV(buffer) {
    const textDecoder = new TextDecoder();
    const content = textDecoder.decode(buffer);
    const lines = content.split(/\r?\n/);
    const headers = lines[0].split(',').map(h => h.trim());
    
    const data = [];
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      
      const values = lines[i].split(',').map(v => v.trim());
      const row = {};
      headers.forEach((header, index) => {
        row[header] = values[index] || '';
      });
      data.push(row);
    }

    return {
      SheetNames: ['Sheet1'],
      Sheets: {
        'Sheet1': {
          data,
          range: { s: { r: 0, c: 0 }, e: { r: data.length, c: headers.length } }
        }
      }
    };
  },

  // Parse XLSX data (basic implementation)
  parseXLSX(buffer) {
    // For now, return error as XLSX binary parsing is complex
    // This should be implemented based on specific needs
    throw new Error('XLSX parsing not implemented');
  },

  // Parse XLS data (basic implementation)
  parseXLS(buffer) {
    // For now, return error as XLS binary parsing is complex
    // This should be implemented based on specific needs
    throw new Error('XLS parsing not implemented');
  },

  // Utility functions
  utils: {
    // Convert column index to letter (e.g., 0 -> 'A', 1 -> 'B')
    columnToLetter(column) {
      let temp = column;
      let letter = '';
      while (temp >= 0) {
        letter = String.fromCharCode((temp % 26) + 65) + letter;
        temp = Math.floor(temp / 26) - 1;
      }
      return letter;
    },

    // Convert letter to column index (e.g., 'A' -> 0, 'B' -> 1)
    letterToColumn(letter) {
      let column = 0;
      for (let i = 0; i < letter.length; i++) {
        column += (letter.charCodeAt(i) - 64) * Math.pow(26, letter.length - i - 1);
      }
      return column - 1;
    }
  }
};

export default XLSX;
