import type {DeletionPlan,RetentionDecision} from './types';

export interface RetentionPolicyView{id:string;policy_version:number;name:string;action:string;minimum_age_seconds:number;grace_period_seconds:number;enabled:boolean;connector_keys:string[];data_classes:string[]}
export interface DeletionPlanView extends Omit<DeletionPlan,'items'>{status:string;items:DeletionPlan['items']}
export interface RetentionOverview{policies:RetentionPolicyView[];decisions:RetentionDecision[];plans:DeletionPlanView[]}
async function request<T>(path:string,body?:unknown):Promise<T>{const response=await fetch(`/api/retention${path}`,{method:body===undefined?'GET':'POST',headers:{'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});const payload=await response.json();if(!response.ok)throw new Error(payload.detail||`Retention request failed (${response.status})`);return payload as T}
export const fetchRetention=()=>request<RetentionOverview>('');
export const createPolicy=(body:Record<string,unknown>)=>request('/policies',body);
export const createDeletionPlan=(body:{policy_id:string;policy_version:number;analysis_run_id:string;decision_ids:string[]})=>request('/plans',body);
export const reviewDecision=(id:string,approved:boolean)=>request(`/decisions/${id}/review`,{actor:'settings-user',approved,reasons:['reviewed in retention settings']});
export const reviewPlan=(id:string)=>request(`/plans/${id}/review`,{actor:'settings-user',confirmation:'REVIEW PLAN'});
export const approvePlan=(id:string,confirmation:string)=>request(`/plans/${id}/approve`,{actor:'settings-user',confirmation});
export const stageItem=(id:string,target:string,confirmation:string)=>request(`/items/${id}/stage`,{actor:'settings-user',target,confirmation});
export const executeItem=(id:string,confirmation:string)=>request(`/items/${id}/execute`,{actor:'settings-user',confirmation});
export const createControllerCandidate=(id:string,controller_key:string)=>request<{id:string}>(`/items/${id}/controller-erasure`,{controller_key});
export const createControllerDraft=(id:string,company_name:string)=>request(`/controller-erasure/${id}/draft`,{actor:'settings-user',confirmation:'CREATE DRAFT ERASURE REQUEST',company_name});
