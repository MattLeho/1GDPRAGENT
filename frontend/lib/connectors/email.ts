import net from 'net';
import tls from 'tls';
import { pool } from '@/lib/db';
import { decryptCredential, encryptCredential } from '@/lib/secure-credentials';

export interface EmailConnectorSettings {
    id:string; email:string; imap_host:string; imap_port:number; smtp_host:string;
    smtp_port:number; smtp_secure:boolean; connection_verified:boolean; credential_status:'active'|'missing'|'needs_reentry';
    paused:boolean; last_sync_at:string|null; next_sync_at:string|null; updated_at:string;
}

export async function saveEmailConnector(input:{email:string;password:string;imap_host:string;imap_port:number;smtp_host?:string;smtp_port?:number;smtp_secure?:boolean}):Promise<EmailConnectorSettings>{
    if(!input.password) throw new Error('Enter the connector password to save or rotate credentials');
    const accountKey=input.email.trim().toLowerCase(); const ciphertext=encryptCredential(input.password);
    const client=await pool.connect();
    try{
        await client.query('BEGIN');
        const credential=await client.query(`INSERT INTO connector_credentials(connector_key,account_key,secret_ciphertext,encryption_version,credential_version,needs_reentry,rotated_at,updated_at)
            VALUES('email',$1,$2,'aes-256-gcm-v1',1,false,NOW(),NOW()) ON CONFLICT(connector_key,account_key) DO UPDATE SET
            secret_ciphertext=EXCLUDED.secret_ciphertext,encryption_version=EXCLUDED.encryption_version,
            credential_version=connector_credentials.credential_version+1,needs_reentry=false,rotated_at=NOW(),updated_at=NOW() RETURNING id`,[accountKey,ciphertext]);
        const existing=await client.query('SELECT id FROM email_settings ORDER BY created_at LIMIT 1');
        const values=[accountKey,input.imap_host,Number(input.imap_port),input.smtp_host||smtpFromImap(input.imap_host),Number(input.smtp_port||465),input.smtp_secure!==false,credential.rows[0].id];
        if(existing.rows[0]) await client.query(`UPDATE email_settings SET email=$1,imap_host=$2,imap_port=$3,smtp_host=$4,smtp_port=$5,smtp_secure=$6,
            credential_id=$7,credential_status='active',connection_verified=false,password_encrypted='',updated_at=NOW() WHERE id=$8`,[...values,existing.rows[0].id]);
        else await client.query(`INSERT INTO email_settings(email,password_encrypted,imap_host,imap_port,smtp_host,smtp_port,smtp_secure,credential_id,credential_status,connection_verified)
            VALUES($1,'',$2,$3,$4,$5,$6,$7,'active',false)`,values);
        await client.query('COMMIT');
    }catch(error){await client.query('ROLLBACK');throw error;}finally{client.release();}
    return (await getEmailConnector())!;
}

export async function getEmailConnector():Promise<EmailConnectorSettings|null>{
    const result=await pool.query(`SELECT id,email,imap_host,imap_port,COALESCE(smtp_host,'') smtp_host,COALESCE(smtp_port,465) smtp_port,
        COALESCE(smtp_secure,true) smtp_secure,connection_verified,credential_status,paused,last_sync_at,next_sync_at,updated_at FROM email_settings ORDER BY created_at LIMIT 1`);
    return result.rows[0]||null;
}

async function internalConnector():Promise<EmailConnectorSettings&{password:string}>{
    const result=await pool.query(`SELECT es.id,es.email,es.imap_host,es.imap_port,COALESCE(es.smtp_host,'') smtp_host,COALESCE(es.smtp_port,465) smtp_port,
        COALESCE(es.smtp_secure,true) smtp_secure,es.connection_verified,es.credential_status,es.paused,es.last_sync_at,es.next_sync_at,es.updated_at,cc.secret_ciphertext
        FROM email_settings es LEFT JOIN connector_credentials cc ON cc.id=es.credential_id ORDER BY es.created_at LIMIT 1`);
    const row=result.rows[0];
    if(!row||row.credential_status!=='active'||!row.secret_ciphertext) throw new Error('Email credential is missing or requires re-entry');
    return {...row,password:decryptCredential(row.secret_ciphertext)};
}

export async function deleteEmailCredential():Promise<void>{
    const client=await pool.connect(); try{await client.query('BEGIN');
        await client.query("DELETE FROM connector_credentials WHERE id IN (SELECT credential_id FROM email_settings)");
        await client.query("UPDATE email_settings SET credential_id=NULL,credential_status='missing',connection_verified=false,password_encrypted='',updated_at=NOW()");
        await client.query('COMMIT');
    }catch(error){await client.query('ROLLBACK');throw error;}finally{client.release();}
}

