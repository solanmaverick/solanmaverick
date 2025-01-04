// Excel parsing utilities
import XLSX from 'xlsx';

// Supported file extensions
const SUPPORTED_EXTENSIONS = ['.xlsx', '.xls', '.csv'];

export const isFileSupported = (filename) => {
  const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
  return SUPPORTED_EXTENSIONS.includes(ext);
};

export const parseExcelFile = async (fileData) => {
  try {
    // Define fixed attributes and display settings
    const FIXED_ATTRIBUTES = ['学校名称', '专业名称', '学校代码', '专业代码', '位次差'];
    const NO_LABEL_ATTRIBUTES = ['学校代码', '专业代码'];
    
    // Convert ArrayBuffer to Uint8Array if needed
    const data = fileData instanceof ArrayBuffer ? new Uint8Array(fileData) : fileData;
    
    // Enable full style parsing and debugging
    console.log('Parsing Excel file with enhanced style options...');
    const workbook = XLSX.read(data, { 
      type: 'array',
      cellStyles: true,
      cellHTML: true,
      cellDates: true,
      cellFormula: true,
      cellNF: true,
      cellText: true,
      sheetStubs: true,
      bookDeps: true,
      bookFiles: true,
      bookProps: true,
      bookSheets: true,
      bookVBA: true,
      numbers: true
    });
    
    const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
    
    // Get headers from first row
    const excelHeaders = [];
    const range = XLSX.utils.decode_range(firstSheet['!ref']);
    
    for (let C = range.s.c; C <= range.e.c; ++C) {
      const cell = firstSheet[XLSX.utils.encode_cell({ r: 0, c: C })];
      excelHeaders.push(cell ? cell.v : '');
    }

    // Identify dynamic attributes (those not in fixed list)
    const dynamicAttributes = excelHeaders.filter(header => !FIXED_ATTRIBUTES.includes(header));

    // Create complete headers list (fixed first, then dynamic)
    const headers = [...FIXED_ATTRIBUTES, ...dynamicAttributes];

    // Parse data with formatting
    const rows = [];
    for (let R = range.s.r + 1; R <= range.e.r; ++R) {
      const row = {};
      let hasData = false;
      
      // Process fixed attributes first (using their positions in Excel if present)
      FIXED_ATTRIBUTES.forEach(attr => {
        const excelIndex = excelHeaders.indexOf(attr);
        const cell = excelIndex !== -1 ? firstSheet[XLSX.utils.encode_cell({ r: R, c: excelIndex })] : null;
        
        row[attr] = {
          value: cell ? cell.v : '',
          style: cell ? (() => {
            // Debug logging for style information
            console.log(`Style debug for fixed attribute ${attr}:`, {
              fill: cell.s?.fill,
              font: cell.s?.font,
              theme: workbook.Themes?.[0]
            });
            
            // Enhanced style extraction with theme support
            const style = {
              backgroundColor: cell.s?.fill?.fgColor?.rgb || 
                             (cell.s?.fill?.fgColor?.theme !== undefined ? 
                               (workbook.Themes?.[0]?.themeElements?.clrScheme?.[`accent${cell.s.fill.fgColor.theme + 1}`]?.rgb || 'FFFFFF') :
                               null),
              color: cell.s?.font?.color?.rgb || 
                    (cell.s?.font?.color?.theme !== undefined ?
                      (workbook.Themes?.[0]?.themeElements?.clrScheme?.[`accent${cell.s.font.color.theme + 1}`]?.rgb || '000000') :
                      null),
              bold: cell.s?.font?.bold || false,
              italic: cell.s?.font?.italic || false,
              fontName: cell.s?.font?.name || null
            };
            console.log(`Extracted style for fixed attribute ${attr}:`, style);
            return style;
          })() : {},
          displayLabel: !NO_LABEL_ATTRIBUTES.includes(attr) // Control label display
        };
        
        if (cell) hasData = true;
      });
      
      // Process dynamic attributes
      dynamicAttributes.forEach(attr => {
        const excelIndex = excelHeaders.indexOf(attr);
        const cell = firstSheet[XLSX.utils.encode_cell({ r: R, c: excelIndex })];
        
        if (cell) {
          hasData = true;
          row[attr] = {
            value: cell.v,
            style: (() => {
              // Debug logging for style information
              console.log(`Style debug for dynamic attribute ${attr}:`, {
                fill: cell.s?.fill,
                font: cell.s?.font,
                theme: workbook.Themes?.[0]
              });
              
              // Enhanced style extraction with theme support
              const style = {
                backgroundColor: cell.s?.fill?.fgColor?.rgb || 
                               (cell.s?.fill?.fgColor?.theme !== undefined ? 
                                 (workbook.Themes?.[0]?.themeElements?.clrScheme?.[`accent${cell.s.fill.fgColor.theme + 1}`]?.rgb || 'FFFFFF') :
                                 null),
                color: cell.s?.font?.color?.rgb || 
                      (cell.s?.font?.color?.theme !== undefined ?
                        (workbook.Themes?.[0]?.themeElements?.clrScheme?.[`accent${cell.s.font.color.theme + 1}`]?.rgb || '000000') :
                        null),
                bold: cell.s?.font?.bold || false,
                italic: cell.s?.font?.italic || false,
                fontName: cell.s?.font?.name || null
              };
              console.log(`Extracted style for dynamic attribute ${attr}:`, style);
              return style;
            })(),
            displayLabel: true // Always show labels for dynamic attributes
          };
        }
      });

      // Only add rows that have data
      if (hasData) {
        rows.push(row);
      }
    }

    return { 
      headers,
      fixedAttributes: FIXED_ATTRIBUTES,
      dynamicAttributes,
      noLabelAttributes: NO_LABEL_ATTRIBUTES,
      rows,
      totalRows: rows.length
    };
  } catch (error) {
    console.error('Error parsing Excel file:', error);
    if (error.message.includes('文件格式错误')) {
      throw error;
    }
    throw new Error('Excel文件解析失败，请检查文件格式是否正确');
  }
};

export const preserveFormatting = (cell) => {
  return {
    value: cell.value,
    style: cell.style || {}
  };
};

export const validateFixedAttributes = (headers) => {
  // No need to modify headers anymore - we handle missing attributes in parseExcelFile
  // Just validate that the file structure is valid
  if (!Array.isArray(headers) || headers.length === 0) {
    throw new Error('Excel文件必须包含标题行');
  }
  return true;
};