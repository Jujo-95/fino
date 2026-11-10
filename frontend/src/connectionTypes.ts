export type ProviderId='nvidia'|'gemini'|'groq';
export type ConnectionEntry={id:string;name:string;category:'Facturación'|'Contexto'|'Herramientas'|'IA';status:string;scope:string;updated?:string;description:string;provider?:ProviderId};
export type ConnectionInventory={remote_source?:{kind:string;verified_at?:string|null}|null;client_id:string;imports:{name:string;rows:number;updated_at:string}[];documents:{name:string;updated_at:string}[];tools:{name:string}[];external_mcp_supported:boolean};
export type SourceStatus={configured:boolean;kind:string;bucket?:string;prefix?:string;synthetic?:boolean;last_sync?:{through:string;objects:number;ingested_rows:number}};
export type ProviderOptions={active:ProviderId|null;providers:{id:ProviderId;provider:string;configured:boolean;model:string}[]};
