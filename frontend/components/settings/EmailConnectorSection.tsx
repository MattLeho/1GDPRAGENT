'use client';
import type { ReactNode } from 'react';
import { useEffect,useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Card,CardContent,CardDescription,CardHeader,CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getEmailSettings,removeEmailCredential,saveEmailCredentials,testImapConnection } from '@/lib/actions/email-settings';
import { toast } from 'sonner';

interface Form { email:string;password:string;imapHost:string;imapPort:string;smtpHost:string;smtpPort:string }
type Status=NonNullable<Awaited<ReturnType<typeof getEmailSettings>>>;

export function EmailConnectorSection(){
    const[status,setStatus]=useState<Status|null>(null);const[busy,setBusy]=useState(false);
    const form=useForm<Form>({defaultValues:{email:'',password:'',imapHost:'imap.gmail.com',imapPort:'993',smtpHost:'smtp.gmail.com',smtpPort:'465'}});
    const apply=(value:Status|null)=>{setStatus(value);if(value)form.reset({email:value.email,password:'',imapHost:value.imap_host,imapPort:String(value.imap_port),smtpHost:value.smtp_host,smtpPort:String(value.smtp_port)})};
    const refresh=async()=>apply(await getEmailSettings());
    useEffect(()=>{let active=true;getEmailSettings().then(value=>{if(active){setStatus(value);if(value)form.reset({email:value.email,password:'',imapHost:value.imap_host,imapPort:String(value.imap_port),smtpHost:value.smtp_host,smtpPort:String(value.smtp_port)})}});return()=>{active=false}},[form]);
    const save=form.handleSubmit(async value=>{setBusy(true);const result=await saveEmailCredentials({email:value.email,password:value.password,imap_host:value.imapHost,imap_port:Number(value.imapPort),smtp_host:value.smtpHost,smtp_port:Number(value.smtpPort),smtp_secure:true});setBusy(false);if(result.success){toast.success(result.message);form.setValue('password','');await refresh()}else toast.error(result.message)});
    const test=async()=>{setBusy(true);const result=await testImapConnection();setBusy(false);if(result.success)toast.success(result.message);else toast.error(result.message);await refresh()};
    const remove=async()=>{setBusy(true);const result=await removeEmailCredential();setBusy(false);if(result.success)toast.success(result.message);else toast.error(result.message);await refresh()};
    return <Card><CardHeader><CardTitle>Email connector</CardTitle><CardDescription>Built-in SMTP sending and incremental IMAP monitoring. Secrets are encrypted after reaching the server and never returned.</CardDescription></CardHeader><CardContent className="space-y-4"><div className="grid gap-3 md:grid-cols-3"><StatusBox label="Status">{status?.credential_status||'Not configured'}</StatusBox><StatusBox label="Permissions">Send and read mail</StatusBox><StatusBox label="Sync">{status?.paused?'Paused':status?.last_sync_at?`Last ${new Date(status.last_sync_at).toLocaleString()}`:'Not yet synced'}</StatusBox></div><form onSubmit={save} className="space-y-3"><div className="grid gap-3 md:grid-cols-2"><Field label="Email"><Input type="email" required {...form.register('email')}/></Field><Field label="App password / token"><Input type="password" required placeholder={status?'Enter to rotate credential':'Enter connector credential'} {...form.register('password')}/></Field><Field label="IMAP host"><Input required {...form.register('imapHost')}/></Field><Field label="IMAP port"><Input type="number" required {...form.register('imapPort')}/></Field><Field label="SMTP host"><Input required {...form.register('smtpHost')}/></Field><Field label="SMTP port"><Input type="number" required {...form.register('smtpPort')}/></Field></div><div className="flex flex-wrap gap-2"><Button type="submit" disabled={busy}>Save / rotate</Button><Button type="button" variant="outline" disabled={busy||!status} onClick={test}>Test connection</Button><Button type="button" variant="destructive" disabled={busy||!status} onClick={remove}>Disconnect</Button></div></form><p className="text-xs text-muted-foreground">Data classes: message headers, controller replies, attachments, and transport metadata. Next sync: {status?.next_sync_at?new Date(status.next_sync_at).toLocaleString():'incremental every 15 minutes'}.</p></CardContent></Card>
}
function Field({label,children}:{label:string;children:ReactNode}){return <div className="space-y-1"><Label>{label}</Label>{children}</div>}
function StatusBox({label,children}:{label:string;children:ReactNode}){return <div className="rounded border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="font-medium">{children}</p></div>}
