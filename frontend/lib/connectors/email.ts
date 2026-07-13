import tls from 'tls';
import type { Socket } from 'net';
import crypto from 'crypto';
import { pool } from '@/lib/db';
import { decryptCredential, encryptCredential } from '@/lib/secure-credentials';
import { sendSmtpMessage } from '@/lib/connectors/smtp-transport';

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

export interface EmailTransportDraft {
    id:string;request_id:string|null;recipient:string;subject:string;status:'draft'|'reviewed'|'sent'|'failed';
    reviewed_by:string|null;reviewed_at:string|null;transport_message_id:string|null;created_at:string;sent_at:string|null;
}

function publicDraft(row:Record<string,unknown>):EmailTransportDraft{return {
    id:String(row.id),request_id:row.request_id?String(row.request_id):null,recipient:String(row.recipient),subject:String(row.subject),
    status:row.status as EmailTransportDraft['status'],reviewed_by:row.reviewed_by?String(row.reviewed_by):null,
    reviewed_at:row.reviewed_at?String(row.reviewed_at):null,transport_message_id:row.transport_message_id?String(row.transport_message_id):null,
    created_at:String(row.created_at),sent_at:row.sent_at?String(row.sent_at):null,
};}

export async function createBuiltInEmailDraft(input:{requestId?:string;to:string;subject:string;body:string}):Promise<EmailTransportDraft>{
    if(!input.to.trim()||!input.subject.trim()||!input.body)throw new Error('Recipient, subject and body are required');
    const result=await pool.query(`INSERT INTO email_transport_drafts(request_id,recipient,subject,body_ciphertext)
        VALUES($1,$2,$3,$4) RETURNING id,request_id,recipient,subject,status,reviewed_by,reviewed_at,transport_message_id,created_at,sent_at`,
    [input.requestId||null,cleanHeader(input.to),cleanHeader(input.subject),encryptCredential(input.body)]);
    return publicDraft(result.rows[0]);
}

export async function reviewBuiltInEmailDraft(draftId:string,reviewedBy:string):Promise<EmailTransportDraft>{
    if(!reviewedBy.trim())throw new Error('A reviewer identity is required');
    const result=await pool.query(`UPDATE email_transport_drafts SET status='reviewed',reviewed_by=$2,reviewed_at=NOW(),error=NULL
        WHERE id=$1 AND status='draft' RETURNING id,request_id,recipient,subject,status,reviewed_by,reviewed_at,transport_message_id,created_at,sent_at`,[draftId,reviewedBy.trim()]);
    if(!result.rows[0])throw new Error('Only a draft can be reviewed');
    return publicDraft(result.rows[0]);
}

export async function sendReviewedBuiltInEmail(draftId:string):Promise<{messageId:string;transport:'smtp';draft:EmailTransportDraft}>{
    const draftResult=await pool.query(`SELECT id,request_id,recipient,subject,body_ciphertext,status FROM email_transport_drafts WHERE id=$1`,[draftId]);
    const draft=draftResult.rows[0];
    if(!draft||draft.status!=='reviewed')throw new Error('Email must be explicitly reviewed before sending');
    const settings=await internalConnector();
    if(settings.paused) throw new Error('Email connector is paused');
    const messageId=`<${crypto.randomUUID()}@${settings.email.split('@')[1]||'gdpr-agent.local'}>`;
    try{
        await smtpSend(settings,{to:draft.recipient,subject:draft.subject,body:decryptCredential(draft.body_ciphertext),messageId});
        const client=await pool.connect();try{await client.query('BEGIN');
            await client.query(`INSERT INTO outbound_messages(request_id,transport,transport_message_id,recipient,subject,status,metadata,sent_at)
                VALUES($1,'smtp',$2,$3,$4,'sent',$5::jsonb,NOW())`,[draft.request_id,messageId,draft.recipient,draft.subject,JSON.stringify({smtp_host:settings.smtp_host,draft_id:draft.id})]);
            const sent=await client.query(`UPDATE email_transport_drafts SET status='sent',transport_message_id=$2,sent_at=NOW(),error=NULL
                WHERE id=$1 AND status='reviewed' RETURNING id,request_id,recipient,subject,status,reviewed_by,reviewed_at,transport_message_id,created_at,sent_at`,[draft.id,messageId]);
            if(!sent.rows[0])throw new Error('Email draft changed before send completion');
            await client.query('COMMIT');return{messageId,transport:'smtp',draft:publicDraft(sent.rows[0])};
        }catch(error){await client.query('ROLLBACK');throw error;}finally{client.release();}
    }catch(error){
        await pool.query(`UPDATE email_transport_drafts SET status='failed',error=$2::jsonb WHERE id=$1 AND status='reviewed'`,[draft.id,JSON.stringify({message:error instanceof Error?error.message:String(error)})]);
        throw error;
    }
}

