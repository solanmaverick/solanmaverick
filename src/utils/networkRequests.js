/**
 * Basic GET request function
 * @param {string} url - The URL to send the GET request to
 * @param {Object} options - Optional request configuration
 * @returns {Promise<any>} - Promise that resolves with the response data
 */
export const get = async (url, options = {}) => {
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('GET request failed:', error);
    throw error;
  }
};

/**
 * Basic POST request function
 * @param {string} url - The URL to send the POST request to
 * @param {Object} data - The data to send in the request body
 * @param {Object} options - Optional request configuration
 * @returns {Promise<any>} - Promise that resolves with the response data
 */
export const post = async (url, data, options = {}) => {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      body: JSON.stringify(data),
      ...options,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('POST request failed:', error);
    throw error;
  }
};
