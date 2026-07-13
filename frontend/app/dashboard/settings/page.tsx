'use client';
import { Tabs,TabsContent,TabsList,TabsTrigger } from '@/components/ui/tabs';
import { UserProfileSection } from '@/components/settings/UserProfileSection';
import { IDDocumentsSection } from '@/components/settings/IDDocumentsSection';
import { EmailConnectorSection } from '@/components/settings/EmailConnectorSection';
import { TaskRoutesSection } from '@/components/settings/TaskRoutesSection';
import { WorkflowSettingsSection } from '@/components/settings/WorkflowSettingsSection';
import { PrivacySecuritySection } from '@/components/settings/PrivacySecuritySection';
import { AICredentialsSection } from '@/components/settings/AICredentialsSection';
import { APICredentialsSection } from '@/components/settings/APICredentialsSection';
import { N8NWebhooksSection } from '@/components/settings/N8NWebhooksSection';
import { SourceConnectorsSection } from '@/components/settings/SourceConnectorsSection';
import { RetentionSettingsSection } from '@/components/settings/RetentionSettingsSection';

const sections=[['profile','Profile & Identity'],['connectors','Connectors'],['processing','Processing & Models'],['workflows','Workflows'],['retention','Data Retention'],['privacy','Privacy & Security'],['advanced','Advanced']] as const;
export default function SettingsPage(){return <div className="mx-auto flex-1 space-y-6 p-6 pt-6 xl:max-w-7xl"><div><h2 className="text-3xl font-bold tracking-tight">Settings</h2><p className="text-muted-foreground">Configure connectors, concrete processing tasks, workflow execution, and privacy controls.</p></div><Tabs defaultValue="profile" orientation="vertical" className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]"><TabsList className="h-auto w-full flex-col items-stretch justify-start bg-muted/50 p-2">{sections.map(([value,label])=><TabsTrigger key={value} value={value} className="justify-start">{label}</TabsTrigger>)}</TabsList><div className="min-w-0"><TabsContent value="profile" className="mt-0 space-y-4"><UserProfileSection/><IDDocumentsSection/></TabsContent><TabsContent value="connectors" className="mt-0 space-y-4"><SourceConnectorsSection/><EmailConnectorSection/></TabsContent><TabsContent value="processing" className="mt-0"><TaskRoutesSection/></TabsContent><TabsContent value="workflows" className="mt-0"><WorkflowSettingsSection/></TabsContent><TabsContent value="retention" className="mt-0"><RetentionSettingsSection/></TabsContent><TabsContent value="privacy" className="mt-0"><PrivacySecuritySection/></TabsContent><TabsContent value="advanced" className="mt-0 space-y-4"><AICredentialsSection/><APICredentialsSection/><N8NWebhooksSection/></TabsContent></div></Tabs></div>}
