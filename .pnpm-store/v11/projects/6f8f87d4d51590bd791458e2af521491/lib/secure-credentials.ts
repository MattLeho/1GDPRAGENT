import crypto from 'crypto';

const PREFIX='aes-256-gcm-v1';
function key():Buffer {
    const value=process.env.CREDENTIALS_ENCRYPTION_KEY||process.env.ENCRYPTION_KEY;
    if(!value){
        if(process.env.NODE_ENV==='production') throw new Error('CREDENTIALS_ENCRYPTION_KEY must be set in production');
        return crypto.createHash('sha256').update('gdpr-agent-local-development-credential-key').digest();
    }
    return crypto.createHash('sha256').update(value).digest();
}
export function encryptCredential(plaintext:string):string {
    if(!plaintext) throw new Error('Credential cannot be empty');
    const iv=crypto.randomBytes(12); const cipher=crypto.createCipheriv('aes-256-gcm',key(),iv);
    const encrypted=Buffer.concat([cipher.update(plaintext,'utf8'),cipher.final()]); const tag=cipher.getAuthTag();
    return [PREFIX,iv.toString('base64url'),tag.toString('base64url'),encrypted.toString('base64url')].join(':');
}
export function decryptCredential(ciphertext:string):string {
    const [version,ivValue,tagValue,dataValue]=ciphertext.split(':');
    if(version!==PREFIX||!ivValue||!tagValue||!dataValue) throw new Error('Unsupported or legacy credential encoding');
    const decipher=crypto.createDecipheriv('aes-256-gcm',key(),Buffer.from(ivValue,'base64url'));
    decipher.setAuthTag(Buffer.from(tagValue,'base64url'));
    return Buffer.concat([decipher.update(Buffer.from(dataValue,'base64url')),decipher.final()]).toString('utf8');
}
export function isCanonicalCiphertext(value:string|null|undefined):boolean{return Boolean(value?.startsWith(`${PREFIX}:`));}
