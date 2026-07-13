# Frontend Standalone Project

This folder contains the standalone frontend copy for the LOUD Platform.

## How to use

1. Start the backend server on `http://127.0.0.1:8000`.
2. Open `frontend/index.html` with a static file server such as Live Server.
3. The frontend will load assets from `frontend/css/` and `frontend/js/`, and send API requests to `http://127.0.0.1:8000/api/v1`.

## Notes

- The backend must allow CORS from the frontend origin when using a browser-based static server.
- Do not modify the UI or business logic in this frontend copy unless you are only fixing integration issues.
- For browser extension integrations, a sample activation helper is available at `frontend/extension_activation_example.js`.
