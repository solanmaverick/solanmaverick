// xlsx.js - Standalone implementation for WeChat Mini Program
// Supports basic Excel file parsing without external dependencies

const pako = require('pako');

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

  // Convert Buffer to ArrayBuffer
  toArrayBuffer(buffer) {
    if (buffer instanceof ArrayBuffer) {
      return buffer;
    }
    if (Buffer.isBuffer(buffer)) {
      const arrayBuffer = new ArrayBuffer(buffer.length);
      const view = new Uint8Array(arrayBuffer);
      for (let i = 0; i < buffer.length; ++i) {
        view[i] = buffer[i];
      }
      return arrayBuffer;
    }
    throw new Error('Input must be Buffer or ArrayBuffer');
  },

  // Detect file type from buffer
  detectFileType(buffer) {
    if (!buffer || (!buffer.length && !(buffer instanceof ArrayBuffer))) return null;
    
    const arrayBuffer = this.toArrayBuffer(buffer);
    const bytes = new Uint8Array(arrayBuffer.slice(0, 4));
    
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
    const text = textDecoder.decode(new Uint8Array(arrayBuffer.slice(0, 1024)));
    if (/^[\w,"'\s]*$/.test(text)) {
      return this.FILE_TYPES.CSV;
    }
    
    return null;
  },

  // Parse workbook from buffer
  read(buffer) {
    // Convert input to ArrayBuffer
    const arrayBuffer = this.toArrayBuffer(buffer);
    
    const fileType = this.detectFileType(arrayBuffer);
    if (!fileType) {
      throw new Error('Unsupported file format');
    }

    switch (fileType) {
      case this.FILE_TYPES.CSV:
        return this.parseCSV(arrayBuffer);
      case this.FILE_TYPES.XLSX:
        return this.parseXLSX(arrayBuffer);
      case this.FILE_TYPES.XLS:
        return this.parseXLS(arrayBuffer);
      default:
        throw new Error('Unsupported file format');
    }
  },

  // Parse CSV data
  parseCSV(buffer) {
    const arrayBuffer = this.toArrayBuffer(buffer);
    const textDecoder = new TextDecoder();
    const content = textDecoder.decode(new Uint8Array(arrayBuffer));
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

  // ZIP parsing utilities
  parseZIPCentralDirectory(buffer) {
    const arrayBuffer = this.toArrayBuffer(buffer);
    const view = new DataView(arrayBuffer);
    const entries = {};
    let offset = arrayBuffer.byteLength - 22; // Start from end of central directory
    
    // Find end of central directory signature
    while (offset > 0) {
      if (view.getUint32(offset, true) === 0x06054b50) break;
      offset--;
    }
    
    if (offset === 0) throw new Error('Invalid ZIP: No central directory found');
    
    const centralDirOffset = view.getUint32(offset + 16, true);
    const centralDirSize = view.getUint32(offset + 12, true);
    
    // Parse central directory
    offset = centralDirOffset;
    while (offset < centralDirOffset + centralDirSize) {
      if (view.getUint32(offset, true) !== 0x02014b50) {
        throw new Error('Invalid ZIP: Central directory entry corrupted');
      }
      
      const nameLength = view.getUint16(offset + 28, true);
      const extraLength = view.getUint16(offset + 30, true);
      const commentLength = view.getUint16(offset + 32, true);
      
      const compressedSize = view.getUint32(offset + 20, true);
      const uncompressedSize = view.getUint32(offset + 24, true);
      const localHeaderOffset = view.getUint32(offset + 42, true);
      
      // Get filename
      const filename = new TextDecoder().decode(
        new Uint8Array(buffer.slice(offset + 46, offset + 46 + nameLength))
      );
      
      entries[filename] = {
        compressedSize,
        uncompressedSize,
        localHeaderOffset
      };
      
      offset += 46 + nameLength + extraLength + commentLength;
    }
    
    return entries;
  },
  
  extractFileFromZIP(buffer, entry) {
    try {
      console.log(`\nExtracting file: ${entry.filename}`);
      console.log('Entry details:', {
        offset: entry.localHeaderOffset,
        compressedSize: entry.compressedSize,
        uncompressedSize: entry.uncompressedSize
      });

      // Convert buffer to ArrayBuffer if needed
      const arrayBuffer = this.toArrayBuffer(buffer);
      const view = new DataView(arrayBuffer);
      let offset = entry.localHeaderOffset;
      
      // Verify local file header signature (0x04034b50)
      const signature = view.getUint32(offset, true);
      console.log(`Local header signature: 0x${signature.toString(16)}`);
      if (signature !== 0x04034b50) {
        throw new Error(`Invalid ZIP: Local file header corrupted. Found signature: 0x${signature.toString(16)}`);
      }
      
      // Read local file header
      const compressionMethod = view.getUint16(offset + 8, true);
      const compressedSize = view.getUint32(offset + 18, true);
      const uncompressedSize = view.getUint32(offset + 22, true);
      const nameLength = view.getUint16(offset + 26, true);
      const extraLength = view.getUint16(offset + 28, true);
      
      console.log('File header info:', {
        compressionMethod,
        compressedSize,
        uncompressedSize,
        nameLength,
        extraLength
      });
      
      // Skip header and read file name
      offset += 30;
      const fileNameBytes = new Uint8Array(arrayBuffer.slice(offset, offset + nameLength));
      const fileName = new TextDecoder().decode(fileNameBytes);
      console.log('Filename from header:', fileName);
      
      // Skip name and extra field to get to data
      offset += nameLength + extraLength;
      console.log('Data starts at offset:', offset);
      
      // Extract compressed data
      const compressedData = new Uint8Array(arrayBuffer.slice(offset, offset + compressedSize));
      console.log(`Read ${compressedData.length} bytes of compressed data`);
      console.log('First few bytes:', Array.from(compressedData.slice(0, 4)).map(b => b.toString(16).padStart(2, '0')).join(' '));
      
      let decompressedArray;
      if (compressionMethod === 0) {
        // Method 0 - Stored (no compression)
        console.log('Using stored (no compression) method');
        decompressedArray = compressedData;
        if (decompressedArray.length !== uncompressedSize) {
          throw new Error(`Uncompressed size mismatch: expected ${uncompressedSize}, got ${decompressedArray.length}`);
        }
      } else if (compressionMethod === 8) {
        // Method 8 - Deflate
        console.log('Using DEFLATE decompression');
        try {
          decompressedArray = pako.inflate(compressedData);
          console.log(`Decompressed to ${decompressedArray.length} bytes`);
          if (decompressedArray.length !== uncompressedSize) {
            console.warn(`Size mismatch: expected ${uncompressedSize}, got ${decompressedArray.length}`);
          }
        } catch (e) {
          console.error('Decompression failed:', e);
          console.error('First 16 bytes of failed data:', Array.from(compressedData.slice(0, 16)).map(b => b.toString(16).padStart(2, '0')).join(' '));
          throw new Error(`Failed to decompress ZIP entry ${fileName}: ${e.message}`);
        }
      } else {
        throw new Error(`Unsupported compression method: ${compressionMethod}`);
      }
      
      // Try UTF-8 decoding first
      try {
        console.log('Attempting UTF-8 decode');
        const text = new TextDecoder('utf-8').decode(decompressedArray);
        console.log(`Successfully decoded ${text.length} characters`);
        return text;
      } catch (e) {
        // Fallback to ASCII if UTF-8 fails
        console.warn('UTF-8 decoding failed, falling back to ASCII');
        return new TextDecoder('ascii').decode(decompressedArray);
      }
    } catch (e) {
      console.error('Error extracting ZIP file:', e);
      console.error('Stack trace:', e.stack);
      throw e;
    }
  },
  
  unzip(buffer) {
    console.log('Starting unzip process...');
    const entries = this.parseZIPCentralDirectory(buffer);
    console.log('ZIP entries found:', Object.keys(entries));
    const files = {};
    
    // Extract required XML files
    const requiredFiles = [
      'xl/workbook.xml',
      'xl/worksheets/sheet1.xml',
      'xl/sharedStrings.xml'
    ];
    
    for (const filename of requiredFiles) {
      console.log(`\nProcessing ${filename}...`);
      if (entries[filename]) {
        try {
          const content = this.extractFileFromZIP(buffer, entries[filename]);
          console.log(`Extracted ${filename} (${content.length} bytes)`);
          console.log('First 200 chars:', content.slice(0, 200));
          files[filename] = content;
        } catch (e) {
          console.warn(`Failed to extract ${filename}:`, e);
          console.warn('Stack trace:', e.stack);
        }
      } else {
        console.warn(`File not found in ZIP: ${filename}`);
      }
    }
    
    return files;
  },

  // XML parsing utilities
  parseXMLString(xmlStr) {
    console.log('\nStarting XML parsing...');
    if (!xmlStr || typeof xmlStr !== 'string') {
      console.error('Invalid XML input:', typeof xmlStr, xmlStr?.length);
      throw new Error('Invalid XML input');
    }
    
    // Remove comments and normalize whitespace
    xmlStr = xmlStr.replace(/<!--[\s\S]*?-->/g, '')
                   .replace(/>\s+</g, '><')
                   .replace(/^\s+|\s+$/g, '');
    
    const result = {
      nodeType: 'root',
      children: []
    };
    let current = result;
    const stack = [result];
    let pos = 0;
    
    const parseAttributes = (str) => {
      const attrs = {};
      const regex = /([^\s=]+)=["']([^"']*)["']/g;
      let match;
      while ((match = regex.exec(str)) !== null) {
        attrs[match[1]] = match[2];
      }
      return attrs;
    };
    
    while (pos < xmlStr.length) {
      if (xmlStr[pos] === '<') {
        if (xmlStr[pos + 1] === '?') {
          // XML declaration
          const endDecl = xmlStr.indexOf('?>', pos);
          if (endDecl === -1) throw new Error('Invalid XML: Unclosed XML declaration');
          pos = endDecl + 2;
          continue;
        }
        
        if (xmlStr[pos + 1] === '!') {
          if (xmlStr.substr(pos + 2, 7) === '[CDATA[') {
            // CDATA section
            const endCDATA = xmlStr.indexOf(']]>', pos);
            if (endCDATA === -1) throw new Error('Invalid XML: Unclosed CDATA section');
            const text = xmlStr.slice(pos + 9, endCDATA);
            if (text) {
              current.children.push({
                nodeType: 'text',
                textContent: text
              });
            }
            pos = endCDATA + 3;
            continue;
          }
        }
        
        if (xmlStr[pos + 1] === '/') {
          // Closing tag
          const endTag = xmlStr.indexOf('>', pos);
          if (endTag === -1) throw new Error('Invalid XML: Unclosed tag');
          const tagName = xmlStr.slice(pos + 2, endTag).trim();
          if (!stack.length || stack[stack.length - 1].tagName !== tagName) {
            throw new Error(`Invalid XML: Mismatched closing tag ${tagName}`);
          }
          stack.pop();
          current = stack[stack.length - 1];
          pos = endTag + 1;
        } else {
          // Opening tag or self-closing tag
          const endTag = xmlStr.indexOf('>', pos);
          if (endTag === -1) throw new Error('Invalid XML: Unclosed tag');
          
          const tagContent = xmlStr.slice(pos + 1, endTag);
          const isSelfClosing = tagContent.endsWith('/') || tagContent.endsWith('?');
          const actualTag = isSelfClosing ? tagContent.slice(0, -1) : tagContent;
          
          // Parse tag name and attributes
          const spaceIndex = actualTag.search(/\s/);
          const tagName = spaceIndex === -1 ? actualTag : actualTag.slice(0, spaceIndex);
          const attributesStr = spaceIndex === -1 ? '' : actualTag.slice(spaceIndex + 1);
          const attributes = parseAttributes(attributesStr);
          
          const node = {
            nodeType: 'element',
            tagName,
            attributes,
            children: [],
            parentNode: current
          };
          
          current.children.push(node);
          if (!isSelfClosing) {
            stack.push(node);
            current = node;
          }
          
          pos = endTag + 1;
        }
      } else {
        // Text content
        const nextTag = xmlStr.indexOf('<', pos);
        if (nextTag === -1) {
          // Handle remaining text at end of document
          const text = xmlStr.slice(pos).trim();
          if (text) {
            current.children.push({
              nodeType: 'text',
              textContent: text
            });
          }
          break;
        }
        
        const text = xmlStr.slice(pos, nextTag).trim();
        if (text) {
          current.children.push({
            nodeType: 'text',
            textContent: text
          });
        }
        pos = nextTag;
      }
    }
    
    if (stack.length > 1) {
      throw new Error(`Invalid XML: Unclosed tag ${stack[stack.length - 1].tagName}`);
    }
    
    return result;
  },
  
  // Helper functions for XML parsing and traversal
  getElementsByTagName(node, tagName) {
    const results = [];
    
    function traverse(node) {
      if (node.nodeType === 'element' && node.tagName === tagName) {
        results.push(node);
      }
      if (node.children) {
        for (const child of node.children) {
          traverse(child);
        }
      }
    }
    
    traverse(node);
    return results;
  },
  
  getElementsByAttribute(node, attrName, attrValue) {
    const results = [];
    
    function traverse(node) {
      if (node.nodeType === 'element' && 
          node.attributes?.[attrName] === attrValue) {
        results.push(node);
      }
      if (node.children) {
        for (const child of node.children) {
          traverse(child);
        }
      }
    }
    
    traverse(node);
    return results;
  },
  
  getFirstChild(node) {
    return node.children?.[0] || null;
  },
  
  getChildNodes(node) {
    return node.children || [];
  },
  
  getParentNode(node) {
    return node.parentNode || null;
  },
  
  getTextContent(node) {
    if (node.nodeType === 'text') return node.textContent;
    if (!node.children) return '';
    
    return node.children
      .map(child => this.getTextContent(child))
      .join('');
  },
  
  getAttribute(node, name) {
    return node.attributes?.[name] || null;
  },
  
  hasAttribute(node, name) {
    return name in (node.attributes || {});
  },
  
  getAttributes(node) {
    return { ...(node.attributes || {}) };
  },

  getSharedStrings(xmlString) {
    const doc = this.parseXMLString(xmlString);
    const strings = [];
    const siNodes = this.getElementsByTagName(doc, 'si');
    
    for (const siNode of siNodes) {
      const tNodes = this.getElementsByTagName(siNode, 't');
      strings.push(tNodes[0] ? this.getTextContent(tNodes[0]) : '');
    }
    
    return strings;
  },

  getCellValue(cell, sharedStrings) {
    const vNodes = this.getElementsByTagName(cell, 'v');
    const value = vNodes[0] ? this.getTextContent(vNodes[0]) : '';
    const type = this.getAttribute(cell, 't');
    
    if (!value) return '';
    
    switch (type) {
      case 's': // Shared string
        return sharedStrings[parseInt(value)] || '';
      case 'b': // Boolean
        return value === '1';
      case 'n': // Number
        return parseFloat(value);
      default: // String or other
        return value;
    }
  },

  getSheetData(sheetXML, sharedStrings) {
    const doc = this.parseXMLString(sheetXML);
    const rows = this.getElementsByTagName(doc, 'row');
    const data = [];
    let maxCol = 0;
    
    for (const row of rows) {
      const rowData = {};
      const cells = this.getElementsByTagName(row, 'c');
      
      for (const cell of cells) {
        const ref = this.getAttribute(cell, 'r');
        const colLetter = ref.replace(/[0-9]/g, '');
        const colIndex = this.letterToColumn(colLetter);
        maxCol = Math.max(maxCol, colIndex);
        
        rowData[colLetter] = this.getCellValue(cell, sharedStrings);
      }
      
      // Convert to array format matching CSV parser
      const rowArray = {};
      const headers = Object.keys(rowData).sort((a, b) => 
        this.utils.letterToColumn(a) - this.utils.letterToColumn(b)
      );
      
      headers.forEach(header => {
        rowArray[header] = rowData[header];
      });
      
      data.push(rowArray);
    }
    
    return { data, maxCol };
  },

  // Parse XLSX data
  parseXLSX(buffer) {
    try {
      const files = this.unzip(buffer);
      
      if (!files['xl/workbook.xml']) {
        throw new Error('Invalid XLSX: Missing workbook.xml');
      }
      
      // Parse shared strings if available
      const sharedStrings = files['xl/sharedStrings.xml'] 
        ? this.getSharedStrings(files['xl/sharedStrings.xml'])
        : [];
      
      // Parse first sheet
      const { data, maxCol } = this.getSheetData(
        files['xl/worksheets/sheet1.xml'],
        sharedStrings
      );
      
      // Convert column indices to letters for headers
      const headers = Array.from({ length: maxCol + 1 }, (_, i) => 
        this.columnToLetter(i)
      );
      
      // Format data to match CSV parser output
      const formattedData = data.map(row => {
        const newRow = {};
        headers.forEach(header => {
          newRow[header] = row[header] || '';
        });
        return newRow;
      });
      
      return {
        SheetNames: ['Sheet1'],
        Sheets: {
          'Sheet1': {
            data: formattedData,
            range: { 
              s: { r: 0, c: 0 }, 
              e: { r: formattedData.length, c: headers.length } 
            }
          }
        }
      };
    } catch (e) {
      throw new Error(`XLSX parsing failed: ${e.message}`);
    }
  },

  // Parse XLS data (basic implementation)
  parseXLS(buffer) {
    // For now, return error as XLS binary parsing is complex
    // This should be implemented based on specific needs
    throw new Error('XLS parsing not implemented');
  },

  // Utility functions
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
};

// Export the XLSX object for CommonJS environments
module.exports = { XLSX };