export async function sendBuiltInEmail(input:{requestId?:string;to:string;subject:string;body:string}):Promise<{messageId:string;transport:'smtp'}>{
    // Request submission is an explicit user send action; preserve a durable
    // draft/review audit rather than bypassing the transport state machine.
    const draft=await createBuiltInEmailDraft(input);
    await reviewBuiltInEmailDraft(draft.id,'request-submit');
    const result=await sendReviewedBuiltInEmail(draft.id);
    return{messageId:result.messageId,transport:result.transport};
}

export async function monitorInboxBuiltIn():Promise<{checked:number;unseen:number;matched:number;status:string}>{
    // The pre-Task-5 monitor acknowledged UIDs before durable provenance and
    // wrote protocol output straight into compatibility tables.  Fail closed
    // until inbox monitoring is backed by the canonical SourceConnector
    // queue/cursor and SourceArtifact/EvidenceLocator/ActivityEvent bridge.
    throw new Error('Inbox monitoring requires the canonical email source connector; the legacy IMAP monitor is disabled');
}

function smtpFromImap(host:string):string{return host.replace(/^imap\./i,'smtp.');}
function cleanHeader(value:string):string{return value.replace(/[\r\n]+/g,' ');}

async function smtpSend(settings:EmailConnectorSettings&{password:string},message:{to:string;subject:string;body:string;messageId:string}):Promise<void>{
    await sendSmtpMessage(
        {host:settings.smtp_host,port:settings.smtp_port,secure:settings.smtp_secure,username:settings.email,password:settings.password},
        {from:settings.email,...message},
    );
}

async function imapCommand(settings:EmailConnectorSettings&{password:string},commands:string[]):Promise<string>{
    const socket=tls.connect({host:settings.imap_host,port:settings.imap_port,servername:settings.imap_host,rejectUnauthorized:true});
    const escapedUser=settings.email.replace(/(["\\])/g,'\\$1'); const escapedPassword=settings.password.replace(/(["\\])/g,'\\$1');
    return protocol(socket,[{expect:/^\* OK/im,send:`a0 LOGIN "${escapedUser}" "${escapedPassword}"\r\n`},{expect:/^a0 OK/im,send:`${commands.join('\r\n')}\r\n`},{expect:new RegExp(`^${commands.at(-1)?.split(' ')[0]} OK`,'im'),send:null}]).finally(()=>socket.destroy());
}

function protocol(socket:Socket|tls.TLSSocket,steps:Array<{expect:RegExp;send:string|null}>):Promise<string>{return new Promise((resolve,reject)=>{
    let all='';let pending='';let index=0;const timeout=setTimeout(()=>{socket.destroy();reject(new Error('Email connector timed out'));},20_000);
    socket.setEncoding('utf8');socket.on('error',(error:Error)=>{clearTimeout(timeout);reject(error);});socket.on('data',(chunk:string)=>{all+=chunk;
        pending+=chunk;while(index<steps.length&&steps[index].expect.test(pending)){const step=steps[index++];pending='';if(step.send)socket.write(step.send);if(index===steps.length){clearTimeout(timeout);resolve(all);}}
    });
  });}