export async function testEmailConnector():Promise<{success:boolean;message:string}>{
    const settings=await internalConnector();
    try{await imapCommand(settings,['a1 CAPABILITY','a2 LOGOUT']);await pool.query('UPDATE email_settings SET connection_verified=true,updated_at=NOW() WHERE id=$1',[settings.id]);return{success:true,message:'Built-in IMAP connector verified'};}
    catch(error){await pool.query('UPDATE email_settings SET connection_verified=false,updated_at=NOW() WHERE id=$1',[settings.id]);return{success:false,message:error instanceof Error?error.message:String(error)};}
}

export async function sendBuiltInEmail(input:{requestId?:string;to:string;subject:string;body:string}):Promise<{messageId:string;transport:'smtp'}>{
    const settings=await internalConnector();
    if(settings.paused) throw new Error('Email connector is paused');
    const messageId=`<${cryptoRandom()}@${settings.email.split('@')[1]||'gdpr-agent.local'}>`;
    await smtpSend(settings,{...input,messageId});
    await pool.query(`INSERT INTO outbound_messages(request_id,transport,transport_message_id,recipient,subject,status,metadata,sent_at)
        VALUES($1,'smtp',$2,$3,$4,'sent',$5::jsonb,NOW())`,[input.requestId||null,messageId,input.to,input.subject,JSON.stringify({smtp_host:settings.smtp_host})]);
    return{messageId,transport:'smtp'};
}

export async function monitorInboxBuiltIn():Promise<{checked:number;unseen:number;matched:number;status:string}>{
    // The pre-Task-5 monitor acknowledged UIDs before durable provenance and
    // wrote protocol output straight into compatibility tables.  Fail closed
    // until inbox monitoring is backed by the canonical SourceConnector
    // queue/cursor and SourceArtifact/EvidenceLocator/ActivityEvent bridge.
    throw new Error('Inbox monitoring requires the canonical email source connector; the legacy IMAP monitor is disabled');
}

function smtpFromImap(host:string):string{return host.replace(/^imap\./i,'smtp.');}
function cryptoRandom():string{return `${Date.now().toString(36)}.${Math.random().toString(36).slice(2)}`;}
function cleanHeader(value:string):string{return value.replace(/[\r\n]+/g,' ');}

async function smtpSend(settings:EmailConnectorSettings&{password:string},message:{to:string;subject:string;body:string;messageId:string}):Promise<void>{
    const socket=settings.smtp_secure?tls.connect({host:settings.smtp_host,port:settings.smtp_port,servername:settings.smtp_host,rejectUnauthorized:true}):net.connect({host:settings.smtp_host,port:settings.smtp_port});
    await protocol(socket,[
        {expect:/^220/m,send:`EHLO gdpr-agent.local\r\n`},{expect:/^250 /m,send:`AUTH LOGIN\r\n`},
        {expect:/^334/m,send:`${Buffer.from(settings.email).toString('base64')}\r\n`},{expect:/^334/m,send:`${Buffer.from(settings.password).toString('base64')}\r\n`},
        {expect:/^235/m,send:`MAIL FROM:<${cleanHeader(settings.email)}>\r\n`},{expect:/^250/m,send:`RCPT TO:<${cleanHeader(message.to)}>\r\n`},
        {expect:/^250/m,send:'DATA\r\n'},{expect:/^354/m,send:`From: ${cleanHeader(settings.email)}\r\nTo: ${cleanHeader(message.to)}\r\nSubject: ${cleanHeader(message.subject)}\r\nMessage-ID: ${message.messageId}\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n${message.body.replace(/^\./gm,'..')}\r\n.\r\n`},
        {expect:/^250/m,send:'QUIT\r\n'},{expect:/^221/m,send:null},
    ]); socket.destroy();
}

async function imapCommand(settings:EmailConnectorSettings&{password:string},commands:string[]):Promise<string>{
    const socket=tls.connect({host:settings.imap_host,port:settings.imap_port,servername:settings.imap_host,rejectUnauthorized:true});
    const escapedUser=settings.email.replace(/(["\\])/g,'\\$1'); const escapedPassword=settings.password.replace(/(["\\])/g,'\\$1');
    return protocol(socket,[{expect:/^\* OK/im,send:`a0 LOGIN "${escapedUser}" "${escapedPassword}"\r\n`},{expect:/^a0 OK/im,send:`${commands.join('\r\n')}\r\n`},{expect:new RegExp(`^${commands.at(-1)?.split(' ')[0]} OK`,'im'),send:null}]).finally(()=>socket.destroy());
}

function protocol(socket:net.Socket|tls.TLSSocket,steps:Array<{expect:RegExp;send:string|null}>):Promise<string>{return new Promise((resolve,reject)=>{
    let all='';let pending='';let index=0;const timeout=setTimeout(()=>{socket.destroy();reject(new Error('Email connector timed out'));},20_000);
    socket.setEncoding('utf8');socket.on('error',error=>{clearTimeout(timeout);reject(error);});socket.on('data',chunk=>{all+=chunk;
        pending+=chunk;while(index<steps.length&&steps[index].expect.test(pending)){const step=steps[index++];pending='';if(step.send)socket.write(step.send);if(index===steps.length){clearTimeout(timeout);resolve(all);}}
    });
  });}
