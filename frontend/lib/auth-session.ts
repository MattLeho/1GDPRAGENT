import { createHmac, timingSafeEqual } from 'crypto';

export interface SessionIdentity { userId: string; profileId: string; issuedAt: number }

function secret(): string {
  const value=process.env.SESSION_SIGNING_KEY||process.env.CREDENTIAL_KEY||process.env.CREDENTIALS_ENCRYPTION_KEY;
  if(!value) throw new Error('SESSION_SIGNING_KEY or CREDENTIAL_KEY is required');
  return value;
}

function signature(payload:string):string {
  return createHmac('sha256',secret()).update(payload).digest('base64url');
}

export function createSessionToken(userId:string,profileId:string,issuedAt=Date.now()):string {
  const payload=Buffer.from(JSON.stringify({userId,profileId,issuedAt}),'utf8').toString('base64url');
  return `${payload}.${signature(payload)}`;
}

export function verifySessionToken(token:string,maxAgeMs=7*24*60*60*1000):SessionIdentity|null {
  const [payload,supplied,...extra]=token.split('.');
  if(!payload||!supplied||extra.length) return null;
  const expected=signature(payload);
  const left=Buffer.from(supplied);const right=Buffer.from(expected);
  if(left.length!==right.length||!timingSafeEqual(left,right)) return null;
  try{
    const value=JSON.parse(Buffer.from(payload,'base64url').toString('utf8')) as SessionIdentity;
    if(typeof value.userId!=='string'||typeof value.profileId!=='string'||typeof value.issuedAt!=='number') return null;
    if(value.issuedAt>Date.now()+60_000||Date.now()-value.issuedAt>maxAgeMs) return null;
    return value;
  }catch{return null}
}
