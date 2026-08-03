import type {ConnectorInstance,SourceConnectorDefinition} from './types';
import {protectedApi} from '@/lib/api-client';

export interface ConnectorOverview{definitions:SourceConnectorDefinition[];instances:ConnectorInstance[]}
export interface BrowserPairing{pairing_id:string;connector_instance_id:string;token:string;created_at:string}
async function request<T>(path:string,init?:RequestInit):Promise<T>{
  return protectedApi<T>(`/api/connectors${path}`,{...init,headers:{'content-type':'application/json',...(init?.headers||{})}});
}
export const fetchConnectors=()=>request<ConnectorOverview>('');
export const createConnector=(body:Record<string,unknown>)=>request<ConnectorInstance>('',{method:'POST',body:JSON.stringify(body)});
export const updateConnectorStatus=(id:string,status:string)=>request<ConnectorInstance>(`/instances/${encodeURIComponent(id)}/status/${encodeURIComponent(status)}`,{method:'POST'});
export const syncConnector=(id:string,backfill=false)=>request<Record<string,unknown>>(`/instances/${encodeURIComponent(id)}/sync?backfill=${backfill}`,{method:'POST'});
export const updateConnectorPermissions=(id:string,permissions:string[])=>request<ConnectorInstance>(`/instances/${encodeURIComponent(id)}/permissions`,{method:'PUT',body:JSON.stringify({enabled_permissions:permissions,actor:'settings-user'})});
export const createBrowserPairing=(connectorInstanceId:string,label:string)=>request<BrowserPairing>('/browser/pairings',{method:'POST',body:JSON.stringify({connector_instance_id:connectorInstanceId,label})});
export const revokeBrowserPairing=(pairingId:string)=>request<{revoked:boolean}>(`/browser/pairings/${encodeURIComponent(pairingId)}`,{method:'DELETE'});
