import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { pool } from '@/lib/db'
import { type APICredentials } from '@/lib/credentials'
import { encryptCredential } from '@/lib/secure-credentials'

const fields: Array<keyof APICredentials>=['hibpApiKey','hunterApiKey','shodanApiKey','whoisApiKey']

export async function GET(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
  try {
    const prefix=`profile.${authority.profileId}.onsit.`
    const result=await pool.query("SELECT key,value IS NOT NULL AND value<>'' AS has_key FROM app_settings WHERE key=ANY($1::text[])",[fields.map(field=>`${prefix}${field}`)])
    const present=new Set(result.rows.filter(row=>row.has_key).map(row=>String(row.key).replace(prefix,'')))
    return NextResponse.json({savedKeys:Object.fromEntries(fields.map(field=>[field,present.has(field)]))})
  } catch(error) {
    console.error('[API Credentials GET] Error:',error)
    return NextResponse.json({error:'Failed to fetch credentials'},{status:500})
  }
}

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
  try {
    const body:APICredentials=await request.json()
    const supplied=fields.flatMap(field=>{
      const value=body[field]?.trim()
      return value ? [{field,value}] : []
    })
    if(supplied.length===0) return NextResponse.json({error:'Enter at least one API key'},{status:400})

    const client=await pool.connect()
    try {
      await client.query('BEGIN')
      for(const {field,value} of supplied) {
        await client.query("INSERT INTO app_settings(key,value,encrypted,updated_at) VALUES($1,$2,true,NOW()) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,encrypted=true,updated_at=NOW()",[`profile.${authority.profileId}.onsit.${field}`,encryptCredential(value)])
      }
      await client.query('COMMIT')
    } catch(error) {
      await client.query('ROLLBACK')
      throw error
    } finally {
      client.release()
    }

    const prefix=`profile.${authority.profileId}.onsit.`
    const result=await pool.query("SELECT key,value IS NOT NULL AND value<>'' AS has_key FROM app_settings WHERE key=ANY($1::text[])",[fields.map(field=>`${prefix}${field}`)])
    const present=new Set(result.rows.filter(row=>row.has_key).map(row=>String(row.key).replace(prefix,'')))
    return NextResponse.json({success:true,savedKeys:Object.fromEntries(fields.map(field=>[field,present.has(field)]))})
  } catch(error) {
    console.error('[API Credentials POST] Error:',error)
    return NextResponse.json({error:'Failed to save credentials'},{status:500})
  }
}
