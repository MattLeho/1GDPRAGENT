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
export default function SettingsPage(){return <div className="mx-auto min-w-0 flex-1 space-y-4 sm:space-y-6 xl:max-w-7xl"><div><h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Settings</h2><p className="text-sm text-muted-foreground sm:text-base">Configure connectors, concrete processing tasks, workflow execution, and privacy controls.</p></div><Tabs defaultValue="profile" className="grid min-w-0 gap-4 xl:grid-cols-[220px_minmax(0,1fr)] xl:gap-6"><TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto bg-muted/50 p-2 xl:flex-col xl:items-stretch">{sections.map(([value,label])=><TabsTrigger key={value} value={value} className="shrink-0 justify-start">{label}</TabsTrigger>)}</TabsList><div className="min-w-0"><TabsContent value="profile" className="mt-0 space-y-4"><UserProfileSection/><IDDocumentsSection/></TabsContent><TabsContent value="connectors" className="mt-0 space-y-4"><SourceConnectorsSection/><EmailConnectorSection/></TabsContent><TabsContent value="processing" className="mt-0"><TaskRoutesSection/></TabsContent><TabsContent value="workflows" className="mt-0"><WorkflowSettingsSection/></TabsContent><TabsContent value="retention" className="mt-0"><RetentionSettingsSection/></TabsContent><TabsContent value="privacy" className="mt-0"><PrivacySecuritySection/></TabsContent><TabsContent value="advanced" className="mt-0 space-y-4"><AICredentialsSection/><APICredentialsSection/><N8NWebhooksSection/></TabsContent></div></Tabs></div>}
