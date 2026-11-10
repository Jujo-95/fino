// Deployment options. This controls presentation; server authentication must still enforce tenant access.
export const multiClientEnabled=import.meta.env.VITE_ENABLE_MULTI_CLIENT==='true';
export const deploymentClientId=String(import.meta.env.VITE_CLIENT_ID||'');
