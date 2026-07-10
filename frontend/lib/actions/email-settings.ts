'use server';

import { revalidatePath } from 'next/cache';
import { deleteEmailCredential, getEmailConnector, saveEmailConnector, testEmailConnector } from '@/lib/connectors/email';

export type EmailSettings = Awaited<ReturnType<typeof getEmailConnector>> extends infer T ? NonNullable<T> : never;

export async function saveEmailCredentials(settings:{
    email:string; password:string; imap_host:string; imap_port:number;
    smtp_host?:string; smtp_port?:number; smtp_secure?:boolean;
}):Promise<{success:boolean;message:string}>{
    try{await saveEmailConnector(settings);revalidatePath('/dashboard/settings');return{success:true,message:'Email connector encrypted and saved server-side'};}
    catch(error){console.error('Failed to save email connector:',error);return{success:false,message:error instanceof Error?error.message:'Failed to save connector'};}
}

/** Public settings never include ciphertext or decrypted secrets. */
export async function getEmailSettings():Promise<EmailSettings|null>{return getEmailConnector();}

export async function testImapConnection():Promise<{success:boolean;message:string}>{
    const result=await testEmailConnector();revalidatePath('/dashboard/settings');return result;
}

export async function removeEmailCredential():Promise<{success:boolean;message:string}>{
    try{await deleteEmailCredential();revalidatePath('/dashboard/settings');return{success:true,message:'Email credential deleted'};}
    catch(error){return{success:false,message:error instanceof Error?error.message:'Failed to delete credential'};}
}
