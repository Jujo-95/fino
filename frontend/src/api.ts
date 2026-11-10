export class ApiError extends Error{constructor(public status:number,public detail:unknown){super(typeof detail==='string'?detail:JSON.stringify(detail))}}
export async function api<T>(path:string,init?:RequestInit):Promise<T>{
  const response=await fetch('/api/v1'+path,init);
  if(!response.ok){const data=await response.json().catch(()=>({detail:response.statusText}));throw new ApiError(response.status,data.detail);}
  return response.json() as Promise<T>;
}
export function download(name:string,text:string,type='text/markdown;charset=utf-8'){
  const url=URL.createObjectURL(new Blob([text],{type}));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url);
}
