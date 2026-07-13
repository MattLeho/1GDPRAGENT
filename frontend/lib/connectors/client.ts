import type {ConnectorInstance,SourceConnectorDefinition} from './types';

export interface ConnectorOverview{definitions:SourceConnectorDefinition[];instances:ConnectorInstance[]}
async function request<T>(path:string,init?:RequestInit):Promise<T>{
  const response=await fetch(`/api/connectors${path}`,{...init,headers:{'content-type':'application/json',...(init?.headers||{})},cache:'no-store'});
  const payload=await response.json();if(!response.ok)throw new Error(payload.detail||`Connector request failed (${response.status})`);return payload as T;
}
export const fetchConnectors=()=>request<ConnectorOverview>('');
export const createConnector=(body:Record<string,unknown>)=>request<ConnectorInstance>('',{method:'POST',body:JSON.stringify(body)});
export const updateConnectorStatus=(id:string,status:string)=>request<ConnectorInstance>(`/instances/${encodeURIComponent(id)}/status/${encodeURIComponent(status)}`,{method:'POST'});
export const syncConnector=(id:string,backfill=false)=>request<Record<string,unknown>>(`/instances/${encodeURIComponent(id)}/sync?backfill=${backfill}`,{method:'POST'});
export const updateConnectorPermissions=(id:string,permissions:string[])=>request<ConnectorInstance>(`/instances/${encodeURIComponent(id)}/permissions`,{method:'PUT',body:JSON.stringify({enabled_permissions:permissions,actor:'settings-user'})});
