import { NextRequest, NextResponse } from 'next/server';
import { pool } from '@/lib/db';
import { verifySessionToken } from '@/lib/auth-session';

export async function requireApiSession(request:NextRequest):Promise<{profileId:string}|NextResponse>{
  const token=request.cookies.get('gdpr-session')?.value;
  if(!token) return NextResponse.json({detail:'Authentication required'},{status:401});
  const identity=verifySessionToken(token);
  if(!identity) return NextResponse.json({detail:'Session is invalid or expired'},{status:401});
  const result=await pool.query('SELECT id FROM user_profiles WHERE id=$1 AND default_profile_id=$2',[identity.userId,identity.profileId]);
  if(result.rowCount!==1) return NextResponse.json({detail:'Session profile no longer exists'},{status:401});
  return {profileId:identity.profileId};
}

export function intelligenceAuthorityHeaders(profileId:string,contentType='application/json'):{[key:string]:string}{
  const key=process.env.INTERNAL_API_KEY||process.env.CREDENTIAL_KEY||process.env.CREDENTIALS_ENCRYPTION_KEY;
  if(!key) throw new Error('INTERNAL_API_KEY or CREDENTIAL_KEY is required');
  return {'content-type':contentType,'x-gdpr-internal-key':key,'x-gdpr-profile-id':profileId};
}
