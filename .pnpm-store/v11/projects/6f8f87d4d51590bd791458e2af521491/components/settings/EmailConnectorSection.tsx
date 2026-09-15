'use client';

import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getEmailSettings, removeEmailCredential, saveEmailCredentials, testImapConnection } from '@/lib/actions/email-settings';
import { toast } from 'sonner';

interface Form {
    email: string;
    password: string;
    imapHost: string;
    imapPort: string;
    smtpHost: string;
    smtpPort: string;
}

type Status = NonNullable<Awaited<ReturnType<typeof getEmailSettings>>>;

export function EmailConnectorSection() {
    const [status, setStatus] = useState<Status | null>(null);
    const [busy, setBusy] = useState(false);
    const form = useForm<Form>({
        defaultValues: {
            email: '', password: '', imapHost: 'imap.gmail.com', imapPort: '993',
            smtpHost: 'smtp.gmail.com', smtpPort: '465',
        },
    });

    const apply = (value: Status | null) => {
        setStatus(value);
        if (value) {
            form.reset({
                email: value.email, password: '', imapHost: value.imap_host,
                imapPort: String(value.imap_port), smtpHost: value.smtp_host,
                smtpPort: String(value.smtp_port),
            });
        }
    };

    const refresh = async () => apply(await getEmailSettings());

    useEffect(() => {
        let active = true;
        void getEmailSettings()
            .then(value => { if (active) apply(value); })
            .catch(() => { if (active) toast.error('Unable to load email connector settings'); });
        return () => { active = false; };
    // apply intentionally uses the stable react-hook-form instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [form]);

    const save = form.handleSubmit(async value => {
        setBusy(true);
        try {
            const result = await saveEmailCredentials({
                email: value.email, password: value.password,
                imap_host: value.imapHost, imap_port: Number(value.imapPort),
                smtp_host: value.smtpHost, smtp_port: Number(value.smtpPort), smtp_secure: true,
            });
            if (result.success) {
                toast.success(result.message);
                form.setValue('password', '');
                await refresh();
            } else toast.error(result.message);
        } catch {
            toast.error('Unable to save email connector settings');
        } finally {
            setBusy(false);
        }
    });

    const test = async () => {
        setBusy(true);
        try {
            const result = await testImapConnection();
            if (result.success) toast.success(result.message);
            else toast.error(result.message);
            await refresh();
        } catch {
            toast.error('Unable to test the IMAP connection');
        } finally {
            setBusy(false);
        }
    };

    const remove = async () => {
        setBusy(true);
        try {
            const result = await removeEmailCredential();
            if (result.success) toast.success(result.message);
            else toast.error(result.message);
            await refresh();
        } catch {
            toast.error('Unable to disconnect the email credential');
        } finally {
            setBusy(false);
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>Email credential</CardTitle>
                <CardDescription>
                    Store SMTP credentials and test IMAP connectivity. Automated inbox monitoring is configured separately through Source Connectors.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-3">
                    <StatusBox label="Credential">{status?.credential_status || 'Not configured'}</StatusBox>
                    <StatusBox label="Available check">IMAP connection test</StatusBox>
                    <StatusBox label="Monitoring">Not configured here</StatusBox>
                </div>
                <form onSubmit={save} className="space-y-3">
                    <div className="grid gap-3 md:grid-cols-2">
                        <Field id="email-connector-email" label="Email"><Input id="email-connector-email" type="email" required {...form.register('email')} /></Field>
                        <Field id="email-connector-password" label="App password / token"><Input id="email-connector-password" type="password" required placeholder={status ? 'Enter to rotate credential' : 'Enter connector credential'} {...form.register('password')} /></Field>
                        <Field id="email-connector-imap-host" label="IMAP host"><Input id="email-connector-imap-host" required {...form.register('imapHost')} /></Field>
                        <Field id="email-connector-imap-port" label="IMAP port"><Input id="email-connector-imap-port" type="number" required {...form.register('imapPort')} /></Field>
                        <Field id="email-connector-smtp-host" label="SMTP host"><Input id="email-connector-smtp-host" required {...form.register('smtpHost')} /></Field>
                        <Field id="email-connector-smtp-port" label="SMTP port"><Input id="email-connector-smtp-port" type="number" required {...form.register('smtpPort')} /></Field>
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                        <Button className="min-h-11 sm:min-h-9" type="submit" disabled={busy}>Save / rotate</Button>
                        <Button className="min-h-11 sm:min-h-9" type="button" variant="outline" disabled={busy || !status} onClick={test}>Test IMAP connection</Button>
                        <Button className="min-h-11 sm:min-h-9" type="button" variant="destructive" disabled={busy || !status} onClick={remove}>Disconnect</Button>
                    </div>
                    <p role="status" aria-live="polite" className="text-xs text-muted-foreground">
                        {busy ? 'Email credential operation in progress.' : 'No periodic inbox monitoring is started by this card.'}
                    </p>
                </form>
            </CardContent>
        </Card>
    );
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
    return <div className="space-y-1"><Label htmlFor={id}>{label}</Label>{children}</div>;
}

function StatusBox({ label, children }: { label: string; children: ReactNode }) {
    return <div className="rounded border p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="font-medium">{children}</p></div>;
}
