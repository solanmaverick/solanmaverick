# Network Request Utilities

Basic GET and POST request utilities for making HTTP requests.

## Usage

```javascript
import { get, post } from './networkRequests.js';

// GET request example
try {
  const data = await get('https://api.example.com/data');
  console.log(data);
} catch (error) {
  console.error('Error:', error);
}

// POST request example
try {
  const response = await post('https://api.example.com/create', {
    name: 'John Doe',
    email: 'john@example.com'
  });
  console.log(response);
} catch (error) {
  console.error('Error:', error);
}
```

## API

### get(url, options)
Makes a GET request to the specified URL.

- `url`: The URL to send the request to
- `options`: Optional request configuration (headers, etc.)

### post(url, data, options)
Makes a POST request to the specified URL with the provided data.

- `url`: The URL to send the request to
- `data`: The data to send in the request body
- `options`: Optional request configuration (headers, etc.)
