import { NextResponse } from 'next/server'
import { pool } from '@/lib/db'
import { obfuscate, type APICredentials } from '@/lib/credentials'

const fields: Array<keyof APICredentials>=['hibpApiKey','hunterApiKey','shodanApiKey','whoisApiKey']

export async function GET() {
  try {
    const result=await pool.query("SELECT key,value IS NOT NULL AND value<>'' AS has_key FROM app_settings WHERE key=ANY($1::text[])",[fields.map(field=>`onsit.${field}`)])
    const present=new Set(result.rows.filter(row=>row.has_key).map(row=>String(row.key).replace('onsit.','')))
    return NextResponse.json({savedKeys:Object.fromEntries(fields.map(field=>[field,present.has(field)]))})
  } catch(error) {
    console.error('[API Credentials GET] Error:',error)
    return NextResponse.json({error:'Failed to fetch credentials'},{status:500})
  }
}

export async function POST(request: Request) {
  try {
    const body:APICredentials=await request.json()
    for(const field of fields) {
      const value=body[field]
      if(value) await pool.query("INSERT INTO app_settings(key,value,encrypted,updated_at) VALUES($1,$2,true,NOW()) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,encrypted=true,updated_at=NOW()",[`onsit.${field}`,obfuscate(value)])
    }
    return NextResponse.json({success:true,savedKeys:Object.fromEntries(fields.map(field=>[field,Boolean(body[field])]))})
  } catch(error) {
    console.error('[API Credentials POST] Error:',error)
    return NextResponse.json({error:'Failed to save credentials'},{status:500})
  }
}
