'use client';

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { User, Mail, Key, Upload, Loader2, Save } from 'lucide-react';
import { toast } from 'sonner';
import { protectedApi, shouldSuppressProtectedRequestError } from '@/lib/api-client';
import { getProfileInitials, useProfileStore } from '@/lib/stores/profile-store';

export function UserProfileSection() {
    const [isChangingPassword, setIsChangingPassword] = useState(false);
    const loadProfile = useProfileStore((state) => state.loadProfile);
    const saveProfile = useProfileStore((state) => state.saveProfile);
    const isSaving = useProfileStore((state) => state.isSaving);
    const [profile, setProfile] = useState(() => {
        const current = useProfileStore.getState().profile;
        return {
            username: current?.username ?? '',
            email: current?.email ?? '',
            profilePictureUrl: current?.profilePictureUrl ?? null,
        };
    });
    const [passwords, setPasswords] = useState({
        current: '',
        new: '',
        confirm: '',
    });
    const [preview, setPreview] = useState<string | null>(() => useProfileStore.getState().profile?.profilePictureUrl ?? null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        return useProfileStore.subscribe((state, previousState) => {
            if (state.profile === previousState.profile) return;
            setProfile({
                username: state.profile?.username ?? '',
                email: state.profile?.email ?? '',
                profilePictureUrl: state.profile?.profilePictureUrl ?? null,
            });
            setPreview(state.profile?.profilePictureUrl ?? null);
        });
    }, []);

    useEffect(() => {
        void loadProfile().catch((error: unknown) => {
            if (shouldSuppressProtectedRequestError(error)) return;
            if (!(error instanceof DOMException && error.name === 'AbortError')) {
                console.error('Failed to load profile:', error);
            }
        });
    }, [loadProfile]);

    const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        // Validate file type
        if (!file.type.startsWith('image/')) {
            toast.error('Please select an image file');
            return;
        }

        // Validate file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            toast.error('Image must be less than 5MB');
            return;
        }

        // Create preview
        const reader = new FileReader();
        reader.onloadend = () => {
            setPreview(reader.result as string);
        };
        reader.readAsDataURL(file);
    };

    const handleSaveProfile = async () => {
        if (!profile.username || !profile.email) {
            toast.error('Username and email are required');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('username', profile.username);
            formData.append('email', profile.email);

            // Add profile picture if changed
            if (fileInputRef.current?.files?.[0]) {
                formData.append('profilePicture', fileInputRef.current.files[0]);
            }

            const updatedProfile = await saveProfile(formData);
            if (updatedProfile) {
                toast.success('Profile updated successfully');
                setPreview(updatedProfile.profilePictureUrl ?? null);
            }
        } catch (error) {
            if (shouldSuppressProtectedRequestError(error)) return;
            toast.error(error instanceof Error ? error.message : 'Failed to save profile');
        }
    };

    const handleChangePassword = async () => {
        if (!passwords.current || !passwords.new || !passwords.confirm) {
            toast.error('All password fields are required');
            return;
        }

        if (passwords.new !== passwords.confirm) {
            toast.error('New passwords do not match');
            return;
        }

        if (passwords.new.length < 8) {
            toast.error('New password must be at least 8 characters');
            return;
        }

        setIsChangingPassword(true);
        try {
            const data = await protectedApi<{ success: boolean; error?: string }>('/api/settings/profile/password', {
                method: 'POST',
                body: JSON.stringify({
                    currentPassword: passwords.current,
                    newPassword: passwords.new,
                }),
            });

            if (data.success) {
                toast.success('Password changed successfully');
                setPasswords({ current: '', new: '', confirm: '' });
            } else {
                toast.error(data.error || 'Failed to change password');
            }
        } catch (error) {
            if (shouldSuppressProtectedRequestError(error)) return;
            toast.error(error instanceof Error ? error.message : 'Failed to change password');
        } finally {
            setIsChangingPassword(false);
        }
    };

    return (
        <Card className="lg:col-span-2">
            <CardHeader>
                <div className="flex items-center gap-2">
                    <User className="h-5 w-5 text-blue-500" />
                    <CardTitle>User Profile</CardTitle>
                </div>
                <CardDescription>
                    Manage your account information and profile picture
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Profile Picture */}
                <div className="flex items-center gap-6">
                    <Avatar className="h-24 w-24">
                        <AvatarImage src={preview || profile.profilePictureUrl || undefined} />
                        <AvatarFallback className="text-2xl">
                            {getProfileInitials(profile.username) || <User className="h-6 w-6" />}
                        </AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            className="hidden"
                            onChange={handleImageSelect}
                        />
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <Upload className="mr-2 h-4 w-4" />
                            Upload Picture
                        </Button>
                        <p className="text-xs text-muted-foreground mt-2">
                            JPG, PNG or GIF. Max 5MB.
                        </p>
                    </div>
                </div>

                {/* Basic Info */}
                <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                        <Label htmlFor="username">Username</Label>
                        <div className="relative">
                            <User className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                id="username"
                                placeholder="johndoe"
                                className="pl-9"
                                value={profile.username}
                                onChange={(e) => setProfile({ ...profile, username: e.target.value })}
                            />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="profile-email">Email</Label>
                        <div className="relative">
                            <Mail className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                id="profile-email"
                                type="email"
                                placeholder="john@example.com"
                                className="pl-9"
                                value={profile.email}
                                onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                            />
                        </div>
                    </div>
                </div>

                <div className="border-t pt-6">
                    <h4 className="font-medium mb-4 flex items-center gap-2">
                        <Key className="h-4 w-4" />
                        Change Password
                    </h4>
                    <div className="grid gap-4 md:grid-cols-3">
                        <div className="space-y-2">
                            <Label htmlFor="current-password">Current Password</Label>
                            <Input
                                id="current-password"
                                type="password"
                                placeholder="••••••••"
                                value={passwords.current}
                                onChange={(e) => setPasswords({ ...passwords, current: e.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="new-password">New Password</Label>
                            <Input
                                id="new-password"
                                type="password"
                                placeholder="••••••••"
                                value={passwords.new}
                                onChange={(e) => setPasswords({ ...passwords, new: e.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="confirm-password">Confirm Password</Label>
                            <Input
                                id="confirm-password"
                                type="password"
                                placeholder="••••••••"
                                value={passwords.confirm}
                                onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })}
                            />
                        </div>
                    </div>
                    <Button
                        type="button"
                        variant="secondary"
                        className="mt-4"
                        onClick={handleChangePassword}
                        disabled={isChangingPassword || !passwords.current || !passwords.new || !passwords.confirm}
                    >
                        Update Password
                    </Button>
                </div>
            </CardContent>
            <CardFooter>
                <Button onClick={handleSaveProfile} disabled={isSaving}>
                    {isSaving ? (
                        <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                        </>
                    ) : (
                        <>
                            <Save className="mr-2 h-4 w-4" />
                            Save Profile
                        </>
                    )}
                </Button>
            </CardFooter>
        </Card>
    );
}
