'use client';

import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { User, Mail, Key, Upload, Loader2, Save } from 'lucide-react';
import { toast } from 'sonner';

interface UserProfile {
    id?: number;
    username: string;
    email: string;
    profilePictureUrl?: string;
}

export function UserProfileSection() {
    const [isLoading, setIsLoading] = useState(false);
    const [profile, setProfile] = useState<UserProfile>({
        username: '',
        email: '',
        profilePictureUrl: undefined,
    });
    const [passwords, setPasswords] = useState({
        current: '',
        new: '',
        confirm: '',
    });
    const [preview, setPreview] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Load profile on mount
    useEffect(() => {
        async function loadProfile() {
            try {
                const res = await fetch('/api/settings/profile');
                if (res.ok) {
                    const data = await res.json();
                    if (data.profile) {
                        setProfile(data.profile);
                        if (data.profile.profilePictureUrl) {
                            setPreview(data.profile.profilePictureUrl);
                        }
                    }
                }
            } catch (error) {
                console.error('Failed to load profile:', error);
            }
        }
        loadProfile();
    }, []);

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

        setIsLoading(true);
        try {
            const formData = new FormData();
            formData.append('username', profile.username);
            formData.append('email', profile.email);

            // Add profile picture if changed
            if (fileInputRef.current?.files?.[0]) {
                formData.append('profilePicture', fileInputRef.current.files[0]);
            }

            const res = await fetch('/api/settings/profile', {
                method: 'POST',
                body: formData,
            });

            const data = await res.json();

            if (data.success) {
                toast.success('Profile updated successfully');
                if (data.profile) {
                    setProfile(data.profile);
                    if (data.profile.profilePictureUrl) {
                        setPreview(data.profile.profilePictureUrl);
                    }
                }
            } else {
                toast.error(data.error || 'Failed to update profile');
            }
        } catch (error) {
            toast.error('Failed to save profile');
        } finally {
            setIsLoading(false);
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

        setIsLoading(true);
        try {
            const res = await fetch('/api/settings/profile/password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    currentPassword: passwords.current,
                    newPassword: passwords.new,
                }),
            });

            const data = await res.json();

            if (data.success) {
                toast.success('Password changed successfully');
                setPasswords({ current: '', new: '', confirm: '' });
            } else {
                toast.error(data.error || 'Failed to change password');
            }
        } catch (error) {
            toast.error('Failed to change password');
        } finally {
            setIsLoading(false);
        }
    };

    const getInitials = (username: string) => {
        return username
            .split(' ')
            .map(word => word[0])
            .join('')
            .toUpperCase()
            .slice(0, 2) || 'U';
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
                        <AvatarImage src={preview || profile.profilePictureUrl} />
                        <AvatarFallback className="text-2xl">
                            {getInitials(profile.username || 'User')}
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
                        disabled={isLoading || !passwords.current || !passwords.new || !passwords.confirm}
                    >
                        Update Password
                    </Button>
                </div>
            </CardContent>
            <CardFooter>
                <Button onClick={handleSaveProfile} disabled={isLoading}>
                    {isLoading ? (
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
